# API_forum 统一路由模块
# 本文件整合了所有论坛相关的路由和工具类
# 原始文件来源:
# - common/utils.py (工具类)
# - floor/routes.py (楼层路由)
# - user/user_ops.py (用户操作路由)
# - admin/forum_manage.py (管理员路由)
# - reply/routes.py (回复路由)
# - post/routes.py (帖子路由)
# - post/public.py (公开接口路由)

import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from flask import Blueprint, request, jsonify
from components import token_required, db
from components.models.forum_models import (
    ForumPost, ForumFloor, ForumReply, ForumLike, ForumVisit
)
from components.models.user_models import User
from components.response_service import ResponseService


# ============================================================================
# 第一部分: 工具类定义 (来自 common/utils.py)
# ============================================================================

class SensitiveWordFilter:
    """敏感词过滤工具类"""

    def __init__(self, sensitive_words: List[str] = None):
        """
        初始化敏感词过滤器

        Args:
            sensitive_words: 敏感词列表，如果为空则使用默认敏感词库
        """
        self.sensitive_words = sensitive_words or [
            '违禁词1', '违禁词2', '违禁词3',  # 实际项目中应从配置或数据库加载
            '垃圾信息', '广告', '违法', '暴力', '色情'
        ]
        self.pattern = re.compile('|'.join(map(re.escape, self.sensitive_words)), re.IGNORECASE)

    def filter_content(self, content: str) -> str:
        """
        过滤内容中的敏感词

        Args:
            content: 待过滤的内容

        Returns:
            过滤后的内容
        """
        if not content:
            return content

        # 将敏感词替换为 ***
        filtered_content = self.pattern.sub('***', content)
        return filtered_content

    def contains_sensitive_word(self, content: str) -> bool:
        """
        检查内容是否包含敏感词

        Args:
            content: 待检查的内容

        Returns:
            是否包含敏感词
        """
        if not content:
            return False

        return bool(self.pattern.search(content))

    def get_sensitive_words(self, content: str) -> List[str]:
        """
        获取内容中的敏感词列表

        Args:
            content: 待检查的内容

        Returns:
            找到的敏感词列表
        """
        if not content:
            return []

        return list(set(match.group() for match in self.pattern.finditer(content)))


class PostSorter:
    """帖子排序工具类"""

    @staticmethod
    def sort_posts(posts: List[ForumPost], sort_by: str = 'latest') -> List[ForumPost]:
        """
        根据指定方式排序帖子

        Args:
            posts: 帖子列表
            sort_by: 排序方式 ('latest', 'hottest', 'most_viewed', 'most_liked')

        Returns:
            排序后的帖子列表
        """
        if sort_by == 'latest':
            # 按创建时间倒序
            return sorted(posts, key=lambda x: x.created_at, reverse=True)
        elif sort_by == 'hottest':
            # 按热度计算（点赞数 + 评论数 + 浏览数/10）
            return sorted(posts, key=lambda x: x.calculate_like_count() + x.calculate_comment_count() + x.view_count/10, reverse=True)
        elif sort_by == 'most_viewed':
            # 按浏览量倒序
            return sorted(posts, key=lambda x: x.view_count, reverse=True)
        elif sort_by == 'most_liked':
            # 按点赞数倒序
            return sorted(posts, key=lambda x: x.calculate_like_count(), reverse=True)
        else:
            # 默认按创建时间倒序
            return sorted(posts, key=lambda x: x.created_at, reverse=True)

    @staticmethod
    def get_hot_posts(hours: int = 24, limit: int = 10) -> List[ForumPost]:
        """
        获取热门帖子

        Args:
            hours: 多少小时内的热门帖子
            limit: 返回数量限制

        Returns:
            热门帖子列表
        """
        # 计算时间范围
        time_threshold = datetime.now() - timedelta(hours=hours)

        # 查询指定时间内的帖子
        recent_posts = ForumPost.query.filter(
            ForumPost.created_at >= time_threshold,
            ForumPost.status == 'published'
        ).all()

        # 按热度排序
        hot_posts = PostSorter.sort_posts(recent_posts, 'hottest')

        return hot_posts[:limit]


class PaginationHelper:
    """分页辅助工具类"""

    @staticmethod
    def get_pagination_params() -> Dict[str, int]:
        """
        从请求中获取分页参数

        Returns:
            包含page和per_page的字典
        """
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('size', 20)), 100)  # 限制最大每页数量

        # 确保页码至少为1
        page = max(page, 1)

        return {'page': page, 'per_page': per_page}

    @staticmethod
    def format_pagination_response(pagination, items: List[Any], transform_func=None) -> Dict[str, Any]:
        """
        格式化分页响应

        Args:
            pagination: 分页对象
            items: 数据项列表
            transform_func: 转换函数，用于处理每个item

        Returns:
            格式化的分页响应数据
        """
        if transform_func:
            formatted_items = [transform_func(item) for item in items]
        else:
            formatted_items = items

        return {
            'total': pagination.total,
            'page': pagination.page,
            'size': pagination.per_page,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'items': formatted_items
        }


class PermissionHelper:
    """权限检查辅助工具类"""

    @staticmethod
    def can_edit_post(user, post) -> bool:
        """
        检查用户是否可以编辑帖子

        Args:
            user: 当前用户对象
            post: 帖子对象

        Returns:
            是否有编辑权限
        """
        # 管理员可以编辑所有帖子
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        # 帖子作者可以编辑
        if hasattr(user, 'is_deleted'):  # 普通用户
            return post.author_user_id == user.id
        elif hasattr(user, 'role'):  # 管理员用户
            return post.author_user_id == user.id

        return False

    @staticmethod
    def can_delete_post(user, post) -> bool:
        """
        检查用户是否可以删除帖子

        Args:
            user: 当前用户对象
            post: 帖子对象

        Returns:
            是否有删除权限
        """
        # 管理员可以删除所有帖子
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        # 帖子作者可以删除
        if hasattr(user, 'is_deleted'):  # 普通用户
            return post.author_user_id == user.id
        elif hasattr(user, 'role'):  # 管理员用户
            return post.author_user_id == user.id

        return False

    @staticmethod
    def can_edit_floor(user, floor) -> bool:
        """
        检查用户是否可以编辑楼层

        Args:
            user: 当前用户对象
            floor: 楼层对象

        Returns:
            是否有编辑权限
        """
        # 管理员可以编辑所有楼层
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        # 楼层作者可以编辑
        if hasattr(user, 'is_deleted'):  # 普通用户
            return floor.author_user_id == user.id
        elif hasattr(user, 'role'):  # 管理员用户
            return floor.author_user_id == user.id

        return False

    @staticmethod
    def can_edit_reply(user, reply) -> bool:
        """
        检查用户是否可以编辑回复

        Args:
            user: 当前用户对象
            reply: 回复对象

        Returns:
            是否有编辑权限
        """
        # 管理员可以编辑所有回复
        if hasattr(user, 'role') and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True

        # 回复作者可以编辑
        if hasattr(user, 'is_deleted'):  # 普通用户
            return reply.author_user_id == user.id
        elif hasattr(user, 'role'):  # 管理员用户
            return reply.author_user_id == user.id

        return False


class ForumStatsHelper:
    """论坛统计辅助工具类"""

    @staticmethod
    def get_post_stats(days: int = 7) -> Dict[str, int]:
        """
        获取帖子统计信息

        Args:
            days: 统计天数

        Returns:
            统计信息字典
        """
        time_threshold = datetime.now() - timedelta(days=days)

        total_posts = ForumPost.query.count()
        recent_posts = ForumPost.query.filter(
            ForumPost.created_at >= time_threshold
        ).count()
        published_posts = ForumPost.query.filter_by(status='published').count()

        return {
            'total': total_posts,
            'recent': recent_posts,
            'published': published_posts,
            'draft': total_posts - published_posts
        }

    @staticmethod
    def get_user_participation_stats(user_id: int, days: int = 30) -> Dict[str, int]:
        """
        获取用户参与统计

        Args:
            user_id: 用户ID
            days: 统计天数

        Returns:
            用户参与统计信息
        """
        time_threshold = datetime.now() - timedelta(days=days)

        posts_count = ForumPost.query.filter(
            ForumPost.author_user_id == user_id,
            ForumPost.created_at >= time_threshold
        ).count()

        floors_count = ForumFloor.query.filter(
            ForumFloor.author_user_id == user_id,
            ForumFloor.created_at >= time_threshold
        ).count()

        replies_count = ForumReply.query.filter(
            ForumReply.author_user_id == user_id,
            ForumReply.created_at >= time_threshold
        ).count()

        return {
            'posts': posts_count,
            'floors': floors_count,
            'replies': replies_count,
            'total': posts_count + floors_count + replies_count
        }


# 全局实例
sensitive_filter = SensitiveWordFilter()
post_sorter = PostSorter()


def validate_content(content: str, min_length: int = 1, max_length: int = 10000) -> Dict[str, Any]:
    """
    验证内容

    Args:
        content: 待验证内容
        min_length: 最小长度
        max_length: 最大长度

    Returns:
        验证结果 {'valid': bool, 'message': str}
    """
    if not content or len(content.strip()) < min_length:
        return {'valid': False, 'message': f'内容不能少于{min_length}个字符'}

    if len(content) > max_length:
        return {'valid': False, 'message': f'内容不能超过{max_length}个字符'}

    if sensitive_filter.contains_sensitive_word(content):
        found_words = sensitive_filter.get_sensitive_words(content)
        return {'valid': False, 'message': f'内容包含敏感词：{", ".join(found_words)}'}

    return {'valid': True, 'message': '内容验证通过'}


