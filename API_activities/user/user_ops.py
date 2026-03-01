
from flask import Blueprint, request
from components import db, token_required
from components.models import Activity, ActivityBooking, ActivityRating, ActivityDiscuss, User
from components.response_service import ResponseService
from ..common.utils import ActivityValidator, ActivityStatistics
from datetime import datetime

user_ops_bp = Blueprint('user_ops', __name__, url_prefix='/api/activities/user')


@user_ops_bp.route('/activities/<int:activity_id>/booking', methods=['POST'])
@token_required
def book_activity(current_user, activity_id):
    
    try:
        print(f"【用户预约活动请求】用户: {current_user.account}, 活动ID: {activity_id}")

        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_book, error_msg = ActivityValidator.is_activity_bookable(activity)
        if not can_book:
            return ResponseService.error(error_msg, status_code=400)

        has_conflict, existing_booking = ActivityValidator.check_user_booking_conflict(
            current_user.account, activity_id
        )

        if has_conflict:
            return ResponseService.error('您已经预约过该活动', status_code=400)

        if existing_booking and existing_booking.status == 'cancelled':
            existing_booking.status = 'booked'
            existing_booking.notes = None
            existing_booking.updated_at = datetime.utcnow()
            db.session.commit()

            print(f"【预约重新激活】预约ID: {existing_booking.id}, 用户: {current_user.account}")

            booking_data = {
                'id': existing_booking.id,
                'activity_id': existing_booking.activity_id,
                'user_account': existing_booking.user_account,
                'status': existing_booking.status,
                'booking_time': existing_booking.booking_time.isoformat().replace('+00:00', 'Z')
            }

            return ResponseService.success(data=booking_data, message='活动预约成功')

        data = request.get_json() or {}
        booking = ActivityBooking(
            activity_id=activity_id,
            user_account=current_user.account,
            status='booked',
            notes=data.get('notes', '')
        )

        db.session.add(booking)
        db.session.commit()

        print(f"【预约创建成功】预约ID: {booking.id}, 用户: {current_user.account}")

        booking_data = {
            'id': booking.id,
            'activity_id': booking.activity_id,
            'user_account': booking.user_account,
            'status': booking.status,
            'notes': booking.notes,
            'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=booking_data, message='活动预约成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'预约失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/booking', methods=['DELETE'])
@token_required
def cancel_booking(current_user, activity_id):
    
    try:
        print(f"【用户取消预约请求】用户: {current_user.account}, 活动ID: {activity_id}")

        booking = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            user_account=current_user.account,
            status='booked'
        ).first()

        if not booking:
            return ResponseService.error('未找到有效的预约记录', status_code=404)

        activity = Activity.query.get(activity_id)
        if activity and activity.status == 'completed':
            return ResponseService.error('活动已结束，无法取消预约', status_code=400)

        booking.status = 'cancelled'
        booking.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【预约取消成功】预约ID: {booking.id}, 用户: {current_user.account}")

        return ResponseService.success(
            data={'id': booking.id, 'activity_id': activity_id},
            message='预约取消成功'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'取消预约失败: {str(e)}', status_code=500)


@user_ops_bp.route('/bookings', methods=['GET'])
@token_required
def get_my_bookings(current_user):
    
    try:
        try:
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 20))
        except ValueError:
            return ResponseService.error('分页参数格式错误', status_code=400)

        if page < 1:
            return ResponseService.error('页码必须大于0', status_code=400)
        if size < 1 or size > 100:
            return ResponseService.error('每页数量必须在1-100之间', status_code=400)

        status = request.args.get('status', '').strip()
        activity_status = request.args.get('activity_status', '').strip()

        query = ActivityBooking.query.filter_by(user_account=current_user.account)

        if status:
            query = query.filter(ActivityBooking.status == status)

        query = query.order_by(ActivityBooking.booking_time.desc())

        pagination = query.paginate(page=page, per_page=size)
        bookings = pagination.items

        activity_ids = [b.activity_id for b in bookings]
        activities = {a.id: a for a in Activity.query.filter(Activity.id.in_(activity_ids)).all()}

        current_participants = {}
        if activity_ids:
            from sqlalchemy import func
            participant_counts = db.session.query(
                ActivityBooking.activity_id,
                func.count(ActivityBooking.id).label('count')
            ).filter(
                ActivityBooking.activity_id.in_(activity_ids),
                ActivityBooking.status == 'booked'
            ).group_by(ActivityBooking.activity_id).all()
            current_participants = {row.activity_id: row.count for row in participant_counts}

        bookings_data = []
        for booking in bookings:
            activity = activities.get(booking.activity_id)

            if activity_status and activity and activity.status != activity_status:
                continue

            booking_info = {
                'id': booking.id,
                'activity_id': booking.activity_id,
                'activity_title': activity.title if activity else '活动已删除',
                'activity_description': activity.description if activity else None,
                'activity_location': activity.location if activity else None,
                'activity_start_time': activity.start_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_end_time': activity.end_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_max_participants': activity.max_participants if activity else None,
                'activity_current_participants': current_participants.get(booking.activity_id, 0),
                'activity_organizer_display': activity.organizer_display if activity else None,
                'activity_tags': activity.tags if activity else [],
                'activity_status': activity.status if activity else None,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                'status': booking.status,
                'notes': booking.notes
            }
            bookings_data.append(booking_info)

        total = len(bookings_data)
        start = (page - 1) * size
        end = start + size
        paginated_data = bookings_data[start:end]

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': paginated_data
        }, message='预约列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取预约列表失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/rating', methods=['POST'])
