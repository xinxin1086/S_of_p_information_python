# API_user 认证授权接口
# 基于 components/token_required.py 的认证功能

import jwt
from datetime import datetime, timedelta
from flask import request, jsonify
from components import db
from components.models import Admin, User
from components.response_service import ResponseService
from config import Config
from . import auth_bp
from ..common.utils import UserQueryHelper, validate_user_data

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录接口
    支持用户和管理员登录
    返回JWT token和用户信息
    """
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
            'exp': datetime.utcnow() + timedelta(hours=24),  # 24小时过期
            'iat': datetime.utcnow()
        }

        token = jwt.encode(
            token_payload,
            Config.JWT_SECRET_KEY,
            algorithm='HS256'
        )

        # 返回用户信息
        from ..common.utils import UserDataProcessor
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
    """
    刷新token接口
    需要有效的token，返回新的token
    """
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return ResponseService.error('缺少有效的token', status_code=401)

        token = auth_header.split(' ')[1]

        try:
            # 验证当前token
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
                'expires_in': 24 * 60 * 60  # 24小时（秒）
            },
            message="Token刷新成功"
        )

    except Exception as e:
        print(f"【token刷新异常】错误: {str(e)}")
        return ResponseService.error(f'token刷新失败: {str(e)}', status_code=500)

@auth_bp.route('/verify', methods=['POST'])
def verify_token():
    """
    验证token有效性接口
    返回token对应的用户信息
    """
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

        from ..common.utils import UserDataProcessor
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
    """
    用户登出接口
    实际上JWT是无状态的，客户端删除token即可完成登出
    """
    try:
        # 获取token进行记录
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
                pass  # token无效也无所谓，登出操作不依赖token有效性

        return ResponseService.success(message="登出成功")

    except Exception as e:
        print(f"【登出异常】错误: {str(e)}")
        return ResponseService.error(f'登出失败: {str(e)}', status_code=500)

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    用户注册接口
    仅支持普通用户注册，管理员需要后台创建
    """
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

        # 返回用户信息（不包含敏感信息）
        from ..common.utils import UserDataProcessor
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
    """
    修改密码接口
    支持用户和管理员修改自己的密码
    需要提供旧密码进行验证
    """
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
        from ..common.utils import UserValidator
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

print("【API_user 认证授权接口模块加载完成】")