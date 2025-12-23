# ./components/__init__.py

from components.models import db, compat_session
from components.token_required import token_required
from components.permissions import (
    require_permission, user_required, admin_required,
    super_admin_required, visit_required, or_permission,
    USER_PERMISSIONS, ADMIN_PERMISSIONS, VISIT_PERMISSIONS, ALL_PERMISSIONS,
    has_permission, is_admin, is_user, get_permission_level, can_manage_role,
    check_table_permission, get_permission_description
)
from components.image_storage import LocalImageStorage

# 导出公共对象供其他模块使用
__all__ = [
    'db', 'compat_session', 'token_required', 'LocalImageStorage',
    # 新权限系统
    'require_permission', 'user_required', 'admin_required',
    'super_admin_required', 'visit_required', 'or_permission',
    'USER_PERMISSIONS', 'ADMIN_PERMISSIONS', 'VISIT_PERMISSIONS', 'ALL_PERMISSIONS',
    'has_permission', 'is_admin', 'is_user', 'get_permission_level', 'can_manage_role',
    'check_table_permission', 'get_permission_description'
]