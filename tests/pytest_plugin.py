# pytest插件配置
# 确保全局Mock管理器正确工作

def pytest_configure(config):
    """pytest配置钩子 - 在所有测试开始前运行"""
    from .conftest_mock_manager import global_mock_manager

    # 设置全局Mock
    global_mock_manager.setup_token_mock()

def pytest_unconfigure(config):
    """pytest清理钩子 - 在所有测试结束后运行"""
    from .conftest_mock_manager import global_mock_manager

    # 清理全局Mock
    global_mock_manager.cleanup_token_mock()

# 确保在每个测试会话开始时都重新设置Mock
def pytest_sessionstart(session):
    """测试会话开始钩子"""
    from .conftest_mock_manager import global_mock_manager

    # 重新设置Mock，确保干净的状态
    global_mock_manager.cleanup_token_mock()
    global_mock_manager.setup_token_mock()