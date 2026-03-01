
from flask import Blueprint, request
from components import db, token_required
from components.models import Activity, ActivityDiscuss, ActivityDiscussComment, User
from components.response_service import ResponseService
from datetime import datetime
from sqlalchemy import text

discussion_bp = Blueprint('discussion', __name__, url_prefix='/api/activities/discussion')


@discussion_bp.route('/activities/<int:activity_id>/discussions', methods=['POST'])
@token_required
def create_discussion(current_user, activity_id):
    
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        content = data.get('content', '').strip()
        image_urls = data.get('image_urls', [])

        if not content:
            return ResponseService.error('讨论内容不能为空', status_code=400)

        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        discussion = ActivityDiscuss(
            activity_id=activity_id,
            content=content,
            image_urls=image_urls if image_urls else None
        )
        discussion.set_author_info(current_user)

        db.session.add(discussion)
        db.session.commit()

        print(f"【讨论创建成功】讨论ID: {discussion.id}, 用户: {current_user.account}")

        discussion_data = {
            'id': discussion.id,
            'activity_id': discussion.activity_id,
            'content': discussion.content,
            'author_user_id': discussion.author_user_id,
            'author_display': discussion.author_display,
            'author_avatar': discussion.author_avatar,
            'image_urls': discussion.image_urls or [],
            'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=discussion_data, message='讨论发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论发表失败: {str(e)}', status_code=500)


@discussion_bp.route('/activities/<int:activity_id>/discussions', methods=['GET'])
def get_activity_discussions(activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        sort_by = request.args.get('sort_by', 'latest')

        query = ActivityDiscuss.query.filter_by(activity_id=activity_id)

        if sort_by == 'latest':
            query = query.order_by(ActivityDiscuss.create_time.desc())
        elif sort_by == 'latest_comment':
            query = query.order_by(ActivityDiscuss.update_time.desc())
        elif sort_by == 'hottest':
            query = query.order_by(text("(SELECT COUNT(*) FROM activity_discuss_comment WHERE discuss_id = activity_discuss.id) DESC"))

        pagination = query.paginate(page=page, per_page=size)
        discussions = pagination.items
        total = pagination.total

        discussions_list = []
        for discussion in discussions:
            comment_count = ActivityDiscussComment.query.filter_by(discuss_id=discussion.id).count()

            latest_comment = ActivityDiscussComment.query.filter_by(discuss_id=discussion.id).order_by(
                ActivityDiscussComment.create_time.desc()
            ).first()

            item = {
                'id': discussion.id,
                'activity_id': discussion.activity_id,
                'content': discussion.content,
                'author_display': discussion.author_display,
                'author_avatar': discussion.author_avatar,
                'image_urls': discussion.image_urls or [],
                'comment_count': comment_count,
                'latest_comment_time': latest_comment.create_time.isoformat().replace('+00:00', 'Z') if latest_comment else None,
                'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z'),
                'update_time': discussion.update_time.isoformat().replace('+00:00', 'Z')
            }
            discussions_list.append(item)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'sort_by': sort_by,
            'items': discussions_list
        }, message='讨论列表查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>', methods=['GET'])
def get_discussion_detail(discussion_id):
    
    try:
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        activity = Activity.query.get(discussion.activity_id)

        comments = ActivityDiscussComment.query.filter_by(discuss_id=discussion_id).order_by(
            ActivityDiscussComment.create_time.asc()
        ).all()

        comments_dict = {}
        root_comments = []

        for comment in comments:
            comment_data = {
                'id': comment.id,
                'discuss_id': comment.discuss_id,
                'content': comment.content,
                'author_display': comment.author_display,
                'author_avatar': comment.author_avatar,
                'parent_comment_id': comment.parent_comment_id,
                'create_time': comment.create_time.isoformat().replace('+00:00', 'Z'),
                'replies': []
            }
            comments_dict[comment.id] = comment_data

            if comment.parent_comment_id is None:
                root_comments.append(comment_data)
            else:
                if comment.parent_comment_id in comments_dict:
                    comments_dict[comment.parent_comment_id]['replies'].append(comment_data)

        discussion_data = {
            'id': discussion.id,
            'activity_id': discussion.activity_id,
            'activity_title': activity.title if activity else '活动已删除',
            'content': discussion.content,
            'author_display': discussion.author_display,
            'author_avatar': discussion.author_avatar,
            'image_urls': discussion.image_urls or [],
            'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z'),
            'update_time': discussion.update_time.isoformat().replace('+00:00', 'Z'),
            'comment_count': len(comments),
            'comments': root_comments
        }

        return ResponseService.success(data=discussion_data, message='讨论详情查询成功')

    except Exception as e:
        return ResponseService.error(f'讨论详情查询失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>', methods=['PUT'])
