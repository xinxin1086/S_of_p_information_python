# tests/test_helpers.py
# 测试辅助工具模块

from functools import wraps
from unittest.mock import Mock


class MockTokenRequired:
    """Mock token_required装饰器"""

    @staticmethod
    def create_mock_decorator(mock_user=None):
        """创建Mock装饰器"""
        def mock_decorator(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                if mock_user:
                    return f(mock_user, *args, **kwargs)
                else:
                    # 如果没有提供mock_user，创建一个默认的
                    default_user = Mock()
                    default_user.id = 1
                    default_user.account = "test_user"
                    default_user.username = "测试用户"
                    default_user.role = "USER"
                    return f(default_user, *args, **kwargs)
            return decorated
        return mock_decorator


class MockDateTime:
    """Mock datetime对象，避免类型比较问题"""

    @staticmethod
    def create_mock_datetime(year=2024, month=1, day=1, hour=12, minute=0, second=0):
        """创建Mock datetime对象"""
        mock_dt = Mock()
        mock_dt.year = year
        mock_dt.month = month
        mock_dt.day = day
        mock_dt.hour = hour
        mock_dt.minute = minute
        mock_dt.second = second

        # 添加比较方法
        def mock_ge(other):
            if hasattr(other, 'year'):
                return (mock_dt.year, mock_dt.month, mock_dt.day, mock_dt.hour, mock_dt.minute, mock_dt.second) >= \
                       (other.year, other.month, other.day, other.hour, other.minute, other.second)
            return False

        def mock_le(other):
            if hasattr(other, 'year'):
                return (mock_dt.year, mock_dt.month, mock_dt.day, mock_dt.hour, mock_dt.minute, mock_dt.second) <= \
                       (other.year, other.month, other.day, other.hour, other.minute, other.second)
            return False

        mock_dt.__ge__ = mock_ge
        mock_dt.__le__ = mock_le

        return mock_dt


# 全局Mock装饰器实例
mock_token_required = MockTokenRequired.create_mock_decorator()