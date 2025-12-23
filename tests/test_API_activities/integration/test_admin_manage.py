# API_activities 管理员接口集成测试

import pytest
import json
from datetime import datetime, timedelta
from flask import Flask
from unittest.mock import patch, Mock

from API_activities.admin.activity_manage import admin_manage_bp
from components.models import Activity, ActivityBooking, ActivityRating, User
from components.response_service import ResponseService
from tests.test_helpers import MockDateTime

# token_required已经被全局Mock管理器处理，无需在此文件中重复设置


@pytest.fixture
def app():
    """创建测试应用"""
    from app import create_app

    # 创建测试配置
    class TestConfig:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SECRET_KEY = 'test_secret_key'
        JWT_SECRET_KEY = 'test_secret_key'
        WTF_CSRF_ENABLED = False

    app = create_app(TestConfig())
    # 不要重复注册蓝图，create_app已经注册了所有蓝图

    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


@pytest.fixture
def mock_admin_user():
    """Mock管理员用户对象"""
    user = Mock()
    user.id = 1
    user.account = "admin"
    user.username = "管理员"
    return user


@pytest.fixture
def mock_activity():
    """Mock活动对象"""
    activity = Mock()
    activity.id = 1
    activity.title = "测试活动"
    activity.description = "这是一个测试活动"
    activity.location = "测试地点"
    activity.start_time = MockDateTime.create_mock_datetime(2024, 1, 2, 10, 0, 0)
    activity.end_time = MockDateTime.create_mock_datetime(2024, 1, 3, 10, 0, 0)
    activity.max_participants = 10
    activity.status = "draft"
    activity.organizer_user_id = 1
    activity.organizer_display = "管理员"
    activity.tags = ["测试"]
    activity.created_at = MockDateTime.create_mock_datetime(2024, 1, 1, 10, 0, 0)
    activity.updated_at = MockDateTime.create_mock_datetime(2024, 1, 1, 10, 0, 0)
    return activity


class TestAdminActivityManagement:
    """管理员活动管理测试"""

    @patch('API_activities.admin.activity_manage.db.session')
    @patch('API_activities.admin.activity_manage.Activity')
    def test_create_activity_success(self, mock_activity_model, mock_session, client, mock_admin_user, mock_auth_headers):
        """测试管理员创建活动 - 成功案例"""
        # token_required已经被全局Mock，无需在每个测试中Mock

        # 创建Mock的活动对象
        mock_activity = Mock()
        mock_activity.id = 1
        mock_activity.title = '新测试活动'
        mock_activity.description = '这是一个新的测试活动'
        mock_activity.location = '新测试地点'
        mock_activity.start_time = datetime.now() + timedelta(days=1)
        mock_activity.end_time = datetime.now() + timedelta(days=2)
        mock_activity.max_participants = 20
        mock_activity.tags = ['新活动']
        mock_activity.status = 'draft'
        mock_activity.organizer_user_id = 1
        mock_activity.organizer_display = '管理员'
        mock_activity.created_at = datetime.now()

        # Mock the isoformat method for datetime objects
        mock_datetime = Mock()
        mock_datetime.isoformat.return_value = '2024-01-02T10:00:00'
        mock_activity.start_time.isoformat = lambda: '2024-01-02T10:00:00Z'
        mock_activity.end_time.isoformat = lambda: '2024-01-03T10:00:00Z'
        mock_activity.created_at.isoformat = lambda: '2024-01-01T10:00:00Z'

        # 设置Mock的返回值 - 确保构造函数返回我们的mock对象
        mock_activity_model.return_value = mock_activity

        # Mock session methods
        mock_session.add = Mock()
        mock_session.commit = Mock()

        # Mock db.session.commit to avoid actual database operations
        mock_session.commit.return_value = None

        activity_data = {
            'title': '新测试活动',
            'description': '这是一个新的测试活动',
            'location': '新测试地点',
            'start_time': (datetime.now() + timedelta(days=1)).isoformat() + 'Z',
            'end_time': (datetime.now() + timedelta(days=2)).isoformat() + 'Z',
            'max_participants': 20,
            'tags': ['新活动'],
            'status': 'draft'
        }

        response = client.post(
            '/api/activities/admin/activities',
            data=json.dumps(activity_data),
            headers=mock_auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert '活动创建成功' in data['message']
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