@token_required
def create_activity_rating(current_user, activity_id):
    
    try:
        print(f"【用户活动评分请求】用户: {current_user.account}, 活动ID: {activity_id}")

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        score = data.get('score')
        comment = data.get('comment', '')

        if not score or not (1 <= int(score) <= 5):
            return ResponseService.error('评分必须是1-5的整数', status_code=400)

        can_rate, error_msg = ActivityValidator.can_user_rate_activity(current_user.id, activity_id)
        if not can_rate:
            return ResponseService.error(error_msg, status_code=400)

        rating = ActivityRating(
            activity_id=activity_id,
            score=int(score),
            comment_content=comment.strip() if comment else None
        )
        rating.set_rater_info(current_user)

        db.session.add(rating)
        db.session.commit()

        print(f"【评分创建成功】评分ID: {rating.id}, 用户: {current_user.account}")

        rating_data = {
            'id': rating.id,
            'activity_id': rating.activity_id,
            'rater_user_id': rating.rater_user_id,
            'rater_display': rating.rater_display,
            'rater_avatar': rating.rater_avatar,
            'score': rating.score,
            'comment_content': rating.comment_content,
            'create_time': rating.create_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=rating_data, message='评分发表成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'评分发表失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/rating', methods=['PUT'])
@token_required
def update_activity_rating(current_user, activity_id):
    
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        rating = ActivityRating.query.filter_by(
            activity_id=activity_id,
            rater_user_id=current_user.id
        ).first()

        if not rating:
            return ResponseService.error('您还未为该活动评分', status_code=404)

        if 'score' in data:
            new_score = data['score']
            if not (1 <= int(new_score) <= 5):
                return ResponseService.error('评分必须是1-5的整数', status_code=400)
            rating.score = int(new_score)

        if 'comment_content' in data:
            rating.comment_content = data['comment_content'].strip() if data['comment_content'] else None

        rating.update_time = datetime.utcnow()
        db.session.commit()

        print(f"【评分更新成功】评分ID: {rating.id}, 用户: {current_user.account}")

        rating_data = {
            'id': rating.id,
            'activity_id': rating.activity_id,
            'rater_display': rating.rater_display,
            'rater_avatar': rating.rater_avatar,
            'score': rating.score,
            'comment_content': rating.comment_content,
            'create_time': rating.create_time.isoformat().replace('+00:00', 'Z'),
            'update_time': rating.update_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=rating_data, message='评分更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'评分更新失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/rating', methods=['DELETE'])
@token_required
def delete_activity_rating(current_user, activity_id):
    
    try:
        rating = ActivityRating.query.filter_by(
            activity_id=activity_id,
            rater_user_id=current_user.id
        ).first()

        if not rating:
            return ResponseService.error('您还未为该活动评分', status_code=404)

        db.session.delete(rating)
        db.session.commit()

        print(f"【评分删除成功】评分ID: {rating.id}, 用户: {current_user.account}")

        return ResponseService.success(
            data={'rating_id': rating.id},
            message='评分删除成功'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'评分删除失败: {str(e)}', status_code=500)


@user_ops_bp.route('/ratings', methods=['GET'])
@token_required
def get_my_ratings(current_user):
    
    try:
        try:
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 20))
        except ValueError:
            return ResponseService.error('分页参数格式错误', status_code=400)

        if page < 1:
            return ResponseService.error('页码必须大于0', status_code=400)
        if size < 1 or size > 100:
            return ResponseService.error('每页数量必须在1-100之间', status_code=400)

        activity_status = request.args.get('activity_status', '').strip()

        query = ActivityRating.query.filter_by(rater_user_id=current_user.id)
        query = query.order_by(ActivityRating.create_time.desc())

        pagination = query.paginate(page=page, per_page=size)
        ratings = pagination.items

        activity_ids = [r.activity_id for r in ratings]
        activities = {a.id: a for a in Activity.query.filter(Activity.id.in_(activity_ids)).all()}

        ratings_list = []
        for rating in ratings:
            activity = activities.get(rating.activity_id)

            if activity_status and activity and activity.status != activity_status:
                continue

            item = {
                'id': rating.id,
                'activity_id': rating.activity_id,
                'activity_title': activity.title if activity else '活动已删除',
                'activity_description': activity.description if activity else None,
                'activity_start_time': activity.start_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_end_time': activity.end_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_organizer_display': activity.organizer_display if activity else None,
                'activity_status': activity.status if activity else None,
                'score': rating.score,
                'comment_content': rating.comment_content,
                'create_time': rating.create_time.isoformat().replace('+00:00', 'Z'),
                'update_time': rating.update_time.isoformat().replace('+00:00', 'Z')
            }
            ratings_list.append(item)

        total = len(ratings_list)
        start = (page - 1) * size
        end = start + size
        paginated_data = ratings_list[start:end]

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': paginated_data
        }, message='评分列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取评分列表失败: {str(e)}', status_code=500)