@token_required
def update_discussion(current_user, discussion_id):
    
    try:
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        if discussion.author_user_id != current_user.id:
            return ResponseService.error('无权限修改此讨论', status_code=403)

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        if 'content' in data:
            new_content = data['content'].strip()
            if not new_content:
                return ResponseService.error('讨论内容不能为空', status_code=400)
            discussion.content = new_content

        if 'image_urls' in data:
            discussion.image_urls = data['image_urls']

        discussion.update_time = datetime.now()
        db.session.commit()

        print(f"【讨论更新成功】讨论ID: {discussion_id}, 用户: {current_user.account}")

        discussion_data = {
            'id': discussion.id,
            'activity_id': discussion.activity_id,
            'content': discussion.content,
            'author_display': discussion.author_display,
            'image_urls': discussion.image_urls or [],
            'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z'),
            'update_time': discussion.update_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=discussion_data, message='讨论更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论更新失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>', methods=['DELETE'])
@token_required
def delete_discussion(current_user, discussion_id):
    
    try:
        print(f"【删除讨论请求】讨论ID: {discussion_id}, 用户: {current_user.account}")

        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        if discussion.author_user_id != current_user.id:
            return ResponseService.error('无权删除此讨论', status_code=403)

        comment_count = ActivityDiscussComment.query.filter_by(discuss_id=discussion_id).count()

        db.session.delete(discussion)
        db.session.commit()

        print(f"【讨论删除成功】讨论ID: {discussion_id}, 用户: {current_user.account}")
        print(f"【级联删除留言】共删除 {comment_count} 条相关留言")

        return ResponseService.success(
            data={
                'id': discussion_id,
                'deleted_comment_count': comment_count
            },
            message='讨论删除成功，所有相关留言已删除'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'讨论删除失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>/comments', methods=['POST'])
@token_required
def create_comment(current_user, discussion_id):
    
    try:
        print(f"【创建讨论留言请求】讨论ID: {discussion_id}, 用户: {current_user.account}")

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        content = data.get('content', '').strip()
        parent_comment_id = data.get('parent_comment_id')

        if not content:
            return ResponseService.error('留言内容不能为空', status_code=400)

        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        if parent_comment_id:
            parent_comment = ActivityDiscussComment.query.get(parent_comment_id)
            if not parent_comment or parent_comment.discuss_id != discussion_id:
                return ResponseService.error('父留言不存在或不属于该讨论', status_code=404)

        comment = ActivityDiscussComment(
            discuss_id=discussion_id,
            content=content,
            parent_comment_id=parent_comment_id if parent_comment_id else None
        )
        comment.set_author_info(current_user)

        db.session.add(comment)
        db.session.commit()

        print(f"【讨论留言成功】留言ID: {comment.id}, 用户: {current_user.account}")

        comment_data = {
            'id': comment.id,
            'discuss_id': comment.discuss_id,
            'content': comment.content,
            'author_user_id': comment.author_user_id,
            'author_display': comment.author_display,
            'author_avatar': comment.author_avatar,
            'parent_comment_id': comment.parent_comment_id,
            'create_time': comment.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=comment_data, message='留言发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'留言发表失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>/comments', methods=['GET'])
def get_discussion_comments(discussion_id):
    
    try:
        print(f"【讨论留言列表查询】讨论ID: {discussion_id}")

        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        sort_by = request.args.get('sort_by', 'oldest')

        query = ActivityDiscussComment.query.filter_by(discuss_id=discussion_id)

        if sort_by == 'latest':
            query = query.order_by(ActivityDiscussComment.create_time.desc())
        else:
            query = query.order_by(ActivityDiscussComment.create_time.asc())

        pagination = query.paginate(page=page, per_page=size)
        comments = pagination.items
        total = pagination.total

        comments_list = []
        for comment in comments:
            reply_count = ActivityDiscussComment.query.filter_by(
                parent_comment_id=comment.id
            ).count()

            comment_data = {
                'id': comment.id,
                'discuss_id': comment.discuss_id,
                'content': comment.content,
                'author_display': comment.author_display,
                'author_avatar': comment.author_avatar,
                'parent_comment_id': comment.parent_comment_id,
                'reply_count': reply_count,
                'create_time': comment.create_time.isoformat().replace('+00:00', 'Z')
            }
            comments_list.append(comment_data)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'sort_by': sort_by,
            'items': comments_list
        }, message="留言列表查询成功")

    except Exception as e:
        return ResponseService.error(f'留言列表查询失败: {str(e)}', status_code=500)


