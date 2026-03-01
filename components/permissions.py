
from functools import wraps
from flask import jsonify, request
import jwt
from datetime import datetime
from config import Config

PERMISSION_VISIT = 'visit'
PERMISSION_USER = 'USER'
PERMISSION_ORG_USER = 'ORG_USER'
PERMISSION_ADMIN = 'ADMIN'
PERMISSION_SUPER_ADMIN = 'SUPER_ADMIN'

VISIT_PERMISSIONS = [PERMISSION_VISIT]
USER_PERMISSIONS = [PERMISSION_USER, PERMISSION_ORG_USER]
ADMIN_PERMISSIONS = [PERMISSION_ADMIN, PERMISSION_SUPER_ADMIN]
ALL_PERMISSIONS = [PERMISSION_USER, PERMISSION_ORG_USER, PERMISSION_ADMIN, PERMISSION_SUPER_ADMIN]


class PermissionError(Exception):
    
    pass


def extract_token_info(request):
    
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None

    try:
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        else:
            token = auth_header

        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])

        if datetime.utcnow().timestamp() > payload.get('exp', 0):
            return None

        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


def get_user_from_token(token_info):
    
    if not token_info:
        return None, None

    try:
        from components.models import User, Admin

        user_id = token_info.get('user_id')
        role = token_info.get('role')

        if role in [PERMISSION_ADMIN, PERMISSION_SUPER_ADMIN]:
            admin = Admin.query.get(user_id)
            if admin:
                return admin, 'admin'

        user = User.query.get(user_id)
        if user:
            return user, 'user'

        return None, None
    except Exception:
        return None, None


def require_permission(required_permissions):
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if PERMISSION_VISIT in required_permissions:
                return f(*args, **kwargs)

            token_info = extract_token_info(request)
            if not token_info:
                return jsonify({
                    'success': False,
                    'message': '需要登录访问此接口',
                    'data': None
                }), 401

            user, user_type = get_user_from_token(token_info)
            if not user:
                return jsonify({
                    'success': False,
                    'message': '用户不存在或已被删除',
                    'data': None
                }), 401

            user_role = getattr(user, 'role', PERMISSION_USER)

            if user_type == 'user' and hasattr(user, 'is_deleted') and user.is_deleted:
                return jsonify({
                    'success': False,
                    'message': '用户已被注销',
                    'data': None
                }), 401

            if user_role not in required_permissions:
                return jsonify({
                    'success': False,
                    'message': '权限不足，无法访问此接口',
                    'data': {
                        'required_permissions': required_permissions,
                        'user_role': user_role
                    }
                }), 403

            kwargs['current_user'] = user
            kwargs['user_type'] = user_type
            kwargs['token_info'] = token_info

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def visit_required(f):
    
    return require_permission(VISIT_PERMISSIONS)(f)


def user_required(f):
    
    return require_permission(USER_PERMISSIONS)(f)


def admin_required(f):
    
    return require_permission(ADMIN_PERMISSIONS)(f)


def super_admin_required(f):
    
    return require_permission([PERMISSION_SUPER_ADMIN])(f)


def or_permission(*permission_lists):
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token_info = extract_token_info(request)
            if not token_info:
                return jsonify({
                    'success': False,
                    'message': '需要登录访问此接口',
                    'data': None
                }), 401

            user, user_type = get_user_from_token(token_info)
            if not user:
                return jsonify({
                    'success': False,
                    'message': '用户不存在或已被删除',
                    'data': None
                }), 401

            user_role = getattr(user, 'role', PERMISSION_USER)

            if user_type == 'user' and hasattr(user, 'is_deleted') and user.is_deleted:
                return jsonify({
                    'success': False,
                    'message': '用户已被注销',
                    'data': None
                }), 401

            for permission_list in permission_lists:
                if user_role in permission_list:
                    kwargs['current_user'] = user
                    kwargs['user_type'] = user_type
                    kwargs['token_info'] = token_info
                    return f(*args, **kwargs)

            return jsonify({
                'success': False,
                'message': '权限不足，无法访问此接口',
                'data': {
                    'user_role': user_role,
                    'allowed_permissions': permission_lists
                }
            }), 403

        return decorated_function
    return decorator


def has_permission(user_role, required_permissions):
    
    return user_role in required_permissions


def is_admin(user_role):
    
    return user_role in ADMIN_PERMISSIONS


def is_user(user_role):
    
    return user_role in USER_PERMISSIONS


def get_permission_level(role):
    
    permission_levels = {
        PERMISSION_VISIT: 0,
        PERMISSION_USER: 1,
        PERMISSION_ORG_USER: 1,
        PERMISSION_ADMIN: 2,
        PERMISSION_SUPER_ADMIN: 3
    }
    return permission_levels.get(role, 0)


def can_manage_role(manager_role, target_role):
    
    manager_level = get_permission_level(manager_role)
    target_level = get_permission_level(target_role)
    return manager_level > target_level


def check_table_permission(table_name, operate_type, user_role):
    
    if user_role == PERMISSION_SUPER_ADMIN:
        return True

    if user_role == PERMISSION_ADMIN:
        allowed_tables = ['user_info', 'science_articles', 'activities', 'notice', 'forum_posts', 'forum_comments']
        no_delete_tables = ['user_info']

        if table_name not in allowed_tables:
            return False

        if operate_type == 'delete' and table_name in no_delete_tables:
            return False

        return True

    return False


def get_permission_description():
    
    return {
        PERMISSION_SUPER_ADMIN: {
            'level': 3,
            'description': '超级管理员，拥有所有权限',
            'permissions': ['user_management', 'admin_management', 'content_management', 'system_operations', 'table_management']
        },
        PERMISSION_ADMIN: {
            'level': 2,
            'description': '普通管理员，拥有部分权限',
            'permissions': ['user_view_edit', 'content_management', 'limited_operations', 'limited_table_management']
        },
        PERMISSION_ORG_USER: {
            'level': 1,
            'description': '组织用户，拥有普通用户权限和组织相关权限',
            'permissions': ['basic_operations', 'content_creation', 'organization_features']
        },
        PERMISSION_USER: {
            'level': 1,
            'description': '普通用户，拥有基础权限',
            'permissions': ['basic_operations', 'content_creation']
        },
        PERMISSION_VISIT: {
            'level': 0,
            'description': '访客权限，只能访问公开内容',
            'permissions': ['public_view']
        }
    }