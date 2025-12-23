import pytest
import tempfile
import os
from flask import Flask
from components import db
from components.models import User, Admin
from API_user import api_user_bp
from datetime import datetime

@pytest.fixture(scope='module')
def app():
    """创建测试应用实例"""
    app = Flask(__name__)

    # 配置测试数据库
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['JWT_SECRET_KEY'] = 'test-jwt-secret'

    # 初始化数据库
    db.init_app(app)

    # 注册蓝图
    app.register_blueprint(api_user_bp)

    # 创建数据库表
    with app.app_context():
        db.create_all()

        # 创建测试数据
        # 创建测试用户
        test_user = User(
            account='testuser',
            username='测试用户',
            email='test@example.com',
            phone='13800138000',
            is_deleted=0
        )
        test_user.set_password('password123')
        db.session.add(test_user)

        # 创建测试管理员
        test_admin = Admin(
            account='testadmin',
            username='测试管理员',
            email='admin@example.com',
            phone='13800138001',
            role='ADMIN'
        )
        test_admin.set_password('admin123')
        db.session.add(test_admin)

        db.session.commit()

    return app

@pytest.fixture(scope='module')
def client(app):
    """创建测试客户端"""
    return app.test_client()

@pytest.fixture(scope='module')
def app_context(app):
    """创建应用上下文"""
    with app.app_context():
        yield

@pytest.fixture
def user_token(client):
    """获取用户认证token"""
    response = client.post('/api/user/login', json={
        'account': 'testuser',
        'password': 'password123'
    })
    data = response.get_json()
    return data['data']['token'] if response.status_code == 200 else None

@pytest.fixture
def admin_token(client):
    """获取管理员认证token"""
    response = client.post('/api/user/login', json={
        'account': 'testadmin',
        'password': 'admin123'
    })
    data = response.get_json()
    return data['data']['token'] if response.status_code == 200 else None

@pytest.fixture
def auth_headers(user_token):
    """获取认证头"""
    return {'Authorization': f'Bearer {user_token}'}

@pytest.fixture
def admin_auth_headers(admin_token):
    """获取管理员认证头"""
    return {'Authorization': f'Bearer {admin_token}'}

def assert_success_response(response, status_code=200):
    """验证成功响应"""
    assert response.status_code == status_code
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data
    return data['data']

def assert_error_response(response, expected_status=400, expected_message=None):
    """验证错误响应"""
    assert response.status_code == expected_status
    data = response.get_json()
    assert data['success'] is False
    if expected_message:
        assert expected_message in data['message']
    return data

def assert_permission_denied(response):
    """验证权限被拒绝"""
    assert response.status_code in [401, 403]
    data = response.get_json()
    assert data['success'] is False