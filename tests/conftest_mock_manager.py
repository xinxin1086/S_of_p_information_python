# 全局Mock管理器
# 用于管理测试环境中的Mock，避免模块单独测试时的冲突

import sys
from unittest.mock import MagicMock

class GlobalMockManager:
    """全局Mock管理器"""

    def __init__(self):
        self.original_modules = {}
        self.mock_active = False

    def setup_token_mock(self):
        """设置token_required的Mock"""
        if self.mock_active:
            return  # 避免重复设置

        # 保存原始模块引用
        if 'components.token_required' in sys.modules:
            self.original_modules['components.token_required'] = sys.modules['components.token_required']

        # 创建Mock模块
        mock_module = MagicMock()

        # 导入并应用我们的Mock实现
        try:
            from tests.mock_token_required import mock_token_required
            mock_module.token_required = mock_token_required

            # 替换模块
            sys.modules['components.token_required'] = mock_module
            self.mock_active = True

        except ImportError:
            # 如果导入失败，创建一个简单的Mock
            def simple_mock_token_required(f):
                from unittest.mock import Mock
                def wrapper(*args, **kwargs):
                    mock_user = Mock()
                    mock_user.id = 1
                    mock_user.account = "testuser"
                    mock_user.username = "测试用户"
                    mock_user.role = "user"
                    mock_user.is_deleted = 0
                    return f(mock_user, *args, **kwargs)
                return wrapper
            mock_module.token_required = simple_mock_token_required
            sys.modules['components.token_required'] = mock_module
            self.mock_active = True

    def cleanup_token_mock(self):
        """清理token_required的Mock"""
        if not self.mock_active:
            return

        # 恢复原始模块
        if 'components.token_required' in self.original_modules:
            sys.modules['components.token_required'] = self.original_modules['components.token_required']
        elif 'components.token_required' in sys.modules:
            del sys.modules['components.token_required']

        self.mock_active = False

# 全局Mock管理器实例
global_mock_manager = GlobalMockManager()

# pytest的配置函数
def pytest_configure(config):
    """pytest配置钩子"""
    # 在所有测试开始前设置Mock
    global_mock_manager.setup_token_mock()

def pytest_unconfigure(config):
    """pytest清理钩子"""
    # 在所有测试结束后清理Mock
    global_mock_manager.cleanup_token_mock()