def create_nested_reply_structure(replies: List[ForumReply]) -> List[Dict[str, Any]]:
    """
    创建嵌套回复结构

    Args:
        replies: 回复列表

    Returns:
        嵌套结构的回复列表
    """
    # 这里可以实现更复杂的嵌套逻辑
    # 当前只是简单的平铺结构，可以根据需要扩展
    result = []

    for reply in replies:
        reply_data = {
            'id': reply.id,
            'content': reply.content,
            'author_display': reply.author_display,
            'like_count': reply.calculate_like_count(),
            'quote_content': reply.quote_content,
            'quote_author': reply.quote_author,
            'created_at': reply.created_at.isoformat() if reply.created_at else None,
            'updated_at': reply.updated_at.isoformat() if reply.updated_at else None
        }
        result.append(reply_data)

    return result


# ============================================================================
# 第二部分: 蓝图定义
# ============================================================================

# 创建帖子模块蓝图
post_bp = Blueprint('post', __name__, url_prefix='/api/forum/posts')

# 创建楼层模块蓝图
floor_bp = Blueprint('floor', __name__, url_prefix='/api/forum/floors')

# 创建回复模块蓝图
reply_bp = Blueprint('reply', __name__, url_prefix='/api/forum/replies')

# 创建用户模块蓝图（使用唯一名称避免与其他 user 模块冲突）
user_bp = Blueprint('forum_user', __name__, url_prefix='/api/forum/users')

# 创建管理员模块蓝图（使用唯一名称避免与 API_admin 冲突）
admin_bp = Blueprint('forum_admin', __name__, url_prefix='/api/forum/admin')

# 创建论坛公开访问模块蓝图
bp_forum_public = Blueprint('forum_public', __name__, url_prefix='/api/public/forum')


# ============================================================================
# 第三部分: 数据转换函数
# ============================================================================

def post_to_dict(post, include_content=True, include_user_info=False):
    """将帖子对象转换为字典"""
    result = {
        'id': post.id,
        'title': post.title,
        'category': post.category,
        'view_count': post.view_count,
        'like_count': post.calculate_like_count(),
        'comment_count': post.calculate_comment_count(),
        'status': post.status,
        'author_display': post.author_display,
        'created_at': post.created_at.isoformat() if post.created_at else None,
        'updated_at': post.updated_at.isoformat() if post.updated_at else None
    }

    if include_content:
        result['content'] = post.content

    if include_user_info and post.author_user_id:
        author = User.query.get(post.author_user_id)
        if author:
            result['author_info'] = {
                'id': author.id,
                'username': author.username,
                'email': author.email,
                'role': author.role,
                'is_deleted': author.is_deleted
            }

    if not include_user_info:
        result['author_user_id'] = post.author_user_id

    return result


def floor_to_dict(floor, include_replies=False, replies_limit=3, include_user_info=False):
    """将楼层对象转换为字典"""
    result = {
        'id': floor.id,
        'post_id': floor.post_id,
        'content': floor.content,
        'floor_number': floor.floor_number,
        'like_count': floor.calculate_like_count(),
        'reply_count': floor.calculate_reply_count(),
        'status': floor.status,
        'author_display': floor.author_display,
        'created_at': floor.created_at.isoformat() if floor.created_at else None,
        'updated_at': floor.updated_at.isoformat() if floor.updated_at else None
    }

    if include_replies:
        # 获取最近的回复
        recent_replies = ForumReply.query.filter_by(
            floor_id=floor.id,
            status='published'
        ).order_by(ForumReply.created_at.desc()).limit(replies_limit).all()

        result['recent_replies'] = create_nested_reply_structure(recent_replies)
        result['total_replies'] = floor.calculate_reply_count()

    if include_user_info and floor.author_user_id:
        author = User.query.get(floor.author_user_id)
        if author:
            result['author_info'] = {
                'id': author.id,
                'username': author.username,
                'email': author.email,
                'role': author.role,
                'is_deleted': author.is_deleted
            }

    if not include_user_info:
        result['author_user_id'] = floor.author_user_id

    return result


def reply_to_dict(reply, include_user_info=False):
    """将回复对象转换为字典"""
    result = {
        'id': reply.id,
        'floor_id': reply.floor_id,
        'content': reply.content,
        'like_count': reply.calculate_like_count(),
        'status': reply.status,
        'author_display': reply.author_display,
        'quote_content': reply.quote_content,
        'quote_author': reply.quote_author,
        'created_at': reply.created_at.isoformat() if reply.created_at else None,
        'updated_at': reply.updated_at.isoformat() if reply.updated_at else None
    }

    if include_user_info and reply.author_user_id:
        author = User.query.get(reply.author_user_id)
        if author:
            result['author_info'] = {
                'id': author.id,
                'username': author.username,
                'email': author.email,
                'role': author.role,
                'is_deleted': author.is_deleted
            }

    if not include_user_info:
        result['author_user_id'] = reply.author_user_id

    return result


# ============================================================================
# 第四部分: 帖子路由 (来自 post/routes.py)
# ============================================================================

