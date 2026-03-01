
import re
from functools import wraps
from flask import request, jsonify
from components.response_service import ResponseService

class UserValidator:
    

    @staticmethod
    def validate_email(email):
        
        if not email:
            return True
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_phone(phone):
        
        if not phone:
            return True
        pattern = r'^1[3-9]\d{9}$'
        return re.match(pattern, phone) is not None

    @staticmethod
    def validate_password(password):
        
        if not password:
            return False, "密码不能为空"
        if len(password) < 6 or len(password) > 20:
            return False, "密码长度应在6-20个字符之间"
        return True, "密码格式正确"

    @staticmethod
    def validate_username(username):
        
        if not username or not username.strip():
            return False, "用户名不能为空"
        if len(username.strip()) < 2 or len(username.strip()) > 20:
            return False, "用户名长度应在2-20个字符之间"
        return True, "用户名格式正确"

class UserPermissionChecker:
    

    @staticmethod
    def is_admin_user(current_user):
        
        return hasattr(current_user, 'role') and current_user.role in ['ADMIN', 'SUPER_ADMIN']

    @staticmethod
    def is_super_admin(current_user):
        
        return hasattr(current_user, 'role') and current_user.role == 'SUPER_ADMIN'

    @staticmethod
    def can_manage_user(current_user, target_user):
        
        if UserPermissionChecker.is_super_admin(current_user):
            return True

        if UserPermissionChecker.is_admin_user(current_user):
            return not UserPermissionChecker.is_admin_user(target_user)

        return False

def admin_required(f):
    
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = args[0]

        if not UserPermissionChecker.is_admin_user(current_user):
            return ResponseService.error('权限不足，需要管理员权限', status_code=403)

        return f(*args, **kwargs)
    return decorated

def super_admin_required(f):
    
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = args[0]

        if not UserPermissionChecker.is_super_admin(current_user):
            return ResponseService.error('权限不足，需要超级管理员权限', status_code=403)

        return f(*args, **kwargs)
    return decorated

class UserDataProcessor:
    

    @staticmethod
    def format_user_info(user, include_sensitive=False):
        
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
        
        if allowed_fields is None:
            allowed_fields = ['username', 'phone', 'email', 'avatar', 'password']

        return {k: v for k, v in data.items() if k in allowed_fields}

class UserQueryHelper:
    @staticmethod
    def find_user_by_account(account):
        from components.models.user_models import User, Admin

        admin = Admin.query.filter_by(account=account).first()
        if admin:
            return admin, 'admin'

        user = User.query.filter_by(account=account, is_deleted=0).first()
        if user:
            return user, 'user'

        return None, None

    @staticmethod
    def find_user_by_identifier(identifier):
        from components.models.user_models import User, Admin

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
    
    errors = []
    validator = UserValidator()

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

print("【API_user 公共工具模块加载完成】")