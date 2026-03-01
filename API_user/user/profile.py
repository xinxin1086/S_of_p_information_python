
from flask import request
from components import token_required, db, LocalImageStorage
from components.models import User, Admin
from components.response_service import ResponseService, UserInfoService, handle_api_exception
from . import user_bp
from ..common.utils import UserDataProcessor, UserValidator, validate_user_data

@user_bp.route('/user/info', methods=['GET'])
@token_required
@handle_api_exception
def get_current_user_info(current_user):
    
    print(f"【查询当前用户信息】用户: {current_user.account}")

    user_info = UserInfoService.get_current_user_info(current_user, include_sensitive=True)

    if not user_info:
        return ResponseService.error('用户信息不存在', status_code=404)

    print(f"【当前用户信息查询成功】用户: {current_user.account}, 用户类型: {user_info['user_type']}")
    return ResponseService.success(data=user_info, message="用户信息查询成功")

@user_bp.route('/user/info/<account>', methods=['GET'])
@token_required
@handle_api_exception
def get_user_info_by_account(current_user, account):
    
    print(f"【查询指定用户信息】查询者: {current_user.account}, 目标账号: {account}")

    user_info = UserInfoService.get_user_by_account(account, include_sensitive=False)

    if not user_info:
        return ResponseService.error('用户不存在', status_code=404)

    print(f"【指定用户信息查询成功】目标用户: {account}, 用户类型: {user_info['user_type']}")
    return ResponseService.success(data=user_info, message="用户信息查询成功")

@user_bp.route('/user/update', methods=['POST'])
@token_required
@handle_api_exception
def update_user_info(current_user):
    
    data = request.get_json()

    if not data:
        return ResponseService.error('请求数据不能为空', status_code=400)

    update_data = data.get('update_data', {})
    if not update_data:
        return ResponseService.error('缺少更新内容：update_data', status_code=400)

    valid_fields = ['username', 'phone', 'email', 'avatar', 'password']
    invalid_fields = [field for field in update_data.keys() if field not in valid_fields]
    if invalid_fields:
        return ResponseService.error(f'不支持的更新字段: {", ".join(invalid_fields)}', status_code=400)

    target_user = None
    target_user_type = None

    target_user = User.query.filter_by(account=current_user.account).first()
    if target_user:
        target_user_type = 'user'
    else:
        target_user = Admin.query.filter_by(account=current_user.account).first()
        if target_user:
            target_user_type = 'admin'

    if not target_user:
        return ResponseService.error('当前用户信息不存在', status_code=404)

    print(f"【用户更新自身信息】用户: {current_user.account}")

    update_data.pop('account', None)

    validation_errors = validate_user_data(update_data, optional_fields=['username', 'phone', 'email'])
    if validation_errors:
        return ResponseService.error(f'数据验证失败: {", ".join(validation_errors)}', status_code=400)

    if 'avatar' in update_data:
        new_avatar = update_data['avatar']
        if new_avatar is None or new_avatar.strip() == '':
            if target_user.avatar:
                filename = target_user.avatar.split('/')[-1]
                LocalImageStorage().delete_image(filename)
                print(f"【删除头像】用户: {target_user.account}, 文件: {filename}")
        else:
            if target_user.avatar:
                filename = target_user.avatar.split('/')[-1]
                LocalImageStorage().delete_image(filename)
                print(f"【更新头像】用户: {target_user.account}, 删除旧头像: {filename}")

    if 'password' in update_data:
        new_password = update_data.pop('password')
        if new_password and new_password.strip():
            target_user.set_password(new_password)
            print(f"【更新密码】用户: {target_user.account} 的密码已更新")

    if 'username' in update_data and update_data['username'] != target_user.username:
        model_class = User if target_user_type == 'user' else Admin
        existing_user = model_class.query.filter_by(username=update_data['username']).first()
        if existing_user and existing_user.id != target_user.id:
            return ResponseService.error('用户名已存在', status_code=400)

    if 'phone' in update_data and update_data['phone'] != target_user.phone:
        model_class = User if target_user_type == 'user' else Admin
        existing_user = model_class.query.filter_by(phone=update_data['phone']).first()
        if existing_user and existing_user.id != target_user.id:
            return ResponseService.error('手机号已存在', status_code=400)

    try:
        updated_count = target_user.__class__.query.filter_by(id=target_user.id).update(update_data)
        db.session.commit()

        print(f"【用户信息更新成功】用户: {target_user.account}, 更新字段数: {len(update_data)}")

        result_data = {
            'updated_count': updated_count,
            'target_account': target_user.account,
            'updated_fields': list(update_data.keys())
        }

        return ResponseService.success(data=result_data, message="个人信息更新成功")

    except Exception as db_error:
        db.session.rollback()
        raise db_error

