# API_forum 楼层路由模块

from flask import request, jsonify
from datetime import datetime
from components import token_required, db
from components.models.forum_models import ForumPost, ForumFloor, ForumReply
from components.response_service import ResponseService
from . import floor_bp
from ..common.utils import (
    sensitive_filter, PaginationHelper, PermissionHelper,
    validate_content, create_nested_reply_structure
)


def floor_to_dict(floor, include_replies=False, replies_limit=3):
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

    return result


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

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='楼层列表查询成功' if pagination.total > 0 else '暂无楼层',
            extra_fields=extra_fields
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
        from components.models.forum_models import ForumLike

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
        from components.models.forum_models import ForumLike

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

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='用户楼层列表查询成功' if pagination.total > 0 else '暂无楼层',
            extra_fields=extra_fields
        )

    except Exception as e:
        print(f"【用户楼层查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)
