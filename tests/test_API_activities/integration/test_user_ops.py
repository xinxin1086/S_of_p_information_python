# API_activities 用户操作接口集成测试

import pytest
import json
from datetime import datetime, timedelta
from flask import Flask
from unittest.mock import patch, Mock

from API_activities.user.user_ops import user_ops_bp
from components.models import Activity, ActivityBooking, ActivityRating, User
from components.response_service import ResponseService

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
def mock_user():
    """Mock用户对象"""
    user = Mock()
    user.id = 1
    user.account = "testuser"
    user.username = "测试用户"
    user.avatar = "avatar.jpg"
    return user


@pytest.fixture
def mock_activity():
    """Mock活动对象"""
    activity = Mock()
    activity.id = 1
    activity.title = "测试活动"
    activity.description = "这是一个测试活动"
    activity.location = "测试地点"
    activity.start_time = datetime.now() + timedelta(days=1)
    activity.end_time = datetime.now() + timedelta(days=2)
    activity.max_participants = 10
    activity.status = "published"
    activity.organizer_user_id = 2
    activity.organizer_display = "组织者"
    activity.tags = ["测试"]
    return activity


class TestUserBookingOperations:
    """用户预约操作测试"""

    @patch('API_activities.user.user_ops.Activity')
    @patch('API_activities.user.user_ops.ActivityValidator.is_activity_bookable')
    @patch('API_activities.user.user_ops.ActivityValidator.check_user_booking_conflict')
    @patch('API_activities.user.user_ops.db.session')
    def test_book_activity_success(self, mock_session, mock_check_conflict,
                                   mock_validate_bookable, mock_activity_model,
                                   client, mock_user, mock_activity, mock_auth_headers):
        """测试用户预约活动 - 成功案例"""
        # token_required已经被全局Mock，无需在每个测试中Mock
        mock_query = Mock()
        mock_activity_model.query = mock_query
        mock_query.get.return_value = mock_activity
        mock_validate_bookable.return_value = (True, "")
        mock_check_conflict.return_value = (False, None)

        # 创建Mock的预约对象
        mock_booking = Mock()
        mock_booking.id = 1
        mock_booking.activity_id = 1
        mock_booking.user_account = 'testuser'
        mock_booking.status = 'booked'
        mock_booking.notes = '测试预约备注'
        mock_booking.booking_time = datetime.now()

        # Mock ActivityBooking构造函数
        with patch('API_activities.user.user_ops.ActivityBooking', Mock(return_value=mock_booking)):
            mock_session.add = Mock()
            mock_session.commit = Mock()

            # 预约数据
            booking_data = {
                'notes': '测试预约备注'
            }

            response = client.post(
                '/api/activities/user/activities/1/booking',
                data=json.dumps(booking_data),
                headers=mock_auth_headers
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert '预约成功' in data['message']
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
