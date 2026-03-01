
from flask import Blueprint, request
from components import db, token_required
from components.models import Activity, ActivityBooking, User
from components.response_service import ResponseService
from ..common.utils import ActivityValidator, ActivityStatistics
from datetime import datetime
from sqlalchemy import text

booking_bp = Blueprint('booking', __name__, url_prefix='/api/activities/booking')


@booking_bp.route('/activities/<int:activity_id>/book', methods=['POST'])
@token_required
def create_booking(current_user, activity_id):
    
    try:
        print(f"【预约接口调用】用户: {current_user.account}, 活动ID: {activity_id}")

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

            print(f"【预约重新激活】预约ID: {existing_booking.id}")

            booking_data = {
                'id': existing_booking.id,
                'activity_id': existing_booking.activity_id,
                'user_account': existing_booking.user_account,
                'status': existing_booking.status,
                'booking_time': existing_booking.booking_time.isoformat().replace('+00:00', 'Z')
            }

            return ResponseService.success(data=booking_data, message='预约成功')

        data = request.get_json() or {}
        booking = ActivityBooking(
            activity_id=activity_id,
            user_account=current_user.account,
            status='booked',
            notes=data.get('notes', '')
        )

        db.session.add(booking)
        db.session.commit()

        print(f"【预约创建成功】预约ID: {booking.id}")

        booking_data = {
            'id': booking.id,
            'activity_id': booking.activity_id,
            'user_account': booking.user_account,
            'status': booking.status,
            'notes': booking.notes,
            'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=booking_data, message='预约成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'预约失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/cancel', methods=['DELETE'])
@token_required
def cancel_booking(current_user, activity_id):
    
    try:
        print(f"【取消预约接口调用】用户: {current_user.account}, 活动ID: {activity_id}")

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

        print(f"【预约取消成功】预约ID: {booking.id}")

        return ResponseService.success(
            data={'id': booking.id, 'activity_id': activity_id},
            message='预约取消成功'
        )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'取消预约失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/bookings', methods=['GET'])
