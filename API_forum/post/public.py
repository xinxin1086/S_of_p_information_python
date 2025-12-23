# 论坛帖子公开访问接口

from flask import Blueprint, request
from components import db
from components.models import ForumPost, ForumFloor, ForumReply
from components.response_service import ResponseService
from components.models import User
from datetime import datetime

# 创建论坛公开访问模块蓝图
bp_forum_public = Blueprint('forum_public', __name__, url_prefix='/api/public/forum')

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

print("【API_forum 公开访问接口模块加载完成】")