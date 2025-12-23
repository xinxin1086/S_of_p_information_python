# API_activities 预约接口集成测试

import pytest
import json
from datetime import datetime, timedelta
from flask import Flask
from unittest.mock import patch, Mock

from API_activities.booking.booking import booking_bp
from components.models import Activity, ActivityBooking, User
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
    user.phone = "13800138000"
    user.email = "test@example.com"
    user.is_deleted = 0
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


@pytest.fixture
def mock_booking():
    """Mock预约对象"""
    booking = Mock()
    booking.id = 1
    booking.activity_id = 1
    booking.user_account = "testuser"
    booking.status = "booked"
    booking.notes = "测试备注"
    booking.booking_time = datetime.now()
    booking.updated_at = datetime.now()
    return booking


class TestBookingOperations:
    """预约操作测试"""

    @patch('API_activities.booking.booking.ActivityValidator.is_activity_bookable')
    @patch('API_activities.booking.booking.ActivityValidator.check_user_booking_conflict')
    @patch('API_activities.booking.booking.db.session')
    def test_create_booking_success(self, mock_session, mock_check_conflict, mock_validate_bookable,
                                   client, mock_user, mock_activity, mock_auth_headers):
        """测试创建预约 - 成功案例"""
        # token_required已经被全局Mock，无需在每个测试中Mock

        # Mock Activity查询
        with patch('API_activities.booking.booking.Activity') as mock_activity_model:
                mock_query = Mock()
                mock_activity_model.query = mock_query
                mock_query.get.return_value = mock_activity

                # 创建Mock的预约对象
                mock_booking = Mock()
                mock_booking.id = 1
                mock_booking.activity_id = 1
                mock_booking.user_account = 'testuser'
                mock_booking.status = 'booked'
                mock_booking.notes = '测试预约备注'
                mock_booking.booking_time = datetime.now()

                # Mock ActivityBooking构造函数
                with patch('API_activities.booking.booking.ActivityBooking', Mock(return_value=mock_booking)):
                    mock_validate_bookable.return_value = (True, "")
                    mock_check_conflict.return_value = (False, None)
                    mock_session.add = Mock()
                    mock_session.commit = Mock()

                    booking_data = {
                        'notes': '测试预约备注'
                    }

                    response = client.post(
                        '/api/activities/booking/activities/1/book',
                        data=json.dumps(booking_data),
                        headers=mock_auth_headers
                    )

                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data['success'] is True
                    assert '预约成功' in data['message']
                    mock_session.add.assert_called_once()
                    mock_session.commit.assert_called_once()

    def test_create_booking_activity_not_found(self, client, mock_user, mock_auth_headers):
        """测试创建预约 - 活动不存在"""
        # token_required已经被全局Mock，无需在每个测试中Mock

        # Mock Activity查询返回None
        with patch('API_activities.booking.booking.Activity') as mock_activity_model:
                mock_query = Mock()
                mock_activity_model.query = mock_query
                mock_query.get.return_value = None

                response = client.post(
                    '/api/activities/booking/activities/999/book',
                    headers=mock_auth_headers
                )

                assert response.status_code == 404
                data = json.loads(response.data)
                assert data['success'] is False
                assert '活动不存在' in data['message']

    def test_create_booking_not_bookable(self, client, mock_user, mock_activity, mock_auth_headers):
        """测试创建预约 - 活动不可预约"""
        # Mock装饰器，让真实装饰器被绕过
        with patch('API_activities.booking.booking.token_required') as mock_token_required:
            def mock_wrapper(func):
                def wrapper(*args, **kwargs):
                    return func(mock_user, *args, **kwargs)
                return wrapper

            mock_token_required.side_effect = mock_wrapper

            # Mock Activity查询和验证
            with patch('API_activities.booking.booking.Activity') as mock_activity_model:
                mock_query = Mock()
                mock_activity_model.query = mock_query
                mock_query.get.return_value = mock_activity

                with patch('API_activities.booking.booking.ActivityValidator.is_activity_bookable') as mock_validate:
                    mock_validate.return_value = (False, "活动人数已满")

                    response = client.post(
                        '/api/activities/booking/activities/1/book',
                        headers=mock_auth_headers
                    )

                    assert response.status_code == 400
                    data = json.loads(response.data)
                    assert data['success'] is False
                    assert '活动人数已满' in data['message']

    @patch('API_activities.booking.booking.token_required')
    @patch('API_activities.booking.booking.ActivityBooking')
    @patch('API_activities.booking.booking.Activity')
    @patch('API_activities.booking.booking.db.session')
    def test_cancel_booking_success(self, mock_session, mock_activity_model, mock_booking_model,
                                   mock_token_required, client, mock_user, mock_activity, mock_booking):
        """测试取消预约 - 成功案例"""
        mock_token_required.return_value = lambda f: f(mock_user)

        # Mock Activity query
        activity_query = Mock()
        mock_activity_model.query = activity_query
        activity_query.get.return_value = mock_activity

        # Mock ActivityBooking query
        booking_query = Mock()
        mock_booking_model.query = booking_query
        booking_query.filter_by.return_value.first.return_value = mock_booking

        response = client.delete('/api/activities/booking/activities/1/cancel')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert '预约取消成功' in data['message']
        assert mock_booking.status == 'cancelled'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
