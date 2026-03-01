# API_user 管理员用户管理接口
# 管理员对用户的管理操作接口

from flask import request
from components import token_required, db
from components.models import Admin, User
from components.response_service import ResponseService, handle_api_exception
from . import admin_bp
from ..common.utils import (
    UserDataProcessor, UserValidator, UserPermissionChecker,
    validate_user_data, UserQueryHelper, admin_required, super_admin_required
)

@admin_bp.route('/admins', methods=['GET'])
@token_required
@admin_required
@handle_api_exception
def get_admin_list(current_user):
    """
    获取管理员列表
    需要管理员权限
    """
    try:
        print(f"【接收查询请求】当前用户: {current_user.account}")
        admins = Admin.query.all()
        data_list = []
        for admin in admins:
            item = UserDataProcessor.format_user_info(admin, include_sensitive=True)
            item.update({
                'phone': admin.phone or '无',
                'email': admin.email or '无'
            })
            data_list.append(item)
            print(f"【管理员数据】{item}")

        return ResponseService.success(
            data={
                'fields': Admin.get_fields_info(),
                'items': data_list,
                'total': len(data_list)
            },
            message='查询成功' if data_list else '无数据'
        )

    except Exception as e:
        print(f"【查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

@admin_bp.route('/users', methods=['GET', 'POST', 'PUT', 'DELETE'])
@token_required
@admin_required
@handle_api_exception
def manage_users(current_user):
    """
    用户信息管理接口
    需要管理员权限
    支持GET(查询)、POST(新增)、PUT(更新)、DELETE(删除)操作
    """
    try:
        if request.method == 'GET':
            # 查询用户列表
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 10))
            keyword = request.args.get('keyword', '').strip()
            role = request.args.get('role', '').strip()
            is_deleted = request.args.get('is_deleted', '0')

            query = User.query

            # 软删除状态筛选
            if is_deleted in ['0', '1']:
                query = query.filter(User.is_deleted == int(is_deleted))

            # 关键词搜索
            if keyword:
                query = query.filter(
                    (User.account.like(f'%{keyword}%')) |
                    (User.username.like(f'%{keyword}%')) |
                    (User.email.like(f'%{keyword}%'))
                )

            # 角色筛选
            if role:
                query = query.filter(User.role == role)

            # 分页查询
            pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=size)
            users = pagination.items
            total = pagination.total

            users_list = []
            for user in users:
                user_info = UserDataProcessor.format_user_info(user, include_sensitive=True)
                user_info['is_deleted'] = user.is_deleted
                users_list.append(user_info)

            return ResponseService.success(
                data={
                    'total': total,
                    'page': page,
                    'size': size,
                    'items': users_list
                },
                message='用户列表查询成功'
            )

        elif request.method == 'POST':
            # 新增用户
            data = request.get_json()

            # 验证必填字段
            required_fields = ['account', 'password', 'username']
            validation_errors = validate_user_data(data, required_fields=required_fields)
            if validation_errors:
                return ResponseService.error(f'数据验证失败: {", ".join(validation_errors)}', status_code=400)

            # 检查账号是否已存在
            if User.query.filter_by(account=data['account']).first():
                return ResponseService.error('账号已存在', status_code=400)

            # 检查手机号是否已存在
            phone = data.get('phone', '').strip()
            if phone and User.query.filter_by(phone=phone).first():
                return ResponseService.error('手机号已被使用', status_code=400)

            # 检查用户名是否已存在
            username = data.get('username', '').strip()
            if User.query.filter_by(username=username).first():
                return ResponseService.error('用户名已被使用', status_code=400)

            # 创建新用户
            user = User(
                account=data['account'],
                username=data['username'],
                email=data.get('email', '').strip(),
                phone=phone,
                role=data.get('role', 'USER'),
                avatar=data.get('avatar', '').strip(),
                is_deleted=0
            )
            user.set_password(data['password'])

            db.session.add(user)
            db.session.commit()

            print(f"【管理员创建用户】管理员: {current_user.account}, 新用户: {user.account}")

            return ResponseService.success(
                data=UserDataProcessor.format_user_info(user, include_sensitive=False),
                message='用户创建成功',
                status_code=201
            )

        elif request.method == 'PUT':
            # 更新用户信息
            data = request.get_json()
            user_id = data.get('id')

            if not user_id:
                return ResponseService.error('缺少用户ID', status_code=400)

            user = User.query.get(user_id)
            if not user:
                return ResponseService.error('用户不存在', status_code=404)

            # 权限检查：普通管理员不能修改其他管理员
            if not UserPermissionChecker.can_manage_user(current_user, user):
                return ResponseService.error('权限不足，无法修改该用户', status_code=403)

            # 清理更新数据
            allowed_fields = ['username', 'email', 'phone', 'avatar', 'password', 'role']
            if not UserPermissionChecker.is_super_admin(current_user):
                allowed_fields.remove('role')  # 普通管理员不能修改角色

            update_data = UserDataProcessor.clean_update_data(data, allowed_fields)

            if not update_data:
                return ResponseService.error('没有有效的更新字段', status_code=400)

            # 验证更新数据
            validation_errors = validate_user_data(update_data, optional_fields=list(update_data.keys()))
            if validation_errors:
                return ResponseService.error(f'数据验证失败: {", ".join(validation_errors)}', status_code=400)

            # 检查唯一性
            if 'username' in update_data and update_data['username'] != user.username:
                if User.query.filter_by(username=update_data['username']).first():
                    return ResponseService.error('用户名已存在', status_code=400)

            if 'phone' in update_data and update_data['phone'] != user.phone:
                if User.query.filter_by(phone=update_data['phone']).first():
                    return ResponseService.error('手机号已存在', status_code=400)

            # 处理密码更新
            if 'password' in update_data:
                user.set_password(update_data['password'])
                update_data.pop('password')

            # 执行更新
            for field, value in update_data.items():
                setattr(user, field, value)

            db.session.commit()

            print(f"【管理员更新用户】管理员: {current_user.account}, 目标用户: {user.account}")

            return ResponseService.success(
                data=UserDataProcessor.format_user_info(user, include_sensitive=False),
                message='用户信息更新成功'
            )

        elif request.method == 'DELETE':
            # 删除用户（软删除）
            user_id = request.args.get('id')

            if not user_id:
                return ResponseService.error('缺少用户ID', status_code=400)

            user = User.query.get(user_id)
            if not user:
                return ResponseService.error('用户不存在', status_code=404)

            # 权限检查：普通管理员不能删除其他管理员
            if not UserPermissionChecker.can_manage_user(current_user, user):
                return ResponseService.error('权限不足，无法删除该用户', status_code=403)

            # 执行软删除
            deleted_user, message = user.soft_delete()

            if deleted_user:
                db.session.add(deleted_user)

            db.session.commit()

            print(f"【管理员删除用户】管理员: {current_user.account}, 删除用户: {user.account}")

            return ResponseService.success(
                data={
                    'id': user.id,
                    'account': user.account,
                    'delete_time': deleted_user.delete_time.isoformat().replace('+00:00', 'Z') if deleted_user else None
                },
                message='用户删除成功'
            )

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'操作失败：{str(e)}', status_code=500)