@discussion_bp.route('/comments/<int:comment_id>', methods=['PUT'])
@token_required
def update_comment(current_user, comment_id):
    
    try:
        comment = ActivityDiscussComment.query.get(comment_id)
        if not comment:
            return ResponseService.error('留言不存在', status_code=404)

        if comment.author_user_id != current_user.id:
            return ResponseService.error('无权限修改此留言', status_code=403)

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        if 'content' in data:
            new_content = data['content'].strip()
            if not new_content:
                return ResponseService.error('留言内容不能为空', status_code=400)
            comment.content = new_content

        comment.update_time = datetime.now()
        db.session.commit()

        print(f"【留言更新成功】留言ID: {comment_id}, 用户: {current_user.account}")

        comment_data = {
            'id': comment.id,
            'discuss_id': comment.discuss_id,
            'content': comment.content,
            'author_display': comment.author_display,
            'parent_comment_id': comment.parent_comment_id,
            'create_time': comment.create_time.isoformat().replace('+00:00', 'Z'),
            'update_time': comment.update_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=comment_data, message='留言更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'留言更新失败: {str(e)}', status_code=500)


@discussion_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_comment(current_user, comment_id):
    
    try:
        print(f"【删除讨论留言请求】留言ID: {comment_id}, 用户: {current_user.account}")

        comment = ActivityDiscussComment.query.get(comment_id)
        if not comment:
            return ResponseService.error('留言不存在', status_code=404)

        if comment.author_user_id != current_user.id:
            return ResponseService.error('无权删除此留言', status_code=403)

        child_comments = ActivityDiscussComment.query.filter_by(parent_comment_id=comment_id).all()
        for child_comment in child_comments:
            child_comment.parent_comment_id = None
            print(f"【子留言处理】子留言ID: {child_comment.id} 的parent_comment_id设为NULL")

        db.session.delete(comment)
        db.session.commit()

        print(f"【讨论留言删除成功】留言ID: {comment_id}, 用户: {current_user.account}")
        print(f"【子留言保留】共保留 {len(child_comments)} 条子留言")

        return ResponseService.success(
            data={
                'id': comment_id,
                'preserved_child_count': len(child_comments)
            },
            message='留言删除成功，子留言已保留'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'留言删除失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>/comments/nested', methods=['GET'])
def get_nested_comments(discussion_id):
    
    try:
        print(f"【嵌套留言查询】讨论ID: {discussion_id}")

        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        comments = ActivityDiscussComment.query.filter_by(
            discuss_id=discussion_id
        ).order_by(ActivityDiscussComment.create_time.asc()).all()

        comments_dict = {}
        root_comments = []

        for comment in comments:
            comment_data = {
                'id': comment.id,
                'discuss_id': comment.discuss_id,
                'content': comment.content,
                'author_display': comment.author_display,
                'author_avatar': comment.author_avatar,
                'parent_comment_id': comment.parent_comment_id,
                'create_time': comment.create_time.isoformat().replace('+00:00', 'Z'),
                'replies': []
            }
            comments_dict[comment.id] = comment_data

            if comment.parent_comment_id is None:
                root_comments.append(comment_data)
            else:
                if comment.parent_comment_id in comments_dict:
                    comments_dict[comment.parent_comment_id]['replies'].append(comment_data)

        return ResponseService.success({
            'discussion_id': discussion_id,
            'total_comments': len(comments),
            'root_comments_count': len(root_comments),
            'comments': root_comments
        }, message="嵌套留言查询成功")

    except Exception as e:
        return ResponseService.error(f'嵌套留言查询失败: {str(e)}', status_code=500)


@discussion_bp.route('/activities/<int:activity_id>/discussions/search', methods=['GET'])
def search_discussions(activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        keyword = request.args.get('keyword', '').strip()
        if not keyword:
            return ResponseService.error('搜索关键词不能为空', status_code=400)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))

        query = ActivityDiscuss.query.filter(
            ActivityDiscuss.activity_id == activity_id,
            ActivityDiscuss.content.like(f'%{keyword}%')
        ).order_by(ActivityDiscuss.create_time.desc())

        pagination = query.paginate(page=page, per_page=size)
        discussions = pagination.items
        total = pagination.total

        discussions_list = []
        for discussion in discussions:
            comment_count = ActivityDiscussComment.query.filter_by(discuss_id=discussion.id).count()

            item = {
                'id': discussion.id,
                'activity_id': discussion.activity_id,
                'content': discussion.content,
                'author_display': discussion.author_display,
                'author_avatar': discussion.author_avatar,
                'image_urls': discussion.image_urls or [],
                'comment_count': comment_count,
                'create_time': discussion.create_time.isoformat().replace('+00:00', 'Z'),
                'update_time': discussion.update_time.isoformat().replace('+00:00', 'Z')
            }
            discussions_list.append(item)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'keyword': keyword,
            'items': discussions_list
        }, message='讨论搜索成功')

    except Exception as e:
        return ResponseService.error(f'搜索失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/<int:discussion_id>/pin', methods=['PUT'])