@user_bp.route('/user/activities', methods=['GET'])
@token_required
@handle_api_exception
def get_user_activities(current_user):
    
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        activity_type = request.args.get('type', 'all')

        published_activities = []
        if activity_type in ['all', 'published']:
            from components.models import Activity
            published_query = Activity.query.filter_by(organizer_user_id=current_user.id)
            published_pagination = published_query.order_by(Activity.updated_at.desc()).paginate(page=page, per_page=size)

            for activity in published_pagination.items:
                published_activities.append({
                    'id': activity.id,
                    'title': activity.title,
                    'location': activity.location,
                    'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                    'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                    'status': activity.status,
                    'max_participants': activity.max_participants,
                    'type': 'published'
                })

        booked_activities = []
        if activity_type in ['all', 'booked']:
            from components.models import ActivityBooking, Activity
            booking_query = ActivityBooking.query.filter_by(user_account=current_user.account, status='booked')
            booking_pagination = booking_query.order_by(ActivityBooking.booking_time.desc()).paginate(page=page, per_page=size)

            for booking in booking_pagination.items:
                activity = Activity.query.get(booking.activity_id)
                if activity:
                    booked_activities.append({
                        'id': activity.id,
                        'title': activity.title,
                        'location': activity.location,
                        'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                        'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                        'status': activity.status,
                        'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z'),
                        'type': 'booked'
                    })

        all_activities = published_activities + booked_activities
        all_activities.sort(key=lambda x: x.get('start_time', x.get('booking_time')), reverse=True)

        result_data = {
            'total': len(all_activities),
            'page': page,
            'size': size,
            'items': all_activities[:size]
        }

        return ResponseService.success(data=result_data, message="用户活动记录查询成功")

    except Exception as e:
        print(f"【用户活动记录查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@user_bp.route('/user/activities/stats', methods=['GET'])
@token_required
def get_user_activities_stats(current_user):
    
    try:
        from components.models import Activity, ActivityBooking
        from sqlalchemy import func

        total_published = Activity.query.filter_by(organizer_user_id=current_user.id).count()

        now = datetime.utcnow()
        upcoming = Activity.query.filter(
            Activity.organizer_user_id == current_user.id,
            Activity.start_time > now,
            Activity.status == 'published'
        ).count()
        ongoing = Activity.query.filter(
            Activity.organizer_user_id == current_user.id,
            Activity.start_time <= now,
            Activity.end_time >= now,
            Activity.status == 'published'
        ).count()
        completed = Activity.query.filter(
            Activity.organizer_user_id == current_user.id,
            Activity.end_time < now,
            Activity.status == 'published'
        ).count()

        total_bookings = ActivityBooking.query.filter_by(user_account=current_user.account).count()

        stats = {
            'total_published': total_published,
            'upcoming': upcoming,
            'ongoing': ongoing,
            'completed': completed,
            'total_bookings': total_bookings
        }

        return ResponseService.success(data=stats, message='用户活动统计查询成功')

    except Exception as e:
        print(f"【用户活动统计查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

@user_bp.route('/user/delete-account', methods=['POST'])
@token_required
@handle_api_exception
def delete_user_account(current_user):
    
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        password = data.get('password', '').strip()
        confirmation = data.get('confirmation', '').strip()

        if not password:
            return ResponseService.error('请提供密码进行身份验证', status_code=400)

        if confirmation != 'DELETE_MY_ACCOUNT':
            return ResponseService.error('请输入确认文本: DELETE_MY_ACCOUNT', status_code=400)

        user = User.query.filter_by(account=current_user.account, is_deleted=0).first()
        if not user:
            return ResponseService.error('用户不存在或已注销', status_code=404)

        if not user.check_password(password):
            return ResponseService.error('密码错误，无法注销账号', status_code=400)

        print(f"【用户注销请求】用户: {current_user.account}")

        deleted_user, message = user.soft_delete()

        if deleted_user:
            db.session.add(deleted_user)

        db.session.commit()

        print(f"【用户注销成功】用户: {current_user.account}, 注销记录ID: {deleted_user.id if deleted_user else None}")

        return ResponseService.success(
            data={
                'original_account': deleted_user.original_account if deleted_user else current_user.account,
                'delete_time': deleted_user.delete_time.isoformat().replace('+00:00', 'Z') if deleted_user else None
            },
            message="账号注销成功"
        )

    except Exception as e:
        db.session.rollback()
        print(f"【用户注销异常】错误: {str(e)}")
        return ResponseService.error(f'账号注销失败：{str(e)}', status_code=500)

print("【API_user 用户端个人信息接口模块加载完成】")