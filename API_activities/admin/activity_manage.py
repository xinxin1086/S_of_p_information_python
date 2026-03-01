
from flask import Blueprint, request
from components import db, token_required
from components.models import Activity, ActivityBooking, ActivityRating, User
from components.response_service import ResponseService
from ..common.utils import ActivityValidator, ActivityStatistics, ActivityStatusManager
from datetime import datetime, timezone

admin_manage_bp = Blueprint('admin_manage', __name__, url_prefix='/api/activities/admin')


@admin_manage_bp.route('/activities', methods=['POST'])
@token_required
def create_activity(current_user):
    
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        location = data.get('location', '').strip()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        max_participants = data.get('max_participants')
        tags = data.get('tags', [])
        status = data.get('status', 'draft')

        if not title:
            return ResponseService.error('活动标题不能为空', status_code=400)
        if not start_time or not end_time:
            return ResponseService.error('活动时间不能为空', status_code=400)
        if not max_participants:
            return ResponseService.error('最大参与人数不能为空', status_code=400)

        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        if start_dt >= end_dt:
            return ResponseService.error('活动开始时间必须早于结束时间', status_code=400)

        if start_dt < datetime.now(timezone.utc):
            return ResponseService.error('活动开始时间不能早于当前时间', status_code=400)

        valid_statuses = ['draft', 'published']
        if status not in valid_statuses:
            return ResponseService.error(f'无效的活动状态，支持的值: {", ".join(valid_statuses)}', status_code=400)

        activity = Activity(
            title=title,
            description=description,
            location=location,
            start_time=start_dt,
            end_time=end_dt,
            max_participants=int(max_participants),
            organizer_user_id=current_user.id,
            organizer_display=current_user.username,
            tags=tags if tags else [],
            status=status
        )

        db.session.add(activity)
        db.session.commit()

        print(f"【管理员创建活动】活动ID: {activity.id}, 用户: {current_user.account}")

        activity_data = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_participants': 0,
            'tags': activity.tags or [],
            'status': activity.status,
            'organizer_display': activity.organizer_display,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=activity_data, message='活动创建成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'活动创建失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>', methods=['PUT'])
@token_required
def update_activity(current_user, activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return ResponseService.error('活动标题不能为空', status_code=400)
            activity.title = title

        if 'description' in data:
            activity.description = data['description'].strip()

        if 'location' in data:
            activity.location = data['location'].strip()

        if 'start_time' in data:
            start_time = data['start_time']
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))

            if activity.end_time and start_dt >= activity.end_time:
                return ResponseService.error('活动开始时间必须早于结束时间', status_code=400)

            activity.start_time = start_dt

        if 'end_time' in data:
            end_time = data['end_time']
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

            if activity.start_time and activity.start_time >= end_dt:
                return ResponseService.error('活动结束时间必须晚于开始时间', status_code=400)

            activity.end_time = end_dt

        if 'max_participants' in data:
            max_participants = data['max_participants']
            if not max_participants or int(max_participants) <= 0:
                return ResponseService.error('最大参与人数必须大于0', status_code=400)

            current_booked = ActivityBooking.query.filter_by(
                activity_id=activity_id,
                status='booked'
            ).count()

            if int(max_participants) < current_booked:
                return ResponseService.error(
                    f'当前已有{current_booked}人预约，不能将人数限制设置为{max_participants}',
                    status_code=400
                )

            activity.max_participants = int(max_participants)

        if 'tags' in data:
            activity.tags = data['tags']

        if 'status' in data:
            new_status = data['status'].strip()
            success, error_msg = ActivityStatusManager.update_activity_status(
                activity, new_status, current_user.id
            )
            if not success:
                return ResponseService.error(error_msg, status_code=400)

        activity.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        print(f"【管理员更新活动】活动ID: {activity_id}, 用户: {current_user.account}")

        current_bookings = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            status='booked'
        ).count()

        activity_data = {
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
            'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=activity_data, message='活动更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'活动更新失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>', methods=['DELETE'])
