# API_forum 管理员论坛管理模块

from flask import request, jsonify
from datetime import datetime, timedelta
from components import token_required, db
from components.models.forum_models import (
    ForumPost, ForumFloor, ForumReply, ForumLike, ForumVisit
)
from components.models.user_models import User
from components.response_service import ResponseService
from . import admin_bp
from ..common.utils import (
    sensitive_filter, PaginationHelper, validate_content,
    ForumStatsHelper, post_sorter
)


def check_admin_permission(user):
    """检查管理员权限"""
    if not hasattr(user, 'role'):
        return False
    return user.role in ['ADMIN', 'SUPER_ADMIN']


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
        'author_user_id': post.author_user_id,
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

    return result


def floor_to_dict(floor, include_user_info=False):
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
        'author_user_id': floor.author_user_id,
        'created_at': floor.created_at.isoformat() if floor.created_at else None,
        'updated_at': floor.updated_at.isoformat() if floor.updated_at else None
    }

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
        'author_user_id': reply.author_user_id,
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

    return result


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

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='帖子列表查询成功' if total > 0 else '无匹配数据',
            extra_fields=extra_fields
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

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='楼层列表查询成功' if pagination.total > 0 else '无匹配数据',
            extra_fields=extra_fields
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

        extra_fields = {key: value for key, value in response_data.items() if key not in {'total', 'page', 'size', 'items'}}
        return ResponseService.paginated_success(
            items=response_data['items'],
            total=response_data['total'],
            page=response_data['page'],
            size=response_data['size'],
            message='回复列表查询成功' if pagination.total > 0 else '无匹配数据',
            extra_fields=extra_fields
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
        from ..common.utils import sensitive_filter

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
        from ..common.utils import sensitive_filter

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
        sensitive_filter.pattern = __import__('re').compile(
            '|'.join(map(__import__('re').escape, sensitive_filter.sensitive_words)),
            __import__('re').IGNORECASE
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
