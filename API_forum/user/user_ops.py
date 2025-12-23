# API_forum 用户操作模块

from flask import request, jsonify
from datetime import datetime, timedelta
from components import token_required, db
from components.models.forum_models import ForumPost, ForumFloor, ForumReply, ForumLike, ForumVisit
from components.response_service import ResponseService
from . import user_bp
from ..common.utils import (
    sensitive_filter, PaginationHelper, validate_content,
    ForumStatsHelper
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


def floor_to_dict(floor):
    """将楼层对象转换为字典"""
    return {
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


def reply_to_dict(reply):
    """将回复对象转换为字典"""
    return {
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
            lambda post: post_to_dict(post)
        )

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='我的帖子列表查询成功',
            extra_fields=extra_fields
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

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='我的楼层列表查询成功',
            extra_fields=extra_fields
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

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='我的回复列表查询成功',
            extra_fields=extra_fields
        )

    except Exception as e:
        print(f"【我的回复查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@user_bp.route('/posts', methods=['POST'])
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

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='我的点赞列表查询成功',
            extra_fields=extra_fields
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

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='浏览记录查询成功',
            extra_fields=extra_fields
        )

    except Exception as e:
        print(f"【浏览记录查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)