@admin_bp.route('/demote/<int:admin_id>', methods=['POST'])
@token_required
@super_admin_required
@handle_api_exception
def demote_admin(current_user, admin_id):
    """
    降级单个管理员为普通用户
    需要超级管理员权限
    """
    try:
        print(f"【管理员降级请求】操作者: {current_user.account}, 目标管理员ID: {admin_id}")

        admin = Admin.query.get(admin_id)
        if not admin:
            return ResponseService.error('管理员不存在', status_code=404)

        # 执行降级操作
        result = admin.demote_to_regular_user()

        print(f"【管理员降级成功】管理员ID: {admin_id} 已降级为普通用户")

        return ResponseService.success(
            data=result,
            message='管理员降级成功'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【管理员降级异常】错误: {str(e)}")
        return ResponseService.error(f'降级管理员失败：{str(e)}', status_code=500)


@admin_bp.route('/create-admin', methods=['POST'])
@token_required
@super_admin_required
@handle_api_exception
def create_admin(current_user):
    """
    创建管理员账号
    需要超级管理员权限
    """
    try:
        data = request.get_json()

        # 验证必填字段
        required_fields = ['account', 'password', 'username', 'phone']
        validation_errors = validate_user_data(data, required_fields=required_fields)
        if validation_errors:
            return ResponseService.error(f'数据验证失败: {", ".join(validation_errors)}', status_code=400)

        # 检查账号是否已存在
        if User.query.filter_by(account=data['account']).first():
            return ResponseService.error('账号已存在', status_code=400)

        if Admin.query.filter_by(account=data['account']).first():
            return ResponseService.error('管理员账号已存在', status_code=400)

        # 检查手机号是否已存在
        if User.query.filter_by(phone=data['phone']).first() or Admin.query.filter_by(phone=data['phone']).first():
            return ResponseService.error('手机号已被使用', status_code=400)

        print(f"【创建管理员请求】操作者: {current_user.account}, 新管理员账号: {data['account']}")

        # 创建管理员
        admin_data = {
            'account': data['account'],
            'username': data['username'],
            'phone': data['phone'],
            'email': data.get('email', ''),
            'avatar': data.get('avatar', ''),
            'role': data.get('role', 'ADMIN')
        }

        admin = Admin.create_with_user(admin_data, data['password'])

        print(f"【管理员创建成功】管理员ID: {admin.id}, 账号: {admin.account}")

        return ResponseService.success(
            data=UserDataProcessor.format_user_info(admin, include_sensitive=False),
            message='管理员创建成功',
            status_code=201
        )

    except Exception as e:
        db.session.rollback()
        print(f"【创建管理员异常】错误: {str(e)}")
        return ResponseService.error(f'创建管理员失败：{str(e)}', status_code=500)

@admin_bp.route('/statistics', methods=['GET'])
@token_required
@admin_required
@handle_api_exception
def get_user_statistics(current_user):
    """
    获取用户统计信息
    需要管理员权限
    """
    try:
        print(f"【用户统计查询】操作者: {current_user.account}")

        # 统计普通用户
        total_users = User.query.count()
        active_users = User.query.filter_by(is_deleted=0).count()
        deleted_users = User.query.filter_by(is_deleted=1).count()

        # 按角色统计
        from sqlalchemy import func
        role_stats = db.session.query(
            User.role,
            func.count(User.id)
        ).filter_by(is_deleted=0).group_by(User.role).all()

        role_distribution = {role: count for role, count in role_stats}

        # 统计管理员
        total_admins = Admin.query.count()
        admin_stats = db.session.query(
            Admin.role,
            func.count(Admin.id)
        ).group_by(Admin.role).all()

        admin_distribution = {role: count for role, count in admin_stats}

        # 最近注册用户
        recent_users = User.query.filter_by(is_deleted=0).order_by(
            User.created_at.desc()
        ).limit(10).all()

        recent_users_list = [
            UserDataProcessor.format_user_info(user, include_sensitive=False)
            for user in recent_users
        ]

        statistics_data = {
            'users': {
                'total': total_users,
                'active': active_users,
                'deleted': deleted_users,
                'role_distribution': role_distribution,
                'recent_registrations': recent_users_list
            },
            'admins': {
                'total': total_admins,
                'role_distribution': admin_distribution
            }
        }

        return ResponseService.success(
            data=statistics_data,
            message='用户统计信息查询成功'
        )

    except Exception as e:
        print(f"【用户统计查询异常】错误: {str(e)}")
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)

print("【API_user 管理员用户管理接口模块加载完成】")