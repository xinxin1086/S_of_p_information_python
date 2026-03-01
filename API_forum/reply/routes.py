
from flask import request, jsonify
from datetime import datetime
from components import token_required, db
from components.models.forum_models import ForumPost, ForumFloor, ForumReply
from components.response_service import ResponseService
from . import reply_bp
from ..common.utils import (
    sensitive_filter, PaginationHelper, PermissionHelper,
    validate_content, create_nested_reply_structure
)


def reply_to_dict(reply):
    
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


@reply_bp.route('/floor/<int:floor_id>', methods=['GET'])
def get_replies_by_floor(floor_id):
    
    try:
        floor = ForumFloor.query.get(floor_id)
        if not floor:
            return ResponseService.error('楼层不存在', status_code=404)

        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        replies_pagination = ForumReply.get_replies_by_floor(floor_id, page, per_page)

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
    
    try:
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

        content_validation = validate_content(content, min_length=1, max_length=2000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        if quote_content:
            quote_validation = validate_content(quote_content, min_length=1, max_length=500)
            if not quote_validation['valid']:
                return ResponseService.error(quote_validation['message'], status_code=400)

        filtered_content = sensitive_filter.filter_content(content)
        filtered_quote_content = sensitive_filter.filter_content(quote_content) if quote_content else None

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
    
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        if not PermissionHelper.can_edit_reply(current_user, reply):
            return ResponseService.error('无权限修改此回复', status_code=403)

        data = request.get_json()
        content = data.get('content', '').strip()

        if not content:
            return ResponseService.error('回复内容不能为空', status_code=400)

        content_validation = validate_content(content, min_length=1, max_length=2000)
        if not content_validation['valid']:
            return ResponseService.error(content_validation['message'], status_code=400)

        filtered_content = sensitive_filter.filter_content(content)

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
    
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        if not PermissionHelper.can_edit_reply(current_user, reply):
            return ResponseService.error('无权限删除此回复', status_code=403)

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
    
    try:
        from components.models.forum_models import ForumLike

        reply = ForumReply.query.get(reply_id)
        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id

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
    
    try:
        from components.models.forum_models import ForumLike

        user_id = current_user.id if hasattr(current_user, 'is_deleted') else current_user.id

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
    
    try:
        pagination_params = PaginationHelper.get_pagination_params()
        page = pagination_params['page']
        per_page = pagination_params['per_page']

        query = ForumReply.query.filter_by(
            author_user_id=user_id,
            status='published'
        ).order_by(ForumReply.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        replies_data = []
        for reply in pagination.items:
            reply_dict = reply_to_dict(reply)

            floor = ForumFloor.query.get(reply.floor_id)
            if floor:
                reply_dict['floor_number'] = floor.floor_number

                post = ForumPost.query.get(floor.post_id)
                if post:
                    reply_dict['post_title'] = post.title
                    reply_dict['post_id'] = post.id

            replies_data.append(reply_dict)

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
    
    try:
        limit = min(int(request.args.get('limit', 20)), 100)

        recent_replies = ForumReply.query.filter_by(
            status='published'
        ).order_by(ForumReply.created_at.desc()).limit(limit).all()

        replies_data = []
        for reply in recent_replies:
            reply_dict = reply_to_dict(reply)

            floor = ForumFloor.query.get(reply.floor_id)
            if floor:
                reply_dict['floor_number'] = floor.floor_number

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
    
    try:
        reply = ForumReply.query.get(reply_id)

        if not reply:
            return ResponseService.error('回复不存在', status_code=404)

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