@user_ops_bp.route('/activities/<int:activity_id>/discussions', methods=['POST'])
@token_required
def create_activity_discussion(current_user, activity_id):
    
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


@user_ops_bp.route('/discussions/<int:discussion_id>', methods=['PUT'])
@token_required
def update_activity_discussion(current_user, discussion_id):
    
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

        discussion.update_time = datetime.utcnow()
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


@user_ops_bp.route('/discussions/<int:discussion_id>', methods=['DELETE'])
@token_required
def delete_activity_discussion(current_user, discussion_id):
    
    try:
        print(f"【删除讨论请求】讨论ID: {discussion_id}, 用户: {current_user.account}")

        discussion = ActivityDiscuss.query.get(discussion_id)
        if not discussion:
            return ResponseService.error('讨论不存在', status_code=404)

        if discussion.author_user_id != current_user.id:
            return ResponseService.error('无权删除此讨论', status_code=403)

        from components.models import ActivityDiscussComment
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


@user_ops_bp.route('/my-activities', methods=['GET'])
@token_required
def get_my_activities(current_user):
    
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        role = request.args.get('role', 'all')
        status = request.args.get('status', '').strip()

        result_list = []

        if role in ['organizer', 'all']:
            organizer_query = Activity.query.filter_by(organizer_user_id=current_user.id)
            if status:
                organizer_query = organizer_query.filter(Activity.status == status)

            organizer_activities = organizer_query.order_by(Activity.updated_at.desc()).all()

            for activity in organizer_activities:
                current_bookings = ActivityBooking.query.filter_by(
                    activity_id=activity.id, status='booked'
                ).count()

                item = {
                    'id': activity.id,
                    'title': activity.title,
                    'description': activity.description,
                    'location': activity.location,
                    'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                    'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                    'max_participants': activity.max_participants,
                    'current_participants': current_bookings,
                    'tags': activity.tags,
                    'status': activity.status,
                    'role': 'organizer',
                    'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
                    'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z')
                }
                result_list.append(item)

        if role in ['participant', 'all']:
            participant_query = ActivityBooking.query.filter_by(user_account=current_user.account)
            if status:
                participant_query = participant_query.join(Activity).filter(Activity.status == status)

            participant_bookings = participant_query.order_by(ActivityBooking.booking_time.desc()).all()

            for booking in participant_bookings:
                activity = Activity.query.get(booking.activity_id)
                if not activity:
                    continue

                if any(item['id'] == activity.id for item in result_list):
                    continue

                current_bookings = ActivityBooking.query.filter_by(
                    activity_id=activity.id, status='booked'
                ).count()

                item = {
                    'id': activity.id,
                    'title': activity.title,
                    'description': activity.description,
                    'location': activity.location,
                    'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                    'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                    'max_participants': activity.max_participants,
                    'current_participants': current_bookings,
                    'tags': activity.tags,
                    'status': activity.status,
                    'role': 'participant',
                    'booking_status': booking.status,
                    'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                    'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
                    'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z')
                }
                result_list.append(item)

        result_list.sort(key=lambda x: x['updated_at'], reverse=True)

        total = len(result_list)
        start = (page - 1) * size
        end = start + size
        paginated_data = result_list[start:end]

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': paginated_data
        }, message='我的活动列表查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败: {str(e)}', status_code=500)