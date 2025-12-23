# 预约专门接口 - 独立拆分的预约管理

from flask import Blueprint, request
from components import db, token_required
from components.models import Activity, ActivityBooking, User
from components.response_service import ResponseService
from ..common.utils import ActivityValidator, ActivityStatistics
from datetime import datetime
from sqlalchemy import text

# 创建预约模块蓝图
booking_bp = Blueprint('booking', __name__, url_prefix='/api/activities/booking')


@booking_bp.route('/activities/<int:activity_id>/book', methods=['POST'])
@token_required
def create_booking(current_user, activity_id):
    """
    创建活动预约
    需要认证：是
    """
    try:
        print(f"【预约接口调用】用户: {current_user.account}, 活动ID: {activity_id}")

        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 验证活动是否可预约
        can_book, error_msg = ActivityValidator.is_activity_bookable(activity)
        if not can_book:
            return ResponseService.error(error_msg, status_code=400)

        # 检查用户预约冲突
        has_conflict, existing_booking = ActivityValidator.check_user_booking_conflict(
            current_user.account, activity_id
        )

        if has_conflict:
            return ResponseService.error('您已经预约过该活动', status_code=400)

        # 如果有取消过的预约记录，重新激活
        if existing_booking and existing_booking.status == 'cancelled':
            existing_booking.status = 'booked'
            existing_booking.notes = None
            existing_booking.updated_at = datetime.now()
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

        # 创建新预约
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
    """
    取消活动预约
    需要认证：是
    """
    try:
        print(f"【取消预约接口调用】用户: {current_user.account}, 活动ID: {activity_id}")

        # 查找用户的预约记录
        booking = ActivityBooking.query.filter_by(
            activity_id=activity_id,
            user_account=current_user.account,
            status='booked'
        ).first()

        if not booking:
            return ResponseService.error('未找到有效的预约记录', status_code=404)

        # 验证活动是否允许取消预约
        activity = Activity.query.get(activity_id)
        if activity and activity.status == 'completed':
            return ResponseService.error('活动已结束，无法取消预约', status_code=400)

        # 更新预约状态为取消
        booking.status = 'cancelled'
        booking.updated_at = datetime.now()
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
    """
    获取活动预约列表（管理员/组织者）
    需要认证：是
    """
    try:
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 检查权限（只有活动组织者可以查看预约列表）
        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限查看此活动的预约列表', status_code=403)

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()

        # 构建查询
        query = ActivityBooking.query.filter_by(activity_id=activity_id)

        # 状态筛选
        if status:
            query = query.filter(ActivityBooking.status == status)

        # 分页查询
        pagination = query.order_by(ActivityBooking.booking_time.desc()).paginate(page=page, per_page=size)
        bookings = pagination.items
        total = pagination.total

        bookings_data = []
        for booking in bookings:
            # 获取用户信息
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
    """
    获取用户的预约列表
    需要认证：是
    """
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '').strip()
        activity_status = request.args.get('activity_status', '').strip()

        # 构建查询
        query = ActivityBooking.query.filter_by(user_account=current_user.account)

        # 预约状态筛选
        if status:
            query = query.filter(ActivityBooking.status == status)

        # 按预约时间倒序排列
        query = query.order_by(ActivityBooking.booking_time.desc())

        # 分页查询
        pagination = query.paginate(page=page, per_page=size)
        bookings = pagination.items
        total = pagination.total

        bookings_data = []
        for booking in bookings:
            # 获取活动信息
            activity = Activity.query.get(booking.activity_id)

            # 活动状态筛选
            if activity_status and activity and activity.status != activity_status:
                continue

            # 获取当前预约人数
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

        # 手动分页（考虑活动状态筛选）
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
    """
    更新预约状态（管理员/组织者操作）
    需要认证：是
    """
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        new_status = data.get('status')
        notes = data.get('notes', '')

        if not new_status:
            return ResponseService.error('状态不能为空', status_code=400)

        # 验证状态值
        valid_statuses = ['booked', 'cancelled', 'attended', 'absent']
        if new_status not in valid_statuses:
            return ResponseService.error(f'无效的状态值，支持的值: {", ".join(valid_statuses)}', status_code=400)

        # 查找预约记录
        booking = ActivityBooking.query.get(booking_id)
        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        # 验证活动权限
        activity = Activity.query.get(booking.activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限修改此活动的预约状态', status_code=403)

        old_status = booking.status
        booking.status = new_status
        booking.notes = notes
        booking.updated_at = datetime.now()
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
    """
    批量操作预约（管理员/组织者操作）
    需要认证：是
    """
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        operation = data.get('operation')  # confirm_attendance/mark_absent/cancel
        booking_ids = data.get('booking_ids', [])

        if not operation:
            return ResponseService.error('操作类型不能为空', status_code=400)

        if not booking_ids:
            return ResponseService.error('预约ID列表不能为空', status_code=400)

        # 验证操作类型
        operation_map = {
            'confirm_attendance': 'attended',
            'mark_absent': 'absent',
            'cancel': 'cancelled'
        }

        if operation not in operation_map:
            return ResponseService.error(f'无效的操作类型，支持的值: {", ".join(operation_map.keys())}', status_code=400)

        # 验证活动权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限批量操作此活动的预约', status_code=403)

        # 查询要操作的预约
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
                booking.updated_at = datetime.now()
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
    """
    获取活动预约统计（管理员/组织者操作）
    需要认证：是
    """
    try:
        # 验证活动权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限查看此活动的预约统计', status_code=403)

        # 获取统计信息
        statistics = ActivityStatistics.get_booking_statistics(activity_id)

        return ResponseService.success(data=statistics, message='预约统计查询成功')

    except ValueError as e:
        return ResponseService.error(str(e), status_code=404)
    except Exception as e:
        return ResponseService.error(f'预约统计查询失败: {str(e)}', status_code=500)


@booking_bp.route('/activities/<int:activity_id>/availability', methods=['GET'])
def check_availability(activity_id):
    """
    检查活动预约可用性（无需认证）
    """
    try:
        # 验证活动是否存在
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        # 验证活动是否可预约
        can_book, error_msg = ActivityValidator.is_activity_bookable(activity)

        # 获取当前预约统计
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
    """
    获取预约详情
    需要认证：是
    """
    try:
        booking = ActivityBooking.query.get(booking_id)
        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        # 验证权限：用户只能查看自己的预约，或组织者可以查看所有预约
        activity = Activity.query.get(booking.activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if booking.user_account != current_user.account and activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限查看此预约记录', status_code=403)

        # 获取用户信息
        user = User.query.filter_by(account=booking.user_account, is_deleted=0).first()

        # 获取当前预约人数
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
            'user_phone': user.phone if (user and activity.organizer_user_id == current_user.id) else None,  # 只有组织者能看到手机号
            'user_email': user.email if (user and activity.organizer_user_id == current_user.id) else None,    # 只有组织者能看到邮箱
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
    """
    删除预约记录（仅管理员/组织者）
    需要认证：是
    """
    try:
        booking = ActivityBooking.query.get(booking_id)
        if not booking:
            return ResponseService.error('预约记录不存在', status_code=404)

        # 验证活动权限
        activity = Activity.query.get(booking.activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限删除此预约记录', status_code=403)

        # 记录删除信息
        deleted_info = {
            'booking_id': booking_id,
            'activity_id': booking.activity_id,
            'user_account': booking.user_account,
            'status': booking.status,
            'deleted_time': datetime.now().isoformat().replace('+00:00', 'Z'),
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
    """
    导出活动预约列表（管理员/组织者操作）
    需要认证：是
    """
    try:
        # 验证活动权限
        activity = Activity.query.get(activity_id)
        if not activity:
            return ResponseService.error('活动不存在', status_code=404)

        if activity.organizer_user_id != current_user.id:
            return ResponseService.error('无权限导出此活动的预约列表', status_code=403)

        status = request.args.get('status', '').strip()

        # 构建查询
        query = ActivityBooking.query.filter_by(activity_id=activity_id)
        if status:
            query = query.filter(ActivityBooking.status == status)

        # 获取所有预约记录
        bookings = query.order_by(ActivityBooking.booking_time.desc()).all()

        export_data = []
        for booking in bookings:
            # 获取用户信息
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
            'export_time': datetime.now().isoformat().replace('+00:00', 'Z'),
            'total_count': len(export_data),
            'data': export_data
        }

        return ResponseService.success(data=export_info, message='预约列表导出成功')

    except Exception as e:
        return ResponseService.error(f'导出失败: {str(e)}', status_code=500)