# API_forum 帖子路由模块

from flask import request, jsonify
from datetime import datetime
from components import token_required, db
from components.models.forum_models import ForumPost, ForumVisit
from components.response_service import ResponseService
from . import post_bp
from ..common.utils import (
    sensitive_filter, post_sorter, PaginationHelper,
    PermissionHelper, validate_content
)


def post_to_dict(post, include_content=True):
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

    return result


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