@token_required
def delete_activity(current_user, activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        active_bookings = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            status='booked'
        ).count()

        if active_bookings > 0:
            return ResponseService.error(
                f'活动有{active_bookings}个有效预约，无法删除。请先取消所有预约或将活动状态改为已取消。',
                status_code=400
            )

        old_status = activity.status
        activity.status = 'cancelled'
        activity.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【管理员删除活动】活动ID: {activity_id}, 用户: {current_user.account}, 状态: {old_status} -> cancelled")

        return ResponseService.success(message='活动删除成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'活动删除失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities', methods=['GET'])
@token_required
def get_activities(current_user):
    
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()
        organizer_user_id = request.args.get('organizer_user_id', '').strip()
        keyword = request.args.get('keyword', '').strip()

        query = Activity.query

        if status:
            query = query.filter(Activity.status == status)

        if organizer_user_id:
            query = query.filter(Activity.organizer_user_id == int(organizer_user_id))

        if keyword:
            keyword = f"%{keyword}%"
            query = query.filter(
                (Activity.title.like(keyword)) |
                (Activity.description.like(keyword)) |
                (Activity.location.like(keyword))
            )

        pagination = query.order_by(Activity.updated_at.desc()).paginate(page=page, per_page=size)
        activities = pagination.items
        total = pagination.total

        result_list = []
        for activity in activities:
            current_bookings = ActivityBooking.query.filter_by(
                activity_id=activity.id,
                status='booked'
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
                'organizer_user_id': activity.organizer_user_id,
                'organizer_display': activity.organizer_display,
                'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
                'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z')
            }
            result_list.append(item)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': result_list
        }, message='活动列表查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>', methods=['GET'])
@token_required
def get_activity_detail(current_user, activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        booking_stats = ActivityStatistics.get_booking_statistics(activity_id)

        rating_stats = ActivityStatistics.get_rating_statistics(activity_id)

        activity_data = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'tags': activity.tags,
            'status': activity.status,
            'organizer_user_id': activity.organizer_user_id,
            'organizer_display': activity.organizer_display,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z'),
            'booking_statistics': booking_stats,
            'rating_statistics': rating_stats
        }

        return ResponseService.success(data=activity_data, message='活动详情查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>/bookings', methods=['GET'])
@token_required
def get_activity_bookings_admin(current_user, activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()

        query = ActivityBooking.query.filter_by(activity_id=activity_id)

        if status:
            query = query.filter(ActivityBooking.status == status)

        pagination = query.order_by(ActivityBooking.booking_time.desc()).paginate(page=page, per_page=size)
        bookings = pagination.items
        total = pagination.total

        bookings_data = []
        for booking in bookings:
            user = User.query.filter_by(account=booking.user_account, is_deleted=0).first()

            booking_info = {
                'id': booking.id,
                'activity_id': booking.activity_id,
                'user_account': booking.user_account,
                'user_display': user.username if user else '用户已注销',
                'user_avatar': user.avatar if user else None,
                'user_phone': user.phone if user else None,
                'user_email': user.email if user else None,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                'status': booking.status,
                'notes': booking.notes,
                'updated_at': booking.updated_at.isoformat().replace('+00:00', 'Z') if booking.updated_at else None
            }
            bookings_data.append(booking_info)

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': bookings_data
        }, message='预约列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取预约列表失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>/bookings/<int:booking_id>/status', methods=['PUT'])
