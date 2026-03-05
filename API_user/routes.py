# API_user 统一路由文件
# 合并所有子模块的路由和工具函数
# 优化后的单文件结构

import re
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify

from components import token_required, db, LocalImageStorage
from components.models import User, Admin, Activity, ActivityBooking
from components.response_service import ResponseService, UserInfoService, handle_api_exception
from config import Config

# ============================================================
# 公共工具类和函数
# ============================================================

class UserValidator:
    """用户相关参数校验工具类"""

    @staticmethod
    def validate_email(email):
        """校验邮箱格式"""
        if not email:
            return True  # 邮箱为空时允许
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_phone(phone):
        """校验手机号格式"""
        if not phone:
            return True  # 手机号为空时允许
        pattern = r'^1[3-9]\d{9}$'
        return re.match(pattern, phone) is not None

    @staticmethod
    def validate_password(password):
        """校验密码格式"""
        if not password:
            return False, "密码不能为空"
        if len(password) < 6 or len(password) > 20:
            return False, "密码长度应在6-20个字符之间"
        return True, "密码格式正确"

    @staticmethod
    def validate_username(username):
        """校验用户名格式"""
        if not username or not username.strip():
            return False, "用户名不能为空"
        if len(username.strip()) < 2 or len(username.strip()) > 20:
            return False, "用户名长度应在2-20个字符之间"
        return True, "用户名格式正确"


