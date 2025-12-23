# 测试专用的token_required Mock
# 用于在测试环境中完全绕过JWT验证

from functools import wraps
from flask import request

def mock_token_required(f):
    """
    测试专用的token_required装饰器Mock
    在测试环境中完全绕过JWT验证
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 从请求头获取mock用户信息
        from unittest.mock import Mock

        mock_user = Mock()
        mock_user.id = 1
        mock_user.account = "testuser"
        mock_user.username = "测试用户"
        mock_user.role = "user"
        mock_user.is_deleted = 0

        # 如果请求头中包含管理员信息，创建管理员Mock
        if hasattr(request, 'headers') and request.headers.get('X-Test-Role') == 'admin':
            mock_admin = Mock()
            mock_admin.id = 1
            mock_admin.account = "testadmin"
            mock_admin.username = "测试管理员"
            mock_admin.role = "admin"
            mock_admin.is_deleted = 0
            return f(mock_admin, *args, **kwargs)

        return f(mock_user, *args, **kwargs)
    return decorated

def mock_admin_token_required(f):
    """
    测试专用的管理员token_required装饰器Mock
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from unittest.mock import Mock

        mock_admin = Mock()
        mock_admin.id = 1
        mock_admin.account = "testadmin"
        mock_admin.username = "测试管理员"
        mock_admin.role = "admin"
        mock_admin.is_deleted = 0

        return f(mock_admin, *args, **kwargs)
    return decorated