@token_required
def update_booking_status_admin(current_user, activity_id, booking_id):
    
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        new_status = data.get('status')
        notes = data.get('notes', '')

        if not new_status:
            return ResponseService.error('状态不能为空', status_code=400)

        valid_statuses = ['booked', 'cancelled', 'attended', 'absent']
        if new_status not in valid_statuses:
            return ResponseService.error(f'无效的状态值，支持的值: {", ".join(valid_statuses)}', status_code=400)

        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        booking = ActivityBooking.query.filter_by(
            id=booking_id,
            activity_id=activity_id
        ).first()

        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        old_status = booking.status
        booking.status = new_status
        booking.notes = notes
        booking.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【管理员更新预约状态】预约ID: {booking_id}, 状态: {old_status} -> {new_status}, 操作者: {current_user.account}")

        return ResponseService.success({
            'booking_id': booking_id,
            'activity_id': activity_id,
            'old_status': old_status,
            'new_status': new_status,
            'notes': notes,
            'updated_time': booking.updated_at.isoformat().replace('+00:00', 'Z')
        }, message='预约状态更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'更新预约状态失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>/bookings/batch', methods=['POST'])
@token_required
def batch_update_bookings_admin(current_user, activity_id):
    
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        operation = data.get('operation')
        booking_ids = data.get('booking_ids', [])

        if not operation:
            return ResponseService.error('操作类型不能为空', status_code=400)

        if not booking_ids:
            return ResponseService.error('预约ID列表不能为空', status_code=400)

        operation_map = {
            'confirm_attendance': 'attended',
            'mark_absent': 'absent',
            'cancel': 'cancelled'
        }

        if operation not in operation_map:
            return ResponseService.error(f'无效的操作类型，支持的值: {", ".join(operation_map.keys())}', status_code=400)

        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        bookings = ActivityBooking.query.filter(
            ActivityBooking.id.in_(booking_ids),
            ActivityBooking.activity_id == activity_id
        ).all()

        if not bookings:
            return ResponseService.error('未找到可操作的预约记录', status_code=404)

        new_status = operation_map[operation]
        success_count = 0
        error_count = 0
        errors = []

        for booking in bookings:
            try:
                old_status = booking.status
                booking.status = new_status
                booking.updated_at = datetime.utcnow()
                success_count += 1
                print(f"【批量操作预约】预约ID: {booking.id}, 状态: {old_status} -> {new_status}")

            except Exception as e:
                error_count += 1
                errors.append(f"预约ID {booking.id}: {str(e)}")

        if success_count > 0:
            db.session.commit()

        return ResponseService.success({
            'operation': operation,
            'activity_id': activity_id,
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors
        }, message=f'批量操作完成，成功: {success_count} 个，失败: {error_count} 个')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'批量操作失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/<int:activity_id>/statistics', methods=['GET'])
@token_required
def get_activity_statistics_admin(current_user, activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_manage, error_msg = ActivityValidator.is_activity_manageable(activity, current_user.id)
        if not can_manage:
            return ResponseService.error(error_msg, status_code=403)

        booking_stats = ActivityStatistics.get_booking_statistics(activity_id)

        rating_stats = ActivityStatistics.get_rating_statistics(activity_id)

        statistics = {
            'activity_id': activity_id,
            'activity_title': activity.title,
            'activity_status': activity.status,
            'booking_statistics': booking_stats,
            'rating_statistics': rating_stats,
            'updated_at': datetime.utcnow().isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=statistics, message='活动统计查询成功')

    except Exception as e:
        return ResponseService.error(f'统计查询失败: {str(e)}', status_code=500)


@admin_manage_bp.route('/activities/summary', methods=['GET'])
@token_required
def get_activities_summary(current_user):
    
    try:
        from sqlalchemy import text

        stats = db.session.execute(text(), {"user_id": current_user.id}).fetchone()

        booking_stats = db.session.execute(text(), {"user_id": current_user.id}).fetchone()

        rating_stats = db.session.execute(text(), {"user_id": current_user.id}).fetchone()

        summary = {
            'user_id': current_user.id,
            'user_display': current_user.username,
            'activities': {
                'total': stats.total_activities or 0,
                'draft': stats.draft_count or 0,
                'published': stats.published_count or 0,
                'cancelled': stats.cancelled_count or 0,
                'completed': stats.completed_count or 0
            },
            'bookings': {
                'total': booking_stats.total_bookings or 0,
                'booked': booking_stats.booked_count or 0,
                'attended': booking_stats.attended_count or 0,
                'cancelled': booking_stats.cancelled_count or 0
            },
            'ratings': {
                'total': rating_stats.total_ratings or 0,
                'average_score': round(float(rating_stats.average_score), 2) if rating_stats.average_score else 0
            },
            'updated_at': datetime.utcnow().isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=summary, message='活动汇总查询成功')

    except Exception as e:
        return ResponseService.error(f'汇总查询失败: {str(e)}', status_code=500)