@post_bp.route('', methods=['GET'])
def get_posts():
    """获取论坛帖子列表（分页查询，支持筛选和排序）"""
    try:
        # 获取查询参数
        category = request.args.get('category', '').strip()
        status = request.args.get('status', 'published').strip()
        keyword = request.args.get('keyword', '').strip()
        sort_by = request.args.get('sort', 'latest').strip()  # latest, hottest, most_viewed, most_liked

        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        # 构建查询
        query = ForumPost.query

        # 应用筛选条件
        if category:
            query = query.filter(ForumPost.category == category)
        if status:
            query = query.filter(ForumPost.status == status)
        if keyword:
            query = query.filter(
                (ForumPost.title.like(f'%{keyword}%')) |
                (ForumPost.content.like(f'%{keyword}%'))
            )

        # 执行查询
        posts = query.all()

        # 排序
        sorted_posts = post_sorter.sort_posts(posts, sort_by)

        # 手动分页
        start = (page - 1) * per_page
        end = start + per_page
        paginated_posts = sorted_posts[start:end]
        total = len(sorted_posts)

        # 格式化响应
        response_data = PaginationHelper.format_pagination_response(
            type('Pagination', (), {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page,
                'has_prev': page > 1,
                'has_next': end < total
            })(),
            paginated_posts,
            post_to_dict
        )

        return ResponseService.success(
            data=response_data,
            message='查询成功' if total > 0 else '无匹配数据'
        )

    except Exception as e:
        print(f"【论坛帖子查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@post_bp.route('/<int:post_id>', methods=['GET'])
def get_post_detail(post_id):
    """获取论坛帖子详情（同时增加浏览计数）"""
    try:
        post = ForumPost.query.get(post_id)

        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        # 增加浏览计数
        post.increment_view_count()

        return ResponseService.success(
            data=post_to_dict(post),
            message='查询成功'
        )

    except Exception as e:
        print(f"【论坛帖子详情查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@post_bp.route('', methods=['POST'])
@token_required
def create_post(current_user):
    """创建论坛帖子"""
    try:
        data = request.get_json()

        # 验证必填字段
        if not data or not data.get('title', '').strip():
            return ResponseService.error('标题不能为空', status_code=400)
        if not data.get('content', '').strip():
            return ResponseService.error('内容不能为空', status_code=400)

        title = data['title'].strip()
        content = data['content'].strip()
        category = data.get('category', 'default').strip()
        status = data.get('status', 'published').strip()

        # 验证内容
        title_validation = validate_content(title, min_length=1, max_length=200)
        if not title_validation['valid']:
            return ResponseService.error(title_validation['message'], status_code=400)

        content_validation = validate_content(content, min_length=1, max_length=10000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        # 敏感词过滤
        filtered_title = sensitive_filter.filter_content(title)
        filtered_content = sensitive_filter.filter_content(content)

        # 创建帖子
        post = ForumPost(
            title=filtered_title,
            content=filtered_content,
            category=category,
            status=status,
            author_user_id=current_user.id if hasattr(current_user, 'is_deleted') else None,
            author_display=current_user.username
        )

        post.update_author_display()
        db.session.add(post)
        db.session.commit()

        print(f"【论坛帖子创建成功】帖子ID: {post.id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=post_to_dict(post),
            message='帖子创建成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【论坛帖子创建异常】错误: {str(e)}")
        return ResponseService.error(f'帖子创建失败: {str(e)}', status_code=500)


@post_bp.route('/<int:post_id>', methods=['PUT'])
@token_required
def update_post(current_user, post_id):
    """更新论坛帖子"""
    try:
        post = ForumPost.query.get(post_id)

        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        # 检查权限
        if not PermissionHelper.can_edit_post(current_user, post):
            return ResponseService.error('无权限修改此帖子', status_code=403)

        data = request.get_json()

        # 更新字段
        if 'title' in data:
            title = data['title'].strip()
            title_validation = validate_content(title, min_length=1, max_length=200)
            if not title_validation['valid']:
                return ResponseService.error(title_validation['message'], status_code=400)
            post.title = sensitive_filter.filter_content(title)

        if 'content' in data:
            content = data['content'].strip()
            content_validation = validate_content(content, min_length=1, max_length=10000)
            if not content_validation['valid']:
                return ResponseService.error(content_validation['message'], status_code=400)
            post.content = sensitive_filter.filter_content(content)

        if 'category' in data:
            post.category = data['category'].strip()

        if 'status' in data:
            post.status = data['status'].strip()

        post.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【论坛帖子更新成功】帖子ID: {post_id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=post_to_dict(post),
            message='帖子更新成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【论坛帖子更新异常】错误: {str(e)}")
        return ResponseService.error(f'帖子更新失败: {str(e)}', status_code=500)


@post_bp.route('/<int:post_id>', methods=['DELETE'])
@token_required
def delete_post(current_user, post_id):
    """删除论坛帖子（软删除，改为deleted状态）"""
    try:
        post = ForumPost.query.get(post_id)

        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        # 检查权限
        if not PermissionHelper.can_delete_post(current_user, post):
            return ResponseService.error('无权限删除此帖子', status_code=403)

        # 软删除：更新状态为deleted
        post.status = 'deleted'
        post.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【论坛帖子删除成功】帖子ID: {post_id}, 作者: {current_user.account}")

        return ResponseService.success(message='帖子删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【论坛帖子删除异常】错误: {str(e)}")
        return ResponseService.error(f'帖子删除失败: {str(e)}', status_code=500)


@post_bp.route('/hot', methods=['GET'])
def get_hot_posts():
    """获取热门帖子"""
    try:
        hours = int(request.args.get('hours', 24))
        limit = min(int(request.args.get('limit', 10)), 50)  # 限制最大返回数量

        hot_posts = post_sorter.get_hot_posts(hours, limit)

        posts_data = [post_to_dict(post, include_content=False) for post in hot_posts]

        return ResponseService.success(
            data=posts_data,
            message='热门帖子查询成功'
        )

    except Exception as e:
        print(f"【热门帖子查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@post_bp.route('/categories', methods=['GET'])
def get_categories():
    """获取帖子分类列表"""
    try:
        # 获取所有不同的分类
        categories = db.session.query(ForumPost.category).filter(
            ForumPost.category.isnot(None),
            ForumPost.category != ''
        ).distinct().all()

        category_list = [cat[0] for cat in categories if cat[0]]

        return ResponseService.success(
            data=category_list,
            message='分类列表查询成功'
        )

    except Exception as e:
        print(f"【分类列表查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@post_bp.route('/search', methods=['GET'])
def search_posts():
    """搜索帖子"""
    try:
        keyword = request.args.get('q', '').strip()
        if not keyword:
            return ResponseService.error('搜索关键词不能为空', status_code=400)

        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        # 搜索查询
        query = ForumPost.query.filter(
            ForumPost.status == 'published',
            (ForumPost.title.like(f'%{keyword}%')) |
            (ForumPost.content.like(f'%{keyword}%'))
        )

        pagination = query.order_by(ForumPost.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # 格式化响应
        response_data = PaginationHelper.format_pagination_response(
            pagination,
            pagination.items,
            lambda post: post_to_dict(post, include_content=False)
        )

        return ResponseService.success(
            data=response_data,
            message='搜索成功' if pagination.total > 0 else '无搜索结果'
        )

    except Exception as e:
        print(f"【帖子搜索异常】错误: {str(e)}")
        return ResponseService.error(f'搜索失败：{str(e)}', status_code=500)


# ============================================================================
# 第五部分: 楼层路由 (来自 floor/routes.py)
# ============================================================================

@floor_bp.route('/post/<int:post_id>', methods=['GET'])
def get_floors_by_post(post_id):
    """获取帖子的楼层列表"""
    try:
        # 验证帖子存在
        post = ForumPost.query.get(post_id)
        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        # 获取是否包含回复的参数
        include_replies = request.args.get('include_replies', 'false').lower() == 'true'
        replies_limit = min(int(request.args.get('replies_limit', 3)), 10)

        # 使用模型的内置方法获取楼层
        floors_data = ForumFloor.get_floors_by_post(post_id, page, per_page)

        # 转换楼层数据
        floors_list = []
        for floor_data in floors_data['floors']:
            floor = floor_data['floor']
            floor_dict = floor_to_dict(floor, include_replies, replies_limit)

            if include_replies:
                floor_dict['recent_replies'] = create_nested_reply_structure(floor_data['recent_replies'])
                floor_dict['total_replies'] = floor_data['total_replies']

            floors_list.append(floor_dict)

        # 格式化分页信息
        pagination = floors_data['pagination']
        response_data = {
            'total': pagination.total,
            'page': pagination.page,
            'size': pagination.per_page,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'total_floors': floors_data['total_floors'],
            'items': floors_list
        }

        return ResponseService.success(
            data=response_data,
            message='楼层列表查询成功' if pagination.total > 0 else '暂无楼层'
        )

    except Exception as e:
        print(f"【楼层列表查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@floor_bp.route('/<int:floor_id>', methods=['GET'])
def get_floor_detail(floor_id):
    """获取楼层详情"""
    try:
        floor = ForumFloor.query.get(floor_id)

        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        # 获取是否包含回复的参数
        include_replies = request.args.get('include_replies', 'true').lower() == 'true'

        result = floor_to_dict(floor, include_replies=False)

        if include_replies:
            # 获取该楼层的所有回复
            page = int(request.args.get('page', 1))
            per_page = min(int(request.args.get('size', 20)), 100)

            replies_pagination = ForumReply.get_replies_by_floor(floor_id, page, per_page)
            replies_data = create_nested_reply_structure(replies_pagination.items)

            result['replies'] = {
                'total': replies_pagination.total,
                'page': replies_pagination.page,
                'size': replies_pagination.per_page,
                'pages': replies_pagination.pages,
                'has_prev': replies_pagination.has_prev,
                'has_next': replies_pagination.has_next,
                'items': replies_data
            }

        return ResponseService.success(
            data=result,
            message='楼层详情查询成功'
        )

    except Exception as e:
        print(f"【楼层详情查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@floor_bp.route('/post/<int:post_id>', methods=['POST'])
@token_required
def create_floor(current_user, post_id):
    """创建楼层（回复帖子）"""
    try:
        # 验证帖子存在
        post = ForumPost.query.get(post_id)
        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        if post.status != 'published':
            return ResponseService.error('只能回复已发布的帖子', status_code=400)

        data = request.get_json()
        content = data.get('content', '').strip()

        if not content:
            return ResponseService.error('回复内容不能为空', status_code=400)

        # 验证内容
        content_validation = validate_content(content, min_length=1, max_length=5000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        # 敏感词过滤
        filtered_content = sensitive_filter.filter_content(content)

        # 创建楼层
        floor = ForumFloor.create_floor(
            post_id=post_id,
            user_id=current_user.id if hasattr(current_user, 'is_deleted') else current_user.id,
            content=filtered_content
        )

        if not floor:
            return ResponseService.error('创建楼层失败', status_code=500)

        floor.update_author_display()

        print(f"【楼层创建成功】楼层ID: {floor.id}, 帖子ID: {post_id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=floor_to_dict(floor),
            message='回复发布成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【楼层创建异常】错误: {str(e)}")
        return ResponseService.error(f'回复发布失败: {str(e)}', status_code=500)


@floor_bp.route('/<int:floor_id>', methods=['PUT'])
@token_required
def update_floor(current_user, floor_id):
    """更新楼层"""
    try:
        floor = ForumFloor.query.get(floor_id)

        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        # 检查权限
        if not PermissionHelper.can_edit_floor(current_user, floor):
            return ResponseService.error('无权限修改此楼层', status_code=403)

        data = request.get_json()
        content = data.get('content', '').strip()

        if not content:
            return ResponseService.error('回复内容不能为空', status_code=400)

        # 验证内容
        content_validation = validate_content(content, min_length=1, max_length=5000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        # 敏感词过滤
        filtered_content = sensitive_filter.filter_content(content)

        # 更新楼层
        floor.content = filtered_content
        floor.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【楼层更新成功】楼层ID: {floor_id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=floor_to_dict(floor),
            message='楼层更新成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【楼层更新异常】错误: {str(e)}")
        return ResponseService.error(f'楼层更新失败: {str(e)}', status_code=500)


@floor_bp.route('/<int:floor_id>', methods=['DELETE'])
@token_required
def delete_floor(current_user, floor_id):
    """删除楼层（软删除，改为deleted状态）"""
    try:
        floor = ForumFloor.query.get(floor_id)

        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        # 检查权限
        if not PermissionHelper.can_edit_floor(current_user, floor):
            return ResponseService.error('无权限删除此楼层', status_code=403)

        # 删除楼层（会同步更新帖子计数）
        floor.delete_floor()

        print(f"【楼层删除成功】楼层ID: {floor_id}, 作者: {current_user.account}")

        return ResponseService.success(message='楼层删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【楼层删除异常】错误: {str(e)}")
        return ResponseService.error(f'楼层删除失败: {str(e)}', status_code=500)


@floor_bp.route('/<int:floor_id>/like', methods=['POST'])
@token_required
def like_floor(current_user, floor_id):
    """点赞楼层"""
    try:
        # 验证楼层存在
        floor = ForumFloor.query.get(floor_id)
        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id

        # 创建点赞记录
        like = ForumLike.create_like(
            user_id=user_id,
            target_type='floor',
            target_id=floor_id,
            floor_id=floor_id
        )

        if not like:
            return ResponseService.error('您已经点赞过了', status_code=400)

        print(f"【楼层点赞成功】楼层ID: {floor_id}, 用户: {current_user.account}")

        return ResponseService.success(message='点赞成功')

    except Exception as e:
        db.session.rollback()
        print(f"【楼层点赞异常】错误: {str(e)}")
        return ResponseService.error(f'点赞失败: {str(e)}', status_code=500)


@floor_bp.route('/<int:floor_id>/like', methods=['DELETE'])
@token_required
def unlike_floor(current_user, floor_id):
    """取消点赞楼层"""
    try:
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id

        # 取消点赞
        success = ForumLike.remove_like(
            user_id=user_id,
            target_type='floor',
            target_id=floor_id,
            floor_id=floor_id
        )

        if not success:
            return ResponseService.error('您还未点赞', status_code=400)

        print(f"【取消楼层点赞成功】楼层ID: {floor_id}, 用户: {current_user.account}")

        return ResponseService.success(message='取消点赞成功')

    except Exception as e:
        db.session.rollback()
        print(f"【取消楼层点赞异常】错误: {str(e)}")
        return ResponseService.error(f'取消点赞失败: {str(e)}', status_code=500)


@floor_bp.route('/user/<int:user_id>', methods=['GET'])
def get_floors_by_user(user_id):
    """获取用户发布的楼层列表"""
    try:
        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        # 查询用户发布的楼层
        query = ForumFloor.query.filter_by(
            author_user_id=user_id,
            status='published'
        ).order_by(ForumFloor.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # 格式化响应
        response_data = PaginationHelper.format_pagination_response(
            pagination,
            pagination.items,
            lambda floor: floor_to_dict(floor, include_replies=False)
        )

        return ResponseService.success(
            data=response_data,
            message='用户楼层列表查询成功' if pagination.total > 0 else '暂无楼层'
        )

    except Exception as e:
        print(f"【用户楼层查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# ============================================================================
# 第六部分: 回复路由 (来自 reply/routes.py)
# ============================================================================

@reply_bp.route('/floor/<int:floor_id>', methods=['GET'])
def get_replies_by_floor(floor_id):
    """获取楼层的回复列表"""
    try:
        # 验证楼层存在
        floor = ForumFloor.query.get(floor_id)
        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        # 使用模型的内置方法获取回复
        replies_pagination = ForumReply.get_replies_by_floor(floor_id, page, per_page)

        # 格式化响应
        response_data = PaginationHelper.format_pagination_response(
            replies_pagination,
            replies_pagination.items,
            reply_to_dict
        )

        return ResponseService.success(
            data=response_data,
            message='回复列表查询成功' if replies_pagination.total > 0 else '暂无回复'
        )

    except Exception as e:
        print(f"【回复列表查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@reply_bp.route('/<int:reply_id>', methods=['GET'])
def get_reply_detail(reply_id):
    """获取回复详情"""
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        return ResponseService.success(
            data=reply_to_dict(reply),
            message='回复详情查询成功'
        )

    except Exception as e:
        print(f"【回复详情查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@reply_bp.route('/floor/<int:floor_id>', methods=['POST'])
@token_required
def create_reply(current_user, floor_id):
    """创建回复（回复楼层）"""
    try:
        # 验证楼层存在
        floor = ForumFloor.query.get(floor_id)
        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        if floor.status != 'published':
            return ResponseService.error('只能回复已发布的楼层', status_code=400)

        data = request.get_json()
        content = data.get('content', '').strip()
        quote_content = data.get('quote_content', '').strip() or None
        quote_author = data.get('quote_author', '').strip() or None

        if not content:
            return ResponseService.error('回复内容不能为空', status_code=400)

        # 验证内容
        content_validation = validate_content(content, min_length=1, max_length=2000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        # 如果有引用内容，也要验证
        if quote_content:
            quote_validation = validate_content(quote_content, min_length=1, max_length=500)
            if not quote_validation['valid']:
                return ResponseService.error(quote_validation['message'], status_code=400)

        # 敏感词过滤
        filtered_content = sensitive_filter.filter_content(content)
        filtered_quote_content = sensitive_filter.filter_content(quote_content) if quote_content else None

        # 创建回复
        reply = ForumReply.create_reply(
            floor_id=floor_id,
            user_id=current_user.id if hasattr(current_user, 'is_deleted') else current_user.id,
            content=filtered_content,
            quote_content=filtered_quote_content,
            quote_author=quote_author
        )

        if not reply:
            return ResponseService.error('创建回复失败', status_code=500)

        reply.update_author_display()

        print(f"【回复创建成功】回复ID: {reply.id}, 楼层ID: {floor_id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=reply_to_dict(reply),
            message='回复发布成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【回复创建异常】错误: {str(e)}")
        return ResponseService.error(f'回复发布失败: {str(e)}', status_code=500)


@reply_bp.route('/<int:reply_id>', methods=['PUT'])
@token_required
def update_reply(current_user, reply_id):
    """更新回复"""
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        # 检查权限
        if not PermissionHelper.can_edit_reply(current_user, reply):
            return ResponseService.error('无权限修改此回复', status_code=403)

        data = request.get_json()
        content = data.get('content', '').strip()

        if not content:
            return ResponseService.error('回复内容不能为空', status_code=400)

        # 验证内容
        content_validation = validate_content(content, min_length=1, max_length=2000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        # 敏感词过滤
        filtered_content = sensitive_filter.filter_content(content)

        # 更新回复
        reply.content = filtered_content
        reply.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【回复更新成功】回复ID: {reply_id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=reply_to_dict(reply),
            message='回复更新成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【回复更新异常】错误: {str(e)}")
        return ResponseService.error(f'回复更新失败: {str(e)}', status_code=500)


@reply_bp.route('/<int:reply_id>', methods=['DELETE'])
@token_required
def delete_reply(current_user, reply_id):
    """删除回复（软删除，改为deleted状态）"""
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        # 检查权限
        if not PermissionHelper.can_edit_reply(current_user, reply):
            return ResponseService.error('无权限删除此回复', status_code=403)

        # 删除回复（会同步更新楼层计数）
        reply.delete_reply()

        print(f"【回复删除成功】回复ID: {reply_id}, 作者: {current_user.account}")

        return ResponseService.success(message='回复删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【回复删除异常】错误: {str(e)}")
        return ResponseService.error(f'回复删除失败: {str(e)}', status_code=500)


@reply_bp.route('/<int:reply_id>/like', methods=['POST'])
@token_required
def like_reply(current_user, reply_id):
    """点赞回复"""
    try:
        # 验证回复存在
        reply = ForumReply.query.get(reply_id)
        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id

        # 创建点赞记录
        like = ForumLike.create_like(
            user_id=user_id,
            target_type='reply',
            target_id=reply_id,
            reply_id=reply_id
        )

        if not like:
            return ResponseService.error('您已经点赞过了', status_code=400)

        print(f"【回复点赞成功】回复ID: {reply_id}, 用户: {current_user.account}")

        return ResponseService.success(message='点赞成功')

    except Exception as e:
        db.session.rollback()
        print(f"【回复点赞异常】错误: {str(e)}")
        return ResponseService.error(f'点赞失败: {str(e)}', status_code=500)


@reply_bp.route('/<int:reply_id>/like', methods=['DELETE'])
@token_required
def unlike_reply(current_user, reply_id):
    """取消点赞回复"""
    try:
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id

        # 取消点赞
        success = ForumLike.remove_like(
            user_id=user_id,
            target_type='reply',
            target_id=reply_id,
            reply_id=reply_id
        )

        if not success:
            return ResponseService.error('您还未点赞', status_code=400)

        print(f"【取消回复点赞成功】回复ID: {reply_id}, 用户: {current_user.account}")

        return ResponseService.success(message='取消点赞成功')

    except Exception as e:
        db.session.rollback()
        print(f"【取消回复点赞异常】错误: {str(e)}")
        return ResponseService.error(f'取消点赞失败: {str(e)}', status_code=500)


@reply_bp.route('/user/<int:user_id>', methods=['GET'])
def get_replies_by_user(user_id):
    """获取用户发布的回复列表"""
    try:
        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        # 查询用户发布的回复
        query = ForumReply.query.filter_by(
            author_user_id=user_id,
            status='published'
        ).order_by(ForumReply.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # 获取楼层和帖子信息
        replies_data = []
        for reply in pagination.items:
            reply_dict = reply_to_dict(reply)

            # 获取楼层信息
            floor = ForumFloor.query.get(reply.floor_id)
            if floor:
                reply_dict['floor_number'] = floor.floor_number

                # 获取帖子信息
                post = ForumPost.query.get(floor.post_id)
                if post:
                    reply_dict['post_title'] = post.title
                    reply_dict['post_id'] = post.id

            replies_data.append(reply_dict)

        # 格式化响应
        response_data = {
            'total': pagination.total,
            'page': pagination.page,
            'size': pagination.per_page,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'items': replies_data
        }

        return ResponseService.success(
            data=response_data,
            message='用户回复列表查询成功' if pagination.total > 0 else '暂无回复'
        )

    except Exception as e:
        print(f"【用户回复查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@reply_bp.route('/recent', methods=['GET'])
def get_recent_replies():
    """获取最新回复列表"""
    try:
        limit = min(int(request.args.get('limit', 20)), 100)

        # 查询最新回复
        recent_replies = ForumReply.query.filter_by(
            status='published'
        ).order_by(ForumReply.created_at.desc()).limit(limit).all()

        # 获取详细信息
        replies_data = []
        for reply in recent_replies:
            reply_dict = reply_to_dict(reply)

            # 获取楼层和帖子信息
            floor = ForumFloor.query.get(reply.floor_id)
            if floor:
                reply_dict['floor_number'] = floor.floor_number

                # 获取帖子信息
                post = ForumPost.query.get(floor.post_id)
                if post:
                    reply_dict['post_title'] = post.title
                    reply_dict['post_id'] = post.id

            replies_data.append(reply_dict)

        return ResponseService.success(
            data=replies_data,
            message='最新回复查询成功'
        )

    except Exception as e:
        print(f"【最新回复查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@reply_bp.route('/quote/<int:reply_id>', methods=['GET'])
def get_quote_info(reply_id):
    """获取回复的引用信息（用于楼中楼功能）"""
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        # 获取楼层和帖子信息
        floor = ForumFloor.query.get(reply.floor_id)
        post_info = None
        floor_info = None

        if floor:
            floor_info = {
                'id': floor.id,
                'floor_number': floor.floor_number,
                'author_display': floor.author_display
            }

            post = ForumPost.query.get(floor.post_id)
            if post:
                post_info = {
                    'id': post.id,
                    'title': post.title
                }

        quote_info = {
            'reply': reply_to_dict(reply),
            'floor': floor_info,
            'post': post_info
        }

        return ResponseService.success(
            data=quote_info,
            message='引用信息查询成功'
        )

    except Exception as e:
        print(f"【引用信息查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# ============================================================================
# 第七部分: 用户操作路由 (来自 user/user_ops.py)
# ============================================================================

@user_bp.route('/posts', methods=['GET'])
@token_required
def get_my_posts(current_user):
    """获取当前用户发布的帖子列表"""
    try:
        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        status = request.args.get('status', '').strip()
        keyword = request.args.get('keyword', '').strip()
        category = request.args.get('category', '').strip()

        # 构建查询
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        query = ForumPost.query.filter_by(author_user_id=user_id)

        # 状态筛选
        if status:
            query = query.filter(ForumPost.status == status)

        # 分类筛选
        if category:
            query = query.filter(ForumPost.category == category)

        # 关键词搜索
        if keyword:
            query = query.filter(
                (ForumPost.title.like(f'%{keyword}%')) |
                (ForumPost.content.like(f'%{keyword}%'))
            )

        # 分页查询（按更新时间倒序）
        pagination = query.order_by(ForumPost.updated_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # 格式化响应
        response_data = PaginationHelper.format_pagination_response(
            pagination,
            pagination.items,
            post_to_dict
        )

        return ResponseService.success(
            data=response_data,
            message='我的帖子列表查询成功'
        )

    except Exception as e:
        print(f"【我的帖子查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@user_bp.route('/floors', methods=['GET'])
@token_required
def get_my_floors(current_user):
    """获取当前用户发布的楼层列表"""
    try:
        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        keyword = request.args.get('keyword', '').strip()

        # 构建查询
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        query = ForumFloor.query.filter_by(author_user_id=user_id, status='published')

        # 关键词搜索
        if keyword:
            query = query.filter(ForumFloor.content.like(f'%{keyword}%'))

        # 分页查询（按创建时间倒序）
        pagination = query.order_by(ForumFloor.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # 获取帖子信息
        floors_data = []
        for floor in pagination.items:
            floor_dict = floor_to_dict(floor)

            # 获取帖子信息
            post = ForumPost.query.get(floor.post_id)
            if post:
                floor_dict['post_title'] = post.title
                floor_dict['post_status'] = post.status

            floors_data.append(floor_dict)

        # 格式化响应
        response_data = {
            'total': pagination.total,
            'page': pagination.page,
            'size': pagination.per_page,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'items': floors_data
        }

        return ResponseService.success(
            data=response_data,
            message='我的楼层列表查询成功'
        )

    except Exception as e:
        print(f"【我的楼层查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@user_bp.route('/replies', methods=['GET'])
@token_required
def get_my_replies(current_user):
    """获取当前用户发布的回复列表"""
    try:
        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        keyword = request.args.get('keyword', '').strip()

        # 构建查询
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        query = ForumReply.query.filter_by(author_user_id=user_id, status='published')

        # 关键词搜索
        if keyword:
            query = query.filter(ForumReply.content.like(f'%{keyword}%'))

        # 分页查询（按创建时间倒序）
        pagination = query.order_by(ForumReply.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # 获取楼层和帖子信息
        replies_data = []
        for reply in pagination.items:
            reply_dict = reply_to_dict(reply)

            # 获取楼层信息
            floor = ForumFloor.query.get(reply.floor_id)
            if floor:
                reply_dict['floor_number'] = floor.floor_number

                # 获取帖子信息
                post = ForumPost.query.get(floor.post_id)
                if post:
                    reply_dict['post_title'] = post.title
                    reply_dict['post_id'] = post.id

            replies_data.append(reply_dict)

        # 格式化响应
        response_data = {
            'total': pagination.total,
            'page': pagination.page,
            'size': pagination.per_page,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'items': replies_data
        }

        return ResponseService.success(
            data=response_data,
            message='我的回复列表查询成功'
        )

    except Exception as e:
        print(f"【我的回复查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@user_bp.route('/posts', methods=['POST'])
@token_required
def create_user_post(current_user):
    """创建论坛帖子"""
    try:
        data = request.get_json()

        # 验证必填字段
        if not data or not data.get('title', '').strip():
            return ResponseService.error('标题不能为空', status_code=400)
        if not data.get('content', '').strip():
            return ResponseService.error('内容不能为空', status_code=400)

        title = data['title'].strip()
        content = data['content'].strip()
        category = data.get('category', 'default').strip()
        status = data.get('status', 'published').strip()

        # 验证内容
        title_validation = validate_content(title, min_length=1, max_length=200)
        if not title_validation['valid']:
            return ResponseService.error(title_validation['message'], status_code=400)

        content_validation = validate_content(content, min_length=1, max_length=10000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        # 敏感词过滤
        filtered_title = sensitive_filter.filter_content(title)
        filtered_content = sensitive_filter.filter_content(content)

        # 创建帖子
        post = ForumPost(
            title=filtered_title,
            content=filtered_content,
            category=category,
            status=status,
            author_user_id=current_user.id if hasattr(current_user, 'is_deleted') else current_user.id,
            author_display=current_user.username
        )

        post.update_author_display()
        db.session.add(post)
        db.session.commit()

        print(f"【用户发帖成功】帖子ID: {post.id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=post_to_dict(post),
            message='帖子创建成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【用户发帖异常】错误: {str(e)}")
        return ResponseService.error(f'帖子创建失败: {str(e)}', status_code=500)


@user_bp.route('/posts/<int:post_id>', methods=['PUT'])
@token_required
def update_my_post(current_user, post_id):
    """更新当前用户的帖子"""
    try:
        post = ForumPost.query.get(post_id)

        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        # 检查权限
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        if post.author_user_id != user_id:
            return ResponseService.error('无权限修改此帖子', status_code=403)

        data = request.get_json()

        # 更新字段
        if 'title' in data:
            title = data['title'].strip()
            title_validation = validate_content(title, min_length=1, max_length=200)
            if not title_validation['valid']:
                return ResponseService.error(title_validation['message'], status_code=400)
            post.title = sensitive_filter.filter_content(title)

        if 'content' in data:
            content = data['content'].strip()
            content_validation = validate_content(content, min_length=1, max_length=10000)
            if not content_validation['valid']:
                return ResponseService.error(content_validation['message'], status_code=400)
            post.content = sensitive_filter.filter_content(content)

        if 'category' in data:
            post.category = data['category'].strip()

        if 'status' in data and data['status'] in ['published', 'draft']:
            post.status = data['status'].strip()

        post.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【用户帖子更新成功】帖子ID: {post_id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=post_to_dict(post),
            message='帖子更新成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【用户帖子更新异常】错误: {str(e)}")
        return ResponseService.error(f'帖子更新失败: {str(e)}', status_code=500)


@user_bp.route('/floors/<int:floor_id>', methods=['PUT'])
@token_required
def update_my_floor(current_user, floor_id):
    """更新当前用户的楼层"""
    try:
        floor = ForumFloor.query.get(floor_id)

        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        # 检查权限
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        if floor.author_user_id != user_id:
            return ResponseService.error('无权限修改此楼层', status_code=403)

        data = request.get_json()
        content = data.get('content', '').strip()

        if not content:
            return ResponseService.error('回复内容不能为空', status_code=400)

        # 验证内容
        content_validation = validate_content(content, min_length=1, max_length=5000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        # 敏感词过滤
        filtered_content = sensitive_filter.filter_content(content)

        # 更新楼层
        floor.content = filtered_content
        floor.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【用户楼层更新成功】楼层ID: {floor_id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=floor_to_dict(floor),
            message='楼层更新成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【用户楼层更新异常】错误: {str(e)}")
        return ResponseService.error(f'楼层更新失败: {str(e)}', status_code=500)


@user_bp.route('/replies/<int:reply_id>', methods=['PUT'])
@token_required
def update_my_reply(current_user, reply_id):
    """更新当前用户的回复"""
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        # 检查权限
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        if reply.author_user_id != user_id:
            return ResponseService.error('无权限修改此回复', status_code=403)

        data = request.get_json()
        content = data.get('content', '').strip()

        if not content:
            return ResponseService.error('回复内容不能为空', status_code=400)

        # 验证内容
        content_validation = validate_content(content, min_length=1, max_length=2000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        # 敏感词过滤
        filtered_content = sensitive_filter.filter_content(content)

        # 更新回复
        reply.content = filtered_content
        reply.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【用户回复更新成功】回复ID: {reply_id}, 作者: {current_user.account}")

        return ResponseService.success(
            data=reply_to_dict(reply),
            message='回复更新成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【用户回复更新异常】错误: {str(e)}")
        return ResponseService.error(f'回复更新失败: {str(e)}', status_code=500)


@user_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@token_required
def delete_my_post(current_user, post_id):
    """删除当前用户的帖子"""
    try:
        post = ForumPost.query.get(post_id)

        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        # 检查权限
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        if post.author_user_id != user_id:
            return ResponseService.error('无权限删除此帖子', status_code=403)

        # 软删除
        post.status = 'deleted'
        post.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【用户帖子删除成功】帖子ID: {post_id}, 作者: {current_user.account}")

        return ResponseService.success(message='帖子删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【用户帖子删除异常】错误: {str(e)}")
        return ResponseService.error(f'帖子删除失败: {str(e)}', status_code=500)


@user_bp.route('/floors/<int:floor_id>', methods=['DELETE'])
@token_required
def delete_my_floor(current_user, floor_id):
    """删除当前用户的楼层"""
    try:
        floor = ForumFloor.query.get(floor_id)

        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        # 检查权限
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        if floor.author_user_id != user_id:
            return ResponseService.error('无权限删除此楼层', status_code=403)

        # 删除楼层
        floor.delete_floor()

        print(f"【用户楼层删除成功】楼层ID: {floor_id}, 作者: {current_user.account}")

        return ResponseService.success(message='楼层删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【用户楼层删除异常】错误: {str(e)}")
        return ResponseService.error(f'楼层删除失败: {str(e)}', status_code=500)


@user_bp.route('/replies/<int:reply_id>', methods=['DELETE'])
@token_required
def delete_my_reply(current_user, reply_id):
    """删除当前用户的回复"""
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        # 检查权限
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        if reply.author_user_id != user_id:
            return ResponseService.error('无权限删除此回复', status_code=403)

        # 删除回复
        reply.delete_reply()

        print(f"【用户回复删除成功】回复ID: {reply_id}, 作者: {current_user.account}")

        return ResponseService.success(message='回复删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【用户回复删除异常】错误: {str(e)}")
        return ResponseService.error(f'回复删除失败: {str(e)}', status_code=500)


@user_bp.route('/likes', methods=['GET'])
@token_required
def get_my_likes(current_user):
    """获取当前用户的点赞列表"""
    try:
        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        target_type = request.args.get('type', '').strip()  # post, floor, reply

        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id
        query = ForumLike.query.filter_by(user_id=user_id)

        # 按目标类型筛选
        if target_type:
            query = query.filter_by(target_type=target_type)

        # 分页查询
        pagination = query.order_by(ForumLike.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # 获取详细信息
        likes_data = []
        for like in pagination.items:
            like_dict = {
                'id': like.id,
                'target_type': like.target_type,
                'target_id': like.target_id,
                'created_at': like.created_at.isoformat() if like.created_at else None
            }

            # 根据目标类型获取详细信息
            if like.target_type == 'post' and like.post_id:
                post = ForumPost.query.get(like.post_id)
                if post:
                    like_dict['target_info'] = {
                        'title': post.title,
                        'content': post.content[:100] + '...' if len(post.content) > 100 else post.content,
                        'author_display': post.author_display
                    }
            elif like.target_type == 'floor' and like.floor_id:
                floor = ForumFloor.query.get(like.floor_id)
                if floor:
                    post = ForumPost.query.get(floor.post_id)
                    like_dict['target_info'] = {
                        'content': floor.content[:100] + '...' if len(floor.content) > 100 else floor.content,
                        'floor_number': floor.floor_number,
                        'post_title': post.title if post else '帖子已删除',
                        'author_display': floor.author_display
                    }
            elif like.target_type == 'reply' and like.reply_id:
                reply = ForumReply.query.get(like.reply_id)
                if reply:
                    floor = ForumFloor.query.get(reply.floor_id)
                    post = ForumPost.query.get(floor.post_id) if floor else None
                    like_dict['target_info'] = {
                        'content': reply.content[:100] + '...' if len(reply.content) > 100 else reply.content,
                        'post_title': post.title if post else '帖子已删除',
                        'author_display': reply.author_display
                    }

            likes_data.append(like_dict)

        # 格式化响应
        response_data = {
            'total': pagination.total,
            'page': pagination.page,
            'size': pagination.per_page,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'items': likes_data
        }

        return ResponseService.success(
            data=response_data,
            message='我的点赞列表查询成功'
        )

    except Exception as e:
        print(f"【我的点赞查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@user_bp.route('/stats', methods=['GET'])
@token_required
def get_my_stats(current_user):
    """获取当前用户的论坛统计信息"""
    try:
        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id

        # 获取基础统计
        basic_stats = {
            'posts_count': ForumPost.query.filter_by(author_user_id=user_id).count(),
            'floors_count': ForumFloor.query.filter_by(author_user_id=user_id).count(),
            'replies_count': ForumReply.query.filter_by(author_user_id=user_id).count(),
            'likes_given': ForumLike.query.filter_by(user_id=user_id).count()
        }

        # 获取收到的点赞数
        likes_received = 0
        likes_received += db.session.query(db.func.sum(ForumPost.like_count)).filter_by(author_user_id=user_id).scalar() or 0
        likes_received += db.session.query(db.func.sum(ForumFloor.like_count)).filter_by(author_user_id=user_id).scalar() or 0
        likes_received += db.session.query(db.func.sum(ForumReply.like_count)).filter_by(author_user_id=user_id).scalar() or 0

        basic_stats['likes_received'] = int(likes_received)

        # 获取最近30天的参与统计
        recent_stats = ForumStatsHelper.get_user_participation_stats(user_id, days=30)

        # 获取最近的帖子
        recent_posts = ForumPost.query.filter_by(author_user_id=user_id).order_by(
            ForumPost.created_at.desc()
        ).limit(5).all()

        recent_posts_data = [post_to_dict(post, include_content=False) for post in recent_posts]

        stats_data = {
            'basic_stats': basic_stats,
            'recent_stats': recent_stats,
            'recent_posts': recent_posts_data
        }

        return ResponseService.success(
            data=stats_data,
            message='用户统计信息查询成功'
        )

    except Exception as e:
        print(f"【用户统计查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@user_bp.route('/visits', methods=['GET'])
@token_required
def get_my_visits(current_user):
    """获取当前用户的浏览记录"""
    try:
        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id

        # 查询浏览记录
        pagination = ForumVisit.query.filter_by(user_id=user_id).order_by(
            ForumVisit.last_visit_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        # 获取帖子信息
        visits_data = []
        for visit in pagination.items:
            post = ForumPost.query.get(visit.post_id)
            if post:
                visit_dict = {
                    'id': visit.id,
                    'post_id': post.id,
                    'post_title': post.title,
                    'post_category': post.category,
                    'first_visit_at': visit.first_visit_at.isoformat() if visit.first_visit_at else None,
                    'last_visit_at': visit.last_visit_at.isoformat() if visit.last_visit_at else None,
                    'visit_count': visit.visit_count
                }
                visits_data.append(visit_dict)

        # 格式化响应
        response_data = {
            'total': pagination.total,
            'page': pagination.page,
            'size': pagination.per_page,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'items': visits_data
        }

        return ResponseService.success(
            data=response_data,
            message='浏览记录查询成功'
        )

    except Exception as e:
        print(f"【浏览记录查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# ============================================================================
# 第八部分: 管理员路由 (来自 admin/forum_manage.py)
# ============================================================================

def check_admin_permission(user):
    """检查管理员权限"""
    if not hasattr(user, 'role'):
        return False
    return user.role in ['ADMIN', 'SUPER_ADMIN']


@admin_bp.before_request
@token_required
def admin_permission_check(current_user):
    """管理员权限检查"""
    if not check_admin_permission(current_user):
        return ResponseService.error('需要管理员权限', status_code=403)


@admin_bp.route('/posts', methods=['GET'])
def get_all_posts():
    """获取所有帖子（管理员视角）"""
    try:
        # 获取查询参数
        category = request.args.get('category', '').strip()
        status = request.args.get('status', '').strip()
        keyword = request.args.get('keyword', '').strip()
        author_id = request.args.get('author_id', '').strip()
        sort_by = request.args.get('sort', 'latest').strip()
        include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'

        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        # 构建查询
        query = ForumPost.query

        # 应用筛选条件
        if category:
            query = query.filter(ForumPost.category == category)
        if status:
            query = query.filter(ForumPost.status == status)
        elif not include_deleted:
            query = query.filter(ForumPost.status != 'deleted')
        if keyword:
            query = query.filter(
                (ForumPost.title.like(f'%{keyword}%')) |
                (ForumPost.content.like(f'%{keyword}%'))
            )
        if author_id:
            query = query.filter(ForumPost.author_user_id == int(author_id))

        # 执行查询
        posts = query.all()

        # 排序
        sorted_posts = post_sorter.sort_posts(posts, sort_by)

        # 手动分页
        start = (page - 1) * per_page
        end = start + per_page
        paginated_posts = sorted_posts[start:end]
        total = len(sorted_posts)

        # 格式化响应
        posts_data = [post_to_dict(post, include_content=False, include_user_info=True) for post in paginated_posts]

        response_data = {
            'total': total,
            'page': page,
            'size': per_page,
            'pages': (total + per_page - 1) // per_page,
            'has_prev': page > 1,
            'has_next': end < total,
            'items': posts_data
        }

        return ResponseService.success(
            data=response_data,
            message='帖子列表查询成功' if total > 0 else '无匹配数据'
        )

    except Exception as e:
        print(f"【管理员帖子查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@admin_bp.route('/posts/<int:post_id>', methods=['GET'])
def get_post_detail_admin(post_id):
    """获取帖子详情（管理员视角）"""
    try:
        post = ForumPost.query.get(post_id)

        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        return ResponseService.success(
            data=post_to_dict(post, include_content=True, include_user_info=True),
            message='帖子详情查询成功'
        )

    except Exception as e:
        print(f"【管理员帖子详情查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@admin_bp.route('/posts/<int:post_id>/status', methods=['PUT'])
def update_post_status(post_id):
    """更新帖子状态（审核、置顶等）"""
    try:
        post = ForumPost.query.get(post_id)

        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        data = request.get_json()
        status = data.get('status', '').strip()

        if not status or status not in ['published', 'draft', 'deleted']:
            return ResponseService.error('无效的状态值', status_code=400)

        # 更新状态
        old_status = post.status
        post.status = status
        post.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【管理员更新帖子状态】帖子ID: {post_id}, 状态: {old_status} -> {status}")

        return ResponseService.success(
            data={'old_status': old_status, 'new_status': status},
            message='帖子状态更新成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【管理员帖子状态更新异常】错误: {str(e)}")
        return ResponseService.error(f'状态更新失败: {str(e)}', status_code=500)


@admin_bp.route('/posts/<int:post_id>/pin', methods=['PUT'])
def pin_post(post_id):
    """置顶/取消置顶帖子"""
    try:
        post = ForumPost.query.get(post_id)

        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        data = request.get_json()
        is_pinned = data.get('is_pinned', False)

        # 这里需要数据库字段支持置顶功能，目前通过更新时间模拟
        if is_pinned:
            # 置顶：将更新时间设为很早的时间，确保排在前面
            post.updated_at = datetime.now() - timedelta(days=365)
            message = '帖子置顶成功'
        else:
            # 取消置顶：恢复正常更新时间
            post.updated_at = datetime.utcnow()
            message = '取消置顶成功'

        db.session.commit()

        print(f"【管理员置顶操作】帖子ID: {post_id}, 置顶: {is_pinned}")

        return ResponseService.success(
            data={'is_pinned': is_pinned, 'updated_at': post.updated_at.isoformat()},
            message=message
        )

    except Exception as e:
        db.session.rollback()
        print(f"【管理员置顶操作异常】错误: {str(e)}")
        return ResponseService.error(f'操作失败: {str(e)}', status_code=500)


@admin_bp.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post_admin(post_id):
    """删除帖子（管理员硬删除）"""
    try:
        post = ForumPost.query.get(post_id)

        if not post:
            return ResponseService.error('帖子不存在', status_code=404)

        # 硬删除帖子及其关联数据
        db.session.delete(post)
        db.session.commit()

        print(f"【管理员删除帖子】帖子ID: {post_id}")

        return ResponseService.success(message='帖子删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【管理员删除帖子异常】错误: {str(e)}")
        return ResponseService.error(f'删除失败: {str(e)}', status_code=500)


@admin_bp.route('/floors', methods=['GET'])
def get_all_floors():
    """获取所有楼层（管理员视角）"""
    try:
        # 获取查询参数
        post_id = request.args.get('post_id', '').strip()
        status = request.args.get('status', '').strip()
        keyword = request.args.get('keyword', '').strip()
        author_id = request.args.get('author_id', '').strip()

        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        # 构建查询
        query = ForumFloor.query

        if post_id:
            query = query.filter(ForumFloor.post_id == int(post_id))
        if status:
            query = query.filter(ForumFloor.status == status)
        if keyword:
            query = query.filter(ForumFloor.content.like(f'%{keyword}%'))
        if author_id:
            query = query.filter(ForumFloor.author_user_id == int(author_id))

        # 分页查询
        pagination = query.order_by(ForumFloor.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # 格式化响应
        response_data = PaginationHelper.format_pagination_response(
            pagination,
            pagination.items,
            lambda floor: floor_to_dict(floor, include_user_info=True)
        )

        return ResponseService.success(
            data=response_data,
            message='楼层列表查询成功' if pagination.total > 0 else '无匹配数据'
        )

    except Exception as e:
        print(f"【管理员楼层查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@admin_bp.route('/floors/<int:floor_id>', methods=['DELETE'])
def delete_floor_admin(floor_id):
    """删除楼层（管理员硬删除）"""
    try:
        floor = ForumFloor.query.get(floor_id)

        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        # 硬删除楼层及其关联数据
        db.session.delete(floor)
        db.session.commit()

        print(f"【管理员删除楼层】楼层ID: {floor_id}")

        return ResponseService.success(message='楼层删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【管理员删除楼层异常】错误: {str(e)}")
        return ResponseService.error(f'删除失败: {str(e)}', status_code=500)


@admin_bp.route('/replies', methods=['GET'])
def get_all_replies():
    """获取所有回复（管理员视角）"""
    try:
        # 获取查询参数
        floor_id = request.args.get('floor_id', '').strip()
        status = request.args.get('status', '').strip()
        keyword = request.args.get('keyword', '').strip()
        author_id = request.args.get('author_id', '').strip()

        # 获取分页参数
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        # 构建查询
        query = ForumReply.query

        if floor_id:
            query = query.filter(ForumReply.floor_id == int(floor_id))
        if status:
            query = query.filter(ForumReply.status == status)
        if keyword:
            query = query.filter(ForumReply.content.like(f'%{keyword}%'))
        if author_id:
            query = query.filter(ForumReply.author_user_id == int(author_id))

        # 分页查询
        pagination = query.order_by(ForumReply.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # 格式化响应
        response_data = PaginationHelper.format_pagination_response(
            pagination,
            pagination.items,
            lambda reply: reply_to_dict(reply, include_user_info=True)
        )

        return ResponseService.success(
            data=response_data,
            message='回复列表查询成功' if pagination.total > 0 else '无匹配数据'
        )

    except Exception as e:
        print(f"【管理员回复查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@admin_bp.route('/replies/<int:reply_id>', methods=['DELETE'])
def delete_reply_admin(reply_id):
    """删除回复（管理员硬删除）"""
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        # 硬删除回复
        db.session.delete(reply)
        db.session.commit()

        print(f"【管理员删除回复】回复ID: {reply_id}")

        return ResponseService.success(message='回复删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【管理员删除回复异常】错误: {str(e)}")
        return ResponseService.error(f'删除失败: {str(e)}', status_code=500)


@admin_bp.route('/stats', methods=['GET'])
def get_forum_stats():
    """获取论坛统计信息（管理员视角）"""
    try:
        days = int(request.args.get('days', 7))

        # 获取基础统计
        stats = ForumStatsHelper.get_post_stats(days)

        # 添加更详细的统计信息
        total_users = User.query.filter_by(is_deleted=0).count()
        active_users = User.query.filter(
            User.is_deleted == 0,
            User.last_login >= datetime.now() - timedelta(days=days)
        ).count()

        # 内容统计
        total_floors = ForumFloor.query.count()
        total_replies = ForumReply.query.count()
        total_likes = ForumLike.query.count()
        total_visits = ForumVisit.query.count()

        # 时间范围内的统计
        time_threshold = datetime.now() - timedelta(days=days)
        recent_posts = ForumPost.query.filter(ForumPost.created_at >= time_threshold).count()
        recent_floors = ForumFloor.query.filter(ForumFloor.created_at >= time_threshold).count()
        recent_replies = ForumReply.query.filter(ForumReply.created_at >= time_threshold).count()

        stats_data = {
            'basic_stats': stats,
            'user_stats': {
                'total_users': total_users,
                'active_users': active_users,
                'new_users': User.query.filter(User.created_at >= time_threshold).count()
            },
            'content_stats': {
                'total_posts': stats['total'],
                'total_floors': total_floors,
                'total_replies': total_replies,
                'total_likes': total_likes,
                'total_visits': total_visits
            },
            'recent_activity': {
                'posts': recent_posts,
                'floors': recent_floors,
                'replies': recent_replies,
                'likes': ForumLike.query.filter(ForumLike.created_at >= time_threshold).count()
            }
        }

        return ResponseService.success(
            data=stats_data,
            message='论坛统计信息查询成功'
        )

    except Exception as e:
        print(f"【论坛统计查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@admin_bp.route('/categories/manage', methods=['GET'])
def get_categories_stats():
    """获取分类统计信息"""
    try:
        # 获取所有分类及其统计
        categories_stats = db.session.query(
            ForumPost.category,
            db.func.count(ForumPost.id).label('posts_count'),
            db.func.sum(ForumPost.view_count).label('total_views'),
            db.func.sum(ForumPost.like_count).label('total_likes')
        ).filter(
            ForumPost.category.isnot(None),
            ForumPost.category != ''
        ).group_by(ForumPost.category).all()

        categories_data = []
        for stat in categories_stats:
            category_data = {
                'name': stat.category,
                'posts_count': stat.posts_count,
                'total_views': stat.total_views or 0,
                'total_likes': stat.total_likes or 0,
                'avg_views_per_post': (stat.total_views or 0) / stat.posts_count if stat.posts_count > 0 else 0
            }
            categories_data.append(category_data)

        return ResponseService.success(
            data=categories_data,
            message='分类统计信息查询成功'
        )

    except Exception as e:
        print(f"【分类统计查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@admin_bp.route('/sensitive-words', methods=['GET'])
def get_sensitive_words():
    """获取敏感词列表"""
    try:
        # 返回当前敏感词列表（实际项目中可能需要权限控制）
        return ResponseService.success(
            data={
                'sensitive_words': sensitive_filter.sensitive_words,
                'count': len(sensitive_filter.sensitive_words)
            },
            message='敏感词列表查询成功'
        )

    except Exception as e:
        print(f"【敏感词查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@admin_bp.route('/sensitive-words', methods=['POST'])
def add_sensitive_words():
    """添加敏感词"""
    try:
        data = request.get_json()
        words = data.get('words', [])

        if not isinstance(words, list) or not words:
            return ResponseService.error('敏感词列表不能为空', status_code=400)

        # 添加新敏感词
        added_words = []
        for word in words:
            word = word.strip()
            if word and word not in sensitive_filter.sensitive_words:
                sensitive_filter.sensitive_words.append(word)
                added_words.append(word)

        # 重新编译正则表达式
        sensitive_filter.pattern = re.compile(
            '|'.join(map(re.escape, sensitive_filter.sensitive_words)),
            re.IGNORECASE
        )

        print(f"【管理员添加敏感词】添加数量: {len(added_words)}")

        return ResponseService.success(
            data={'added_words': added_words, 'total_count': len(sensitive_filter.sensitive_words)},
            message=f'成功添加 {len(added_words)} 个敏感词'
        )

    except Exception as e:
        print(f"【添加敏感词异常】错误: {str(e)}")
        return ResponseService.error(f'添加失败: {str(e)}', status_code=500)


@admin_bp.route('/bulk-operation', methods=['POST'])
def bulk_operation():
    """批量操作（批量删除、状态修改等）"""
    try:
        data = request.get_json()
        operation = data.get('operation', '').strip()
        target_type = data.get('target_type', '').strip()  # post, floor, reply
        target_ids = data.get('target_ids', [])

        if not operation or not target_type or not target_ids:
            return ResponseService.error('参数不完整', status_code=400)

        if not isinstance(target_ids, list) or not target_ids:
            return ResponseService.error('目标ID列表不能为空', status_code=400)

        success_count = 0
        error_count = 0

        if target_type == 'post':
            for post_id in target_ids:
                try:
                    post = ForumPost.query.get(int(post_id))
                    if post:
                        if operation == 'delete':
                            db.session.delete(post)
                        elif operation in ['published', 'draft', 'deleted']:
                            post.status = operation
                            post.updated_at = datetime.utcnow()
                        success_count += 1
                    else:
                        error_count += 1
                except Exception:
                    error_count += 1

        elif target_type == 'floor':
            for floor_id in target_ids:
                try:
                    floor = ForumFloor.query.get(int(floor_id))
                    if floor:
                        if operation == 'delete':
                            db.session.delete(floor)
                        elif operation in ['published', 'deleted']:
                            floor.status = operation
                            floor.updated_at = datetime.utcnow()
                        success_count += 1
                    else:
                        error_count += 1
                except Exception:
                    error_count += 1

        elif target_type == 'reply':
            for reply_id in target_ids:
                try:
                    reply = ForumReply.query.get(int(reply_id))
                    if reply:
                        if operation == 'delete':
                            db.session.delete(reply)
                        elif operation in ['published', 'deleted']:
                            reply.status = operation
                            reply.updated_at = datetime.utcnow()
                        success_count += 1
                    else:
                        error_count += 1
                except Exception:
                    error_count += 1

        else:
            return ResponseService.error('不支持的目标类型', status_code=400)

        db.session.commit()

        print(f"【管理员批量操作】操作: {operation}, 类型: {target_type}, 成功: {success_count}, 失败: {error_count}")

        return ResponseService.success(
            data={
                'operation': operation,
                'target_type': target_type,
                'success_count': success_count,
                'error_count': error_count,
                'total_count': len(target_ids)
            },
            message=f'批量操作完成：成功 {success_count} 个，失败 {error_count} 个'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【批量操作异常】错误: {str(e)}")
        return ResponseService.error(f'批量操作失败: {str(e)}', status_code=500)


# ============================================================================
# 第九部分: 公开访问路由 (来自 post/public.py)
# ============================================================================

# 公开的论坛帖子列表查询（无需登录）
@bp_forum_public.route('/posts', methods=['GET'])
def get_public_forum_posts():
    """
    获取公开发布的论坛帖子列表（无需登录）
    """
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        category = request.args.get('category', '').strip()
        keyword = request.args.get('keyword', '').strip()

        # 构建查询
        query = ForumPost.query.filter_by(status='published')

        # 分类筛选
        if category:
            query = query.filter(ForumPost.category == category)

        # 关键词搜索
        if keyword:
            query = query.filter(
                (ForumPost.title.like(f'%{keyword}%')) |
                (ForumPost.content.like(f'%{keyword}%'))
            )

        # 分页查询
        pagination = query.order_by(ForumPost.created_at.desc()).paginate(page=page, per_page=size)
        posts = pagination.items
        total = pagination.total

        result_list = []
        for post in posts:
            # 获取作者基础信息
            author_info = {}
            if post.author_user_id:
                author = User.query.filter_by(id=post.author_user_id, is_deleted=0).first()
                if author:
                    author_info = {
                        'username': author.username,
                        'avatar': author.avatar,
                        'role_cn': '普通用户'
                    }

            item = {
                'id': post.id,
                'title': post.title,
                'category': post.category,
                'summary': post.content[:200] + '...' if len(post.content) > 200 else post.content,
                'view_count': post.view_count or 0,
                'like_count': post.calculate_like_count(),
                'comment_count': post.calculate_comment_count(),
                'author_display': post.author_display,
                'author_info': author_info,
                'created_at': post.created_at.isoformat().replace('+00:00', 'Z'),
                'updated_at': post.updated_at.isoformat().replace('+00:00', 'Z')
            }
            result_list.append(item)

        return ResponseService.paginated_success(
            items=result_list,
            total=total,
            page=page,
            size=size,
            message="论坛帖子列表查询成功"
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 公开的论坛帖子详情查询（无需登录）
@bp_forum_public.route('/posts/<int:post_id>', methods=['GET'])
def get_public_forum_post_detail(post_id):
    """
    获取公开发布的论坛帖子详情（无需登录）
    """
    try:
        post = ForumPost.query.filter_by(id=post_id, status='published').first()
        if not post:
            return ResponseService.error('帖子不存在或未发布', status_code=404)

        # 增加浏览次数
        post.view_count = (post.view_count or 0) + 1
        db.session.commit()

        # 获取作者信息
        author_info = {}
        if post.author_user_id:
            author = User.query.filter_by(id=post.author_user_id, is_deleted=0).first()
            if author:
                author_info = {
                    'id': author.id,
                    'username': author.username,
                    'avatar': author.avatar,
                    'role_cn': '普通用户'
                }

        # 返回完整信息
        item = {
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'category': post.category,
            'view_count': post.view_count or 0,
            'like_count': post.calculate_like_count(),
            'comment_count': post.calculate_comment_count(),
            'author_display': post.author_display,
            'author_info': author_info,
            'created_at': post.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': post.updated_at.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=item, message="论坛帖子详情查询成功")

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 公开的论坛帖子楼层查询（无需登录）
@bp_forum_public.route('/posts/<int:post_id>/floors', methods=['GET'])
def get_public_forum_floors(post_id):
    """
    获取论坛帖子的楼层列表（无需登录）
    """
    try:
        # 验证帖子存在且已发布
        post = ForumPost.query.filter_by(id=post_id, status='published').first()
        if not post:
            return ResponseService.error('帖子不存在或未发布', status_code=404)

        # 获取分页参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))

        # 查询楼层
        pagination = ForumFloor.query.filter_by(
            post_id=post_id,
            status='published'
        ).order_by(ForumFloor.floor_number.asc()).paginate(page=page, per_page=size)

        floors = pagination.items
        total = pagination.total

        floors_data = []
        for floor in floors:
            # 获取楼层作者信息
            author_info = {}
            if floor.author_user_id:
                author = User.query.filter_by(id=floor.author_user_id, is_deleted=0).first()
                if author:
                    author_info = {
                        'username': author.username,
                        'avatar': author.avatar,
                        'role_cn': '普通用户'
                    }

            floor_data = {
                'id': floor.id,
                'floor_number': floor.floor_number,
                'content': floor.content,
                'like_count': floor.calculate_like_count(),
                'reply_count': floor.calculate_reply_count(),
                'author_display': floor.author_display,
                'author_info': author_info,
                'created_at': floor.created_at.isoformat().replace('+00:00', 'Z')
            }
            floors_data.append(floor_data)

        return ResponseService.paginated_success(
            items=floors_data,
            total=total,
            page=page,
            size=size,
            message="楼层列表查询成功"
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


# 公开的论坛帖子分类统计（无需登录）
@bp_forum_public.route('/categories', methods=['GET'])
def get_public_forum_categories():
    """
    获取论坛帖子分类统计（无需登录）
    """
    try:
        from sqlalchemy import func

        # 获取各分类统计
        category_stats = db.session.query(
            ForumPost.category,
            func.count(ForumPost.id).label('post_count'),
            func.sum(ForumPost.view_count).label('total_views'),
            func.sum(ForumPost.like_count).label('total_likes')
        ).filter(
            ForumPost.category.isnot(None),
            ForumPost.category != '',
            ForumPost.status == 'published'
        ).group_by(ForumPost.category).all()

        categories_data = []
        for stat in category_stats:
            category_data = {
                'name': stat.category,
                'post_count': stat.post_count or 0,
                'total_views': stat.total_views or 0,
                'total_likes': stat.total_likes or 0,
                'avg_views_per_post': round((stat.total_views or 0) / stat.post_count, 2) if stat.post_count > 0 else 0
            }
            categories_data.append(category_data)

        return ResponseService.success(data=categories_data, message="分类统计查询成功")

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)


print("【API_forum 统一路由模块加载完成】")