@token_required
def get_activity_bookings(current_user, activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限查看此活动的预约列表', status_code=403)

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


@booking_bp.route('/my-bookings', methods=['GET'])
@token_required
def get_user_bookings(current_user):
    
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
        total = pagination.total

        bookings_data = []
        for booking in bookings:
            activity = Activity.query.get(booking.activity_id)

            if activity_status and activity and activity.status != activity_status:
                continue

            current_booked = ActivityBooking.query.filter_by(
                activity_id=booking.activity_id,
                status='booked'
            ).count()

            booking_info = {
                'id': booking.id,
                'activity_id': booking.activity_id,
                'activity_title': activity.title if activity else '活动已删除',
                'activity_description': activity.description if activity else None,
                'activity_location': activity.location if activity else None,
                'activity_start_time': activity.start_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_end_time': activity.end_time.isoformat().replace('+00:00', 'Z') if activity else None,
                'activity_max_participants': activity.max_participants if activity else None,
                'activity_current_participants': current_booked,
                'activity_organizer_display': activity.organizer_display if activity else None,
                'activity_tags': activity.tags if activity else [],
                'activity_status': activity.status if activity else None,
                'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                'status': booking.status,
                'notes': booking.notes,
                'updated_at': booking.updated_at.isoformat().replace('+00:00', 'Z') if booking.updated_at else None
            }
            bookings_data.append(booking_info)

        filtered_total = len(bookings_data)
        start = (page - 1) * size
        end = start + size
        paginated_data = bookings_data[start:end]

        return ResponseService.success({
            'total': filtered_total,
            'page': page,
            'size': size,
            'items': paginated_data
        }, message='预约列表获取成功')

    except Exception as e:
        return ResponseService.error(f'获取预约列表失败: {str(e)}', status_code=500)


@booking_bp.route('/bookings/<int:booking_id>/status', methods=['PUT'])
@token_required
def update_booking_status(current_user, booking_id):
    
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

        booking = ActivityBooking.query.get(booking_id)
        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        activity = Activity.query.get(booking.activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限修改此活动的预约状态', status_code=403)

        old_status = booking.status
        booking.status = new_status
        booking.notes = notes
        booking.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"【预约状态更新】预约ID: {booking_id}, 状态: {old_status} -> {new_status}")

        return ResponseService.success({
            'booking_id': booking_id,
            'activity_id': booking.activity_id,
            'old_status': old_status,
            'new_status': new_status,
            'notes': notes,
            'updated_time': booking.updated_at.isoformat().replace('+00:00', 'Z')
        }, message='预约状态更新成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'更新预约状态失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/bookings/batch', methods=['POST'])
@token_required
def batch_update_bookings(current_user, activity_id):
    
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

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限批量操作此活动的预约', status_code=403)

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


@booking_bp.route('/activities/<int:activity_id>/bookings/statistics', methods=['GET'])
@token_required
def get_booking_statistics(current_user, activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限查看此活动的预约统计', status_code=403)

        statistics = ActivityStatistics.get_booking_statistics(activity_id)

        return ResponseService.success(data=statistics, message='预约统计查询成功')

    except ValueError as e:
        return ResponseService.error(str(e), status_code=404)
    except Exception as e:
        return ResponseService.error(f'预约统计查询失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/availability', methods=['GET'])
def check_availability(activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        can_book, error_msg = ActivityValidator.is_activity_bookable(activity)

        try:
            statistics = ActivityStatistics.get_booking_statistics(activity_id)
        except ValueError:
            statistics = {
                'activity_id': activity_id,
                'total_bookings': 0,
                'current_booked': 0,
                'max_participants': activity.max_participants
            }

        availability = {
            'activity_id': activity_id,
            'title': activity.title,
            'status': activity.status,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_booked': statistics.get('current_booked', 0),
            'available_spots': statistics.get('available_spots', None),
            'is_bookable': can_book,
            'error_message': error_msg if not can_book else None,
            'booking_deadline': activity.end_time.isoformat().replace('+00:00', 'Z') if activity.end_time else None
        }

        return ResponseService.success(data=availability, message='可用性查询成功')

    except Exception as e:
        return ResponseService.error(f'可用性查询失败: {str(e)}', status_code=500)


@booking_bp.route('/bookings/<int:booking_id>', methods=['GET'])
@token_required
def get_booking_detail(current_user, booking_id):
    
    try:
        booking = ActivityBooking.query.get(booking_id)
        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        activity = Activity.query.get(booking.activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if booking.user_account != current_user.account and activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限查看此预约记录', status_code=403)

        user = User.query.filter_by(account=booking.user_account, is_deleted=0).first()

        current_booked = ActivityBooking.query.filter_by(
            activity_id=booking.activity_id,
            status='booked'
        ).count()

        booking_data = {
            'id': booking.id,
            'activity_id': booking.activity_id,
            'activity_title': activity.title,
            'activity_description': activity.description,
            'activity_location': activity.location,
            'activity_start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'activity_end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'activity_max_participants': activity.max_participants,
            'activity_current_participants': current_booked,
            'activity_status': activity.status,
            'user_account': booking.user_account,
            'user_display': user.username if user else '用户已注销',
            'user_avatar': user.avatar if user else None,
            'user_phone': user.phone if (user and activity.organizer_user_id == current_user.id) else None,
            'user_email': user.email if (user and activity.organizer_user_id == current_user.id) else None,
            'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
            'status': booking.status,
            'notes': booking.notes,
            'updated_at': booking.updated_at.isoformat().replace('+00:00', 'Z') if booking.updated_at else None
        }

        return ResponseService.success(data=booking_data, message='预约详情查询成功')

    except Exception as e:
        return ResponseService.error(f'预约详情查询失败: {str(e)}', status_code=500)


@booking_bp.route('/bookings/<int:booking_id>', methods=['DELETE'])
@token_required
def delete_booking(current_user, booking_id):
    
    try:
        booking = ActivityBooking.query.get(booking_id)
        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        activity = Activity.query.get(booking.activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限删除此预约记录', status_code=403)

        deleted_info = {
            'booking_id': booking_id,
            'activity_id': booking.activity_id,
            'user_account': booking.user_account,
            'status': booking.status,
            'deleted_time': datetime.utcnow().isoformat().replace('+00:00', 'Z'),
            'deleted_by': current_user.account
        }

        db.session.delete(booking)
        db.session.commit()

        print(f"【预约记录删除】预约ID: {booking_id}, 操作者: {current_user.account}")

        return ResponseService.success(data=deleted_info, message='预约记录删除成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'删除预约记录失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/export/bookings', methods=['GET'])
@token_required
def export_bookings(current_user, activity_id):
    
    try:
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限导出此活动的预约列表', status_code=403)

        status = request.args.get('status', '').strip()

        query = ActivityBooking.query.filter_by(activity_id=activity_id)
        if status:
            query = query.filter(ActivityBooking.status == status)

        bookings = query.order_by(ActivityBooking.booking_time.desc()).all()

        export_data = []
        for booking in bookings:
            user = User.query.filter_by(account=booking.user_account, is_deleted=0).first()

            booking_data = {
                '预约ID': booking.id,
                '活动ID': booking.activity_id,
                '活动标题': activity.title,
                '用户账号': booking.user_account,
                '用户姓名': user.username if user else '用户已注销',
                '用户手机': user.phone if user else '',
                '用户邮箱': user.email if user else '',
                '预约时间': booking.booking_time.strftime('%Y-%m-%d %H:%M:%S'),
                '预约状态': booking.status,
                '备注': booking.notes or '',
                '更新时间': booking.updated_at.strftime('%Y-%m-%d %H:%M:%S') if booking.updated_at else ''
            }
            export_data.append(booking_data)

        export_info = {
            'activity_id': activity_id,
            'activity_title': activity.title,
            'export_time': datetime.utcnow().isoformat().replace('+00:00', 'Z'),
            'total_count': len(export_data),
            'data': export_data
        }

        return ResponseService.success(data=export_info, message='预约列表导出成功')

    except Exception as e:
        return ResponseService.error(f'导出失败: {str(e)}', status_code=500)