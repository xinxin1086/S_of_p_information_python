# API_admin 测试配置文件

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock

@pytest.fixture
def app():
    """
    创建简化的测试应用实例
    避免复杂的数据库初始化
    """
    from flask import Flask

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['JWT_SECRET_KEY'] = 'test-jwt-secret'

    return app

@pytest.fixture
def client(app):
    """
    创建测试客户端
    """
    return app.test_client()

@pytest.fixture
def super_admin_token(client):
    """
    创建超级管理员token
    """
    # 登录超级管理员获取token
    login_data = {
        'username': 'test_super_admin',
        'password': 'test_password'
    }

    response = client.post('/api/admin/login',
                          data=json.dumps(login_data),
                          content_type='application/json')

    if response.status_code == 200:
        data = json.loads(response.data)
        return data['data']['token']
    else:
        # 如果登录接口不存在，直接返回测试token
        return 'test-super-admin-token'

@pytest.fixture
def regular_admin_token(client):
    """
    创建普通管理员token
    """
    # 登录普通管理员获取token
    login_data = {
        'username': 'test_admin',
        'password': 'test_password'
    }

    response = client.post('/api/admin/login',
                          data=json.dumps(login_data),
                          content_type='application/json')

    if response.status_code == 200:
        data = json.loads(response.data)
        return data['data']['token']
    else:
        return 'test-admin-token'

@pytest.fixture
def mock_admin_user():
    """
    模拟管理员用户对象
    """
    admin = Mock()
    admin.id = 1
    admin.account = 'test_super_admin'
    admin.username = 'test_super_admin'
    admin.email = 'super_admin@test.com'
    admin.role = 'SUPER_ADMIN'
    admin.is_active = True
    return admin

@pytest.fixture
def mock_regular_admin():
    """
    模拟普通管理员用户对象
    """
    admin = Mock()
    admin.id = 2
    admin.account = 'test_admin'
    admin.username = 'test_admin'
    admin.email = 'admin@test.com'
    admin.role = 'ADMIN'
    admin.is_active = True
    return admin

@pytest.fixture
def mock_user():
    """
    模拟普通用户对象
    """
    user = Mock()
    user.id = 1
    user.account = 'test_user'
    user.username = 'test_user'
    user.email = 'user@test.com'
    user.nickname = '测试用户'
    user.is_deleted = 0
    return user

@pytest.fixture
def mock_article():
    """
    模拟科普文章对象
    """
    article = Mock()
    article.id = 1
    article.title = '测试科普文章'
    article.content = '这是一篇测试科普文章的内容'
    article.summary = '测试文章摘要'
    article.author_display = '测试用户'
    article.author_user_id = 1
    article.status = 'pending'
    article.category = '健康'
    article.view_count = 100
    article.like_count = 10
    article.created_at = datetime.now()
    article.updated_at = datetime.now()
    return article

@pytest.fixture
def mock_activity():
    """
    模拟活动对象
    """
    activity = Mock()
    activity.id = 1
    activity.title = '测试活动'
    activity.description = '这是一个测试活动'
    activity.organizer_display = '测试组织者'
    activity.activity_type = '健康讲座'
    activity.status = 'pending'
    activity.start_time = datetime.now() + timedelta(days=7)
    activity.end_time = datetime.now() + timedelta(days=8)
    activity.max_participants = 50
    activity.current_participants = 25
    activity.created_at = datetime.now()
    activity.updated_at = datetime.now()
    return activity

# 测试工具函数
def get_auth_headers(token):
    """
    获取认证头信息
    """
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }

def assert_success_response(response, expected_message=None):
    """
    断言成功响应
    """
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    if expected_message:
        assert expected_message in data['message']
    return data

def assert_error_response(response, expected_status_code=400, expected_message=None):
    """
    断言错误响应
    """
    assert response.status_code == expected_status_code
    data = json.loads(response.data)
    assert data['success'] is False
    if expected_message:
        assert expected_message in data['message']
    return data

def assert_permission_denied(response):
    """
    断言权限拒绝响应
    """
    return assert_error_response(response, 403, '权限不足')