@token_required
def pin_discussion(current_user, discussion_id):
    
    try:
        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        activity = Activity.query.get(discussion.activity_id)
        if not activity or activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限置顶此讨论', status_code=403)

        data = request.get_json()
        is_pinned = data.get('is_pinned', True)


        pin_info = {
            'discussion_id': discussion_id,
            'is_pinned': is_pinned,
            'pin_time': datetime.now().isoformat().replace('+00:00', 'Z') if is_pinned else None,
            'operator': current_user.account
        }

        return ResponseService.success(data=pin_info, message=f'讨论已{"置顶" if is_pinned else "取消置顶"}')

    except Exception as e:
        return ResponseService.error(f'置顶操作失败: {str(e)}', status_code=500)


@discussion_bp.route('/discussions/statistics', methods=['GET'])
@token_required
def get_discussion_statistics(current_user):
    
    try:
        from sqlalchemy import text

        user_activities = Activity.query.filter_by(organizer_user_id=current_user.id).all()
        activity_ids = [activity.id for activity in user_activities]

        if not activity_ids:
            return ResponseService.success({
                'total_discussions': 0,
                'total_comments': 0,
                'activities_with_discussions': 0,
                'activities': []
            }, message='讨论统计查询成功')

        discussion_stats = db.session.execute(text(), {"activity_ids": tuple(activity_ids)}).fetchone()

        comment_stats = db.session.execute(text(), {"activity_ids": tuple(activity_ids)}).fetchone()

        activity_stats = db.session.execute(text(), {"activity_ids": tuple(activity_ids)}).fetchall()

        activities_data = []
        for stat in activity_stats:
            activities_data.append({
                'activity_id': stat.id,
                'activity_title': stat.title,
                'discussion_count': stat.discussion_count,
                'comment_count': stat.comment_count
            })

        statistics = {
            'user_id': current_user.id,
            'total_discussions': discussion_stats.total_discussions or 0,
            'total_comments': comment_stats.total_comments or 0,
            'activities_with_discussions': discussion_stats.activities_with_discussions or 0,
            'total_activities': len(activity_ids),
            'activities': activities_data,
            'updated_at': datetime.now().isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=statistics, message='讨论统计查询成功')

    except Exception as e:
        return ResponseService.error(f'统计查询失败: {str(e)}', status_code=500)