class UserPermissionChecker:
    """用户权限检查工具类"""

    @staticmethod
    def is_admin_user(current_user):
        """检查当前用户是否为管理员"""
        return hasattr(current_user, 'role') and current_user.role in ['ADMIN', 'SUPER_ADMIN']

    @staticmethod
    def is_super_admin(current_user):
        """检查当前用户是否为超级管理员"""
        return hasattr(current_user, 'role') and current_user.role == 'SUPER_ADMIN'

    @staticmethod
    def can_manage_user(current_user, target_user):
        """检查当前用户是否可以管理目标用户"""
        # 超级管理员可以管理所有用户
        if UserPermissionChecker.is_super_admin(current_user):
            return True

        # 普通管理员只能管理普通用户，不能管理其他管理员
        if UserPermissionChecker.is_admin_user(current_user):
            return not UserPermissionChecker.is_admin_user(target_user)

        # 普通用户不能管理其他用户
        return False


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = args[0]  # 假设第一个参数是 current_user

        if not UserPermissionChecker.is_admin_user(current_user):
            return ResponseService.error('权限不足，需要管理员权限', status_code=403)

        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    """超级管理员权限装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = args[0]  # 假设第一个参数是 current_user

        if not UserPermissionChecker.is_super_admin(current_user):
            return ResponseService.error('权限不足，需要超级管理员权限', status_code=403)

        return f(*args, **kwargs)
    return decorated


class UserDataProcessor:
    """用户数据处理工具类"""

    @staticmethod
    def format_user_info(user, include_sensitive=False):
        """格式化用户信息"""
        base_info = {
            'id': user.id,
            'username': user.username,
            'avatar': user.avatar,
            'role': getattr(user, 'role', 'USER'),
            'created_at': user.created_at.isoformat().replace('+00:00', 'Z')
        }

        if include_sensitive:
            base_info.update({
                'account': user.account,
                'phone': getattr(user, 'phone', ''),
                'email': getattr(user, 'email', ''),
                'is_deleted': getattr(user, 'is_deleted', 0)
            })

        return base_info

    @staticmethod
    def clean_update_data(data, allowed_fields=None):
        """清理更新数据，只保留允许的字段"""
        if allowed_fields is None:
            allowed_fields = ['username', 'phone', 'email', 'avatar', 'password']

        return {k: v for k, v in data.items() if k in allowed_fields}


class UserQueryHelper:
    @staticmethod
    def find_user_by_account(account):
        admin = Admin.query.filter_by(account=account).first()
        if admin:
            return admin, 'admin'

        user = User.query.filter_by(account=account, is_deleted=0).first()
        if user:
            return user, 'user'

        return None, None

    @staticmethod
    def find_user_by_identifier(identifier):
        admin = Admin.query.filter_by(account=identifier).first()
        if admin:
            return admin, 'admin'
        user = User.query.filter_by(account=identifier, is_deleted=0).first()
        if user:
            return user, 'user'

        admin = Admin.query.filter_by(phone=identifier).first()
        if admin:
            return admin, 'admin'
        user = User.query.filter_by(phone=identifier, is_deleted=0).first()
        if user:
            return user, 'user'

        admin = Admin.query.filter_by(email=identifier).first()
        if admin:
            return admin, 'admin'
        user = User.query.filter_by(email=identifier, is_deleted=0).first()
        if user:
            return user, 'user'

        return None, None


def validate_user_data(data, required_fields=None, optional_fields=None):
    """通用用户数据验证函数"""
    errors = []
    validator = UserValidator()

    # 检查必填字段
    if required_fields:
        for field in required_fields:
            value = data.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                errors.append(f'{field}不能为空')
            elif field == 'email' and not validator.validate_email(value):
                errors.append('邮箱格式不正确')
            elif field == 'phone' and not validator.validate_phone(value):
                errors.append('手机号格式不正确')
            elif field == 'password':
                is_valid, msg = validator.validate_password(value)
                if not is_valid:
                    errors.append(msg)
            elif field == 'username':
                is_valid, msg = validator.validate_username(value)
                if not is_valid:
                    errors.append(msg)

    # 检查可选字段格式
    if optional_fields:
        for field in optional_fields:
            value = data.get(field)
            if value and isinstance(value, str) and value.strip():
                if field == 'email' and not validator.validate_email(value):
                    errors.append('邮箱格式不正确')
                elif field == 'phone' and not validator.validate_phone(value):
                    errors.append('手机号格式不正确')
                elif field == 'username':
                    is_valid, msg = validator.validate_username(value)
                    if not is_valid:
                        errors.append(msg)

    return errors


# ============================================================
# Blueprint 创建
# ============================================================

# 创建主 Blueprint
api_user_bp = Blueprint('api_user', __name__, url_prefix='/api/user')

# 创建用户端模块 Blueprint
user_bp = Blueprint('user', __name__)

# 创建管理员用户管理模块 Blueprint
admin_bp = Blueprint('user_admin', __name__, url_prefix='/admin')

# 创建认证模块 Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# 创建用户信息公开访问模块蓝图
bp_user_public = Blueprint('user_public', __name__, url_prefix='/api/public/user')

# ============================================================
# 认证授权路由 (auth/)
# ============================================================

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录接口"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        account = data.get('account', '').strip()
        password = data.get('password', '').strip()

        if not account or not password:
            return ResponseService.error('账号和密码不能为空', status_code=400)

        print(f"【用户登录请求】账号: {account}")

        # 查找用户
        user, user_type = UserQueryHelper.find_user_by_identifier(account)

        if not user:
            print(f"【登录失败】用户不存在: {account}")
            return ResponseService.error('账号或密码错误', status_code=401)

        # 验证密码
        if not user.check_password(password):
            print(f"【登录失败】密码错误: {account}")
            return ResponseService.error('账号或密码错误', status_code=401)

        # 检查用户状态（仅普通用户需要检查）
        if user_type == 'user' and user.is_deleted == 1:
            print(f"【登录失败】用户已注销: {account}")
            return ResponseService.error('用户账号已注销', status_code=403)

        # 生成JWT token
        token_payload = {
            'user_id': user.id,
            'account': user.account,
            'role': 'admin' if user_type == 'admin' else 'user',
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow()
        }

        token = jwt.encode(
            token_payload,
            Config.JWT_SECRET_KEY,
            algorithm='HS256'
        )

        # 返回用户信息
        user_info = UserDataProcessor.format_user_info(user, include_sensitive=False)
        user_info.update({
            'user_type': user_type,
            'token': token
        })

        print(f"【登录成功】账号: {account}, 用户类型: {user_type}")

        return ResponseService.success(
            data=user_info,
            message="登录成功"
        )

    except Exception as e:
        print(f"【登录异常】错误: {str(e)}")
        return ResponseService.error(f'登录失败: {str(e)}', status_code=500)


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """刷新token接口"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return ResponseService.error('缺少有效的token', status_code=401)

        token = auth_header.split(' ')[1]

        try:
            payload = jwt.decode(
                token,
                Config.JWT_SECRET_KEY,
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            return ResponseService.error('token已过期，请重新登录', status_code=401)
        except jwt.InvalidTokenError:
            return ResponseService.error('token格式无效', status_code=401)

        # 查找用户
        user_id = payload['user_id']
        role = payload.get('role', 'user')

        if role == 'admin':
            user = Admin.query.get(user_id)
        else:
            user = User.query.get(user_id)

        if not user:
            return ResponseService.error('用户不存在', status_code=404)

        # 生成新token
        new_payload = {
            'user_id': user.id,
            'account': user.account,
            'role': role,
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow()
        }

        new_token = jwt.encode(
            new_payload,
            Config.JWT_SECRET_KEY,
            algorithm='HS256'
        )

        print(f"【token刷新成功】用户: {user.account}")

        return ResponseService.success(
            data={
                'token': new_token,
                'expires_in': 24 * 60 * 60
            },
            message="Token刷新成功"
        )

    except Exception as e:
        print(f"【token刷新异常】错误: {str(e)}")
        return ResponseService.error(f'token刷新失败: {str(e)}', status_code=500)


@auth_bp.route('/verify', methods=['POST'])
def verify_token():
    """验证token有效性接口"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return ResponseService.error('缺少token', status_code=401)

        token = auth_header.split(' ')[1]

        try:
            payload = jwt.decode(
                token,
                Config.JWT_SECRET_KEY,
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            return ResponseService.error('token已过期', status_code=401)
        except jwt.InvalidTokenError:
            return ResponseService.error('token格式无效', status_code=401)

        # 查找用户
        user_id = payload['user_id']
        role = payload.get('role', 'user')

        if role == 'admin':
            user = Admin.query.get(user_id)
        else:
            user = User.query.get(user_id)

        if not user:
            return ResponseService.error('用户不存在', status_code=404)

        # 检查用户状态
        if role == 'user' and user.is_deleted == 1:
            return ResponseService.error('用户账号已注销', status_code=403)

        user_info = UserDataProcessor.format_user_info(user, include_sensitive=False)
        user_info.update({
            'user_type': role,
            'token_valid': True,
            'expires_at': datetime.fromtimestamp(payload['exp']).isoformat().replace('+00:00', 'Z')
        })

        print(f"【token验证成功】用户: {user.account}")

        return ResponseService.success(
            data=user_info,
            message="Token验证成功"
        )

    except Exception as e:
        print(f"【token验证异常】错误: {str(e)}")
        return ResponseService.error(f'token验证失败: {str(e)}', status_code=500)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """用户登出接口"""
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                payload = jwt.decode(
                    token,
                    Config.JWT_SECRET_KEY,
                    algorithms=['HS256']
                )
                print(f"【用户登出】用户ID: {payload.get('user_id')}, 账号: {payload.get('account')}")
            except:
                pass

        return ResponseService.success(message="登出成功")

    except Exception as e:
        print(f"【登出异常】错误: {str(e)}")
        return ResponseService.error(f'登出失败: {str(e)}', status_code=500)


@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册接口"""
    try:
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        # 验证必填字段
        required_fields = ['account', 'password', 'username']
        validation_errors = validate_user_data(data, required_fields=required_fields)

        if validation_errors:
            return ResponseService.error(f'数据验证失败: {", ".join(validation_errors)}', status_code=400)

        account = data['account'].strip()
        password = data['password'].strip()
        username = data['username'].strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()

        print(f"【用户注册请求】账号: {account}")

        # 检查账号是否已存在
        existing_user = User.query.filter_by(account=account, is_deleted=0).first()
        if existing_user:
            return ResponseService.error('账号已存在', status_code=400)

        # 检查手机号是否已存在
        if phone:
            existing_phone = User.query.filter_by(phone=phone, is_deleted=0).first()
            if existing_phone:
                return ResponseService.error('手机号已被使用', status_code=400)

        # 检查用户名是否已存在
        existing_username = User.query.filter_by(username=username, is_deleted=0).first()
        if existing_username:
            return ResponseService.error('用户名已被使用', status_code=400)

        # 创建新用户
        new_user = User(
            account=account,
            username=username,
            phone=phone,
            email=email,
            role='USER',
            is_deleted=0
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        print(f"【用户注册成功】账号: {account}, 用户ID: {new_user.id}")

        user_info = UserDataProcessor.format_user_info(new_user, include_sensitive=False)

        return ResponseService.success(
            data=user_info,
            message="注册成功"
        )

    except Exception as e:
        db.session.rollback()
        print(f"【用户注册异常】错误: {str(e)}")
        return ResponseService.error(f'注册失败: {str(e)}', status_code=500)


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """修改密码接口"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return ResponseService.error('需要登录', status_code=401)

        token = auth_header.split(' ')[1]

        try:
            payload = jwt.decode(
                token,
                Config.JWT_SECRET_KEY,
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            return ResponseService.error('登录已过期，请重新登录', status_code=401)
        except jwt.InvalidTokenError:
            return ResponseService.error('登录状态无效', status_code=401)

        # 查找用户
        user_id = payload['user_id']
        role = payload.get('role', 'user')

        if role == 'admin':
            user = Admin.query.get(user_id)
        else:
            user = User.query.get(user_id)

        if not user:
            return ResponseService.error('用户不存在', status_code=404)

        # 获取请求数据
        data = request.get_json()
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        old_password = data.get('old_password', '').strip()
        new_password = data.get('new_password', '').strip()

        if not old_password or not new_password:
            return ResponseService.error('旧密码和新密码不能为空', status_code=400)

        # 验证新密码格式
        is_valid, msg = UserValidator.validate_password(new_password)
        if not is_valid:
            return ResponseService.error(msg, status_code=400)

        # 验证旧密码
        if not user.check_password(old_password):
            print(f"【修改密码失败】旧密码错误: {user.account}")
            return ResponseService.error('原密码错误', status_code=400)

        # 设置新密码
        user.set_password(new_password)
        db.session.commit()

        print(f"【密码修改成功】用户: {user.account}")

        return ResponseService.success(message="密码修改成功")

    except Exception as e:
        db.session.rollback()
        print(f"【修改密码异常】错误: {str(e)}")
        return ResponseService.error(f'密码修改失败: {str(e)}', status_code=500)


# ============================================================
# 用户端个人信息路由 (user/profile.py)
# ============================================================

@user_bp.route('/user/info', methods=['GET'])
@token_required
@handle_api_exception
def get_current_user_info(current_user):
    """获取当前登录用户的详细信息"""
    print(f"【查询当前用户信息】用户: {current_user.account}")

    # 使用通用服务获取当前用户信息（包含敏感信息）
    user_info = UserInfoService.get_current_user_info(current_user, include_sensitive=True)

    if not user_info:
        return ResponseService.error('用户信息不存在', status_code=404)

    print(f"【当前用户信息查询成功】用户: {current_user.account}, 用户类型: {user_info['user_type']}")
    return ResponseService.success(data=user_info, message="用户信息查询成功")


@user_bp.route('/user/info/<account>', methods=['GET'])
@token_required
@handle_api_exception
def get_user_info_by_account(current_user, account):
    """获取指定用户的基础信息（不包含敏感信息）"""
    print(f"【查询指定用户信息】查询者: {current_user.account}, 目标账号: {account}")

    # 使用通用服务获取用户信息（不包含敏感信息）
    user_info = UserInfoService.get_user_by_account(account, include_sensitive=False)

    if not user_info:
        return ResponseService.error('用户不存在', status_code=404)

    print(f"【指定用户信息查询成功】目标用户: {account}, 用户类型: {user_info['user_type']}")
    return ResponseService.success(data=user_info, message="用户信息查询成功")


@user_bp.route('/user/update', methods=['POST'])
@token_required
@handle_api_exception
def update_user_info(current_user):
    """更新用户个人信息（用户权限）"""
    data = request.get_json()

    # 验证必要参数
    if not data:
        return ResponseService.error('请求数据不能为空', status_code=400)

    update_data = data.get('update_data', {})
    if not update_data:
        return ResponseService.error('缺少更新内容：update_data', status_code=400)

    # 验证更新数据的字段
    valid_fields = ['username', 'phone', 'email', 'avatar', 'password']
    invalid_fields = [field for field in update_data.keys() if field not in valid_fields]
    if invalid_fields:
        return ResponseService.error(f'不支持的更新字段: {", ".join(invalid_fields)}', status_code=400)

    # 确定目标用户和权限
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

    # 禁止修改账号
    update_data.pop('account', None)

    # 验证更新数据的格式
    validation_errors = validate_user_data(update_data, optional_fields=['username', 'phone', 'email'])
    if validation_errors:
        return ResponseService.error(f'数据验证失败: {", ".join(validation_errors)}', status_code=400)

    # 处理头像更新
    if 'avatar' in update_data:
        new_avatar = update_data['avatar']
        if new_avatar is None or new_avatar.strip() == '':
            # 删除头像
            if target_user.avatar:
                filename = target_user.avatar.split('/')[-1]
                LocalImageStorage().delete_image(filename)
                print(f"【删除头像】用户: {target_user.account}, 文件: {filename}")
        else:
            # 更新头像，先删除旧头像
            if target_user.avatar:
                filename = target_user.avatar.split('/')[-1]
                LocalImageStorage().delete_image(filename)
                print(f"【更新头像】用户: {target_user.account}, 删除旧头像: {filename}")

    # 处理密码更新
    if 'password' in update_data:
        new_password = update_data.pop('password')
        if new_password and new_password.strip():
            target_user.set_password(new_password)
            print(f"【更新密码】用户: {target_user.account} 的密码已更新")

    # 处理用户名和手机号唯一性检查
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

    # 执行更新
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
    """获取用户相关的活动记录"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        activity_type = request.args.get('type', 'all')  # all, published, booked

        # 查询用户发布的活动
        published_activities = []
        if activity_type in ['all', 'published']:
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

        # 查询用户预约的活动
        booked_activities = []
        if activity_type in ['all', 'booked']:
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

        # 合并结果
        all_activities = published_activities + booked_activities
        # 按时间排序
        all_activities.sort(key=lambda x: x.get('start_time', x.get('booking_time')), reverse=True)

        result_data = {
            'total': len(all_activities),
            'page': page,
            'size': size,
            'items': all_activities[:size]  # 分页返回
        }

        return ResponseService.success(data=result_data, message="用户活动记录查询成功")

    except Exception as e:
        print(f"【用户活动记录查询异常】错误: {str(e)}")
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@user_bp.route('/user/activities/stats', methods=['GET'])
@token_required
def get_user_activities_stats(current_user):
    """获取当前用户相关活动统计"""
    try:
        from sqlalchemy import func

        # 用户发布的活动统计
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

        # 用户参与/预约统计
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
    """用户注销账号接口"""
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

        # 查找用户记录
        user = User.query.filter_by(account=current_user.account, is_deleted=0).first()
        if not user:
            return ResponseService.error('用户不存在或已注销', status_code=404)

        # 验证密码
        if not user.check_password(password):
            return ResponseService.error('密码错误，无法注销账号', status_code=400)

        print(f"【用户注销请求】用户: {current_user.account}")

        # 执行软删除
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


# ============================================================
# 用户端头像管理路由 (user/auth.py)
# ============================================================

@user_bp.route('/user/avatar', methods=['POST'])
@token_required
def upload_avatar(current_user):
    """用户头像上传接口"""
    try:
        print(f"【头像上传请求】用户: {current_user.account}")
        avatar_file = request.files.get('avatar')

        if not avatar_file:
            return ResponseService.error('缺少头像文件', status_code=400)

        # 确定当前用户类型和记录
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
            return ResponseService.error('用户信息不存在', status_code=404)

        # 删除旧头像
        if target_user.avatar:
            old_filename = target_user.avatar.split('/')[-1]
            LocalImageStorage().delete_image(old_filename)
            print(f"【上传新头像】删除旧头像：{old_filename}")

        # 保存新头像
        image_storage = LocalImageStorage()
        save_result = image_storage.save_image(avatar_file)

        if save_result['status'] != 'success':
            return ResponseService.error(f'图片上传失败：{save_result["message"]}', status_code=400)

        # 更新头像URL
        target_user.avatar = save_result['url']
        db.session.commit()

        print(f"【头像上传成功】用户: {current_user.account}, 新头像URL: {save_result['url']}")

        return ResponseService.success(
            data={
                'avatar_url': save_result['url'],
                'filename': save_result['filename']
            },
            message='头像上传成功（旧头像已删除）'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【头像上传异常】错误: {str(e)}")
        return ResponseService.error(f'头像上传失败：{str(e)}', status_code=500)


@user_bp.route('/user/avatar', methods=['DELETE'])
@token_required
def delete_avatar(current_user):
    """删除用户头像接口"""
    try:
        print(f"【头像删除请求】用户: {current_user.account}")

        # 确定当前用户类型和记录
        target_user = None

        target_user = User.query.filter_by(account=current_user.account).first()
        if not target_user:
            target_user = Admin.query.filter_by(account=current_user.account).first()

        if not target_user:
            return ResponseService.error('用户信息不存在', status_code=404)

        # 删除头像文件和数据库记录
        if target_user.avatar:
            filename = target_user.avatar.split('/')[-1]
            LocalImageStorage().delete_image(filename)
            print(f"【删除头像文件】用户: {target_user.account}, 文件: {filename}")

            target_user.avatar = None
            db.session.commit()

        return ResponseService.success(message='头像删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【头像删除异常】错误: {str(e)}")
        return ResponseService.error(f'头像删除失败：{str(e)}', status_code=500)


# ============================================================
# 用户信息公开访问路由 (user/public.py)
# ============================================================

@bp_user_public.route('/info', methods=['GET'])
def get_public_user_info():
    """获取用户基础信息（公开接口，无需认证）"""
    try:
        # 获取用户账号参数
        account = request.args.get('account')
        if not account or not account.strip():
            return ResponseService.error('缺少参数：account', status_code=400)

        account = account.strip()

        # 查询目标用户（支持管理员和普通用户）
        target_user = None
        user_type = None

        # 先查普通用户表
        target_user = User.query.filter_by(account=account, is_deleted=0).first()
        if target_user:
            user_type = 'user'
        else:
            # 再查管理员表
            target_user = Admin.query.filter_by(account=account).first()
            if target_user:
                user_type = 'admin'

        if not target_user:
            return ResponseService.error('用户不存在', status_code=404)

        # 返回公开的基础信息（不包含敏感信息如电话、邮箱等）
        user_info = {
            'id': target_user.id,
            'account': target_user.account,
            'username': target_user.username,
            'avatar': target_user.avatar,
            'role': getattr(target_user, 'role', 'USER'),
            'user_type': user_type
        }

        # 角色中文显示
        if user_type == 'admin':
            role_mapping = {'SUPER_ADMIN': '超级管理员', 'ADMIN': '管理员', 'USER': '管理员用户'}
            user_info['role_cn'] = role_mapping.get(getattr(target_user, 'role', 'USER'), '未知角色')
        else:
            role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户', 'ADMIN': '管理员用户'}
            user_info['role_cn'] = role_mapping.get(getattr(target_user, 'role', 'USER'), '未知角色')

        return ResponseService.success(data=user_info, message="用户信息查询成功")

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)


@bp_user_public.route('/info/batch', methods=['POST'])
def get_batch_public_user_info():
    """批量获取用户基础信息（公开接口，无需认证）"""
    try:
        data = request.get_json()
        if not data or 'accounts' not in data:
            return ResponseService.error('缺少参数：accounts', status_code=400)

        accounts = data.get('accounts', [])
        if not isinstance(accounts, list):
            return ResponseService.error('accounts参数必须是数组', status_code=400)

        if not accounts:
            return ResponseService.success(data=[], message="用户列表为空")

        # 去重
        accounts = list(set(account.strip() for account in accounts if account.strip()))

        result = []
        for account in accounts:
            # 查询目标用户
            target_user = None
            user_type = None

            # 先查普通用户表
            target_user = User.query.filter_by(account=account, is_deleted=0).first()
            if target_user:
                user_type = 'user'
            else:
                # 再查管理员表
                target_user = Admin.query.filter_by(account=account).first()
                if target_user:
                    user_type = 'admin'

            if target_user:
                user_info = {
                    'id': target_user.id,
                    'account': target_user.account,
                    'username': target_user.username,
                    'avatar': target_user.avatar,
                    'role': getattr(target_user, 'role', 'USER'),
                    'user_type': user_type
                }

                # 角色中文显示
                if user_type == 'admin':
                    role_mapping = {'SUPER_ADMIN': '超级管理员', 'ADMIN': '管理员', 'USER': '管理员用户'}
                    user_info['role_cn'] = role_mapping.get(getattr(target_user, 'role', 'USER'), '未知角色')
                else:
                    role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户', 'ADMIN': '管理员用户'}
                    user_info['role_cn'] = role_mapping.get(getattr(target_user, 'role', 'USER'), '未知角色')

                result.append(user_info)

        return ResponseService.success(data=result, message=f"批量查询成功，找到 {len(result)} 个用户")

    except Exception as e:
        return ResponseService.error(f'批量查询失败：{str(e)}', status_code=500)


@bp_user_public.route('/statistics', methods=['GET'])
def get_public_user_statistics():
    """获取用户统计信息（公开接口，无需登录）"""
    try:
        from sqlalchemy import func, case

        # 普通用户统计
        user_stats = db.session.query(
            func.count(User.id).label('total_users'),
            func.sum(case((User.is_deleted == 0, 1), else_=0)).label('active_users'),
            func.sum(case((User.is_deleted == 1, 1), else_=0)).label('deleted_users')
        ).first()

        # 管理员统计
        admin_stats = db.session.query(
            func.count(Admin.id).label('total_admins'),
            func.sum(case((Admin.role == 'SUPER_ADMIN', 1), else_=0)).label('super_admins'),
            func.sum(case((Admin.role == 'ADMIN', 1), else_=0)).label('regular_admins')
        ).first()

        statistics = {
            'user_statistics': {
                'total_users': int(user_stats.total_users or 0),
                'active_users': int(user_stats.active_users or 0),
                'deleted_users': int(user_stats.deleted_users or 0)
            },
            'admin_statistics': {
                'total_admins': int(admin_stats.total_admins or 0),
                'super_admins': int(admin_stats.super_admins or 0),
                'regular_admins': int(admin_stats.regular_admins or 0)
            }
        }

        return ResponseService.success(data=statistics, message="用户统计查询成功")

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)


# ============================================================
# 管理员用户管理路由 (admin/user_manage.py)
# ============================================================

@admin_bp.route('/admins', methods=['GET'])
@token_required
@admin_required
@handle_api_exception
def get_admin_list(current_user):
    """获取管理员列表"""
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
    """用户信息管理接口"""
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
    """降级单个管理员为普通用户"""
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
    """创建管理员账号"""
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
    """获取用户统计信息"""
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


# ============================================================
# 注册子模块 Blueprint 到主模块
# ============================================================

api_user_bp.register_blueprint(user_bp)
api_user_bp.register_blueprint(admin_bp)
api_user_bp.register_blueprint(auth_bp)


# ============================================================
# 导出接口
# ============================================================

__all__ = [
    'api_user_bp',
    'user_bp',
    'admin_bp',
    'auth_bp',
    'bp_user_public',
    'UserValidator',
    'UserPermissionChecker',
    'UserDataProcessor',
    'UserQueryHelper',
    'validate_user_data',
    'admin_required',
    'super_admin_required'
]


print("【API_user 统一路由模块加载完成】已整合所有子模块功能")
