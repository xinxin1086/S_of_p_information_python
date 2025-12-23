# 测试应用配置

"""
测试专用的Flask应用配置
避免在测试中直接使用SQLAlchemy模型类的query属性
"""

import pytest
from flask import Flask
from unittest.mock import Mock

def create_test_app():
    """创建测试应用"""
    app = Flask(__name__)

    # 测试配置
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 避免初始化数据库，只提供基本配置
    return app

@pytest.fixture
def test_app():
    """测试应用fixture"""
    return create_test_app()

@pytest.fixture
def test_client(test_app):
    """测试客户端fixture"""
    return test_app.test_client()

# 安全的Mock对象创建，避免SQLAlchemy上下文问题
def create_safe_mock(model_name):
    """创建安全的Mock对象，避免触发SQLAlchemy"""
    mock = Mock()

    # 根据模型类型设置默认属性
    if model_name == 'User':
        mock.id = 1
        mock.account = 'testuser'
        mock.username = '测试用户'
        mock.role = 'USER'
        mock.is_deleted = 0

    elif model_name == 'Admin':
        mock.id = 1
        mock.account = 'testadmin'
        mock.username = '测试管理员'
        mock.role = 'ADMIN'

    elif model_name == 'Activity':
        mock.id = 1
        mock.title = '测试活动'
        mock.description = '这是一个测试活动'
        mock.location = '测试地点'
        mock.max_participants = 10
        mock.status = 'published'
        mock.organizer_user_id = 1

    elif model_name == 'ActivityBooking':
        mock.id = 1
        mock.activity_id = 1
        mock.user_account = 'testuser'
        mock.status = 'booked'

    elif model_name == 'Notice':
        mock.id = 1
        mock.title = '测试公告'
        mock.content = '这是测试公告内容'
        mock.status = 'APPROVED'

    return mock

# 测试数据常量
TEST_USER_DATA = {
    'account': 'testuser',
    'username': '测试用户',
    'password': 'testpass123'
}

TEST_ADMIN_DATA = {
    'account': 'testadmin',
    'username': '测试管理员',
    'password': 'adminpass123'
}

TEST_ACTIVITY_DATA = {
    'title': '测试活动',
    'description': '这是一个测试活动',
    'location': '测试地点',
    'start_time': '2024-12-15T10:00:00Z',
    'end_time': '2024-12-15T12:00:00Z',
    'max_participants': 10
}