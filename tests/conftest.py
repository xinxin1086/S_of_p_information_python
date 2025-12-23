# tests/conftest.py

"""
pytest 配置文件
定义测试夹具和通用配置
"""

import sys
import os
import random
import string

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 导入全局Mock管理器
from .conftest_mock_manager import global_mock_manager

# 在导入其他模块之前设置全局Mock
global_mock_manager.setup_token_mock()

import pytest
from components import db, compat_session  # 使用兼容性session
from components.models import ScienceArticle, User, Admin
from components.db_compatibility import DatabaseCompatibilityManager
from datetime import datetime
from unittest.mock import Mock
from .shared_test_config import (
    create_simple_mock,
    SAMPLE_UPDATE_DATA
)

# 为Flask-SQLAlchemy 3.x修复session问题
def safe_db_session():
    """安全获取数据库会话"""
    try:
        return db.session
    except AttributeError:
        return compat_session()


@pytest.fixture
def app():
    """创建测试应用"""
    from app import create_app

    # 创建测试配置类
    class TestConfig:
        TESTING = True
        # 优化SQLite配置，启用外键支持和WAL模式
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:?foreign_keys=ON'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'connect_args': {
                'timeout': 20,
                'check_same_thread': False,
            }
        }
        JWT_SECRET_KEY = 'test_secret_key'  # 测试用密钥
        JWT_EXPIRATION_DELTA = 3600
        IMAGE_STORAGE_DIR = 'test_images'
        ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        ALLOWED_IMAGE_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        MAX_IMAGE_SIZE = 5 * 1024 * 1024

        # 修复Flask会话后端问题
        SECRET_KEY = 'test_session_secret_key'
        SESSION_TYPE = 'null'  # 使用null会话类型避免文件系统依赖
        WTF_CSRF_ENABLED = False  # 测试时禁用CSRF保护

        # 添加测试专用配置
        TESTING = True

    app = create_app(TestConfig())

    with app.app_context():
        # 创建所有表
        db.create_all()

        # 使用数据库兼容性管理器设置数据库
        compatibility_manager = DatabaseCompatibilityManager(db.engine)
        compatibility_manager.setup_database_compatibility()

        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """创建测试客户端"""
    # 使用null会话类型避免了session_transaction的问题
    return app.test_client()


@pytest.fixture
def test_user(app):
    """创建测试用户（使用唯一手机号）"""
    with app.app_context():
        # 生成随机唯一手机号（138开头+8位随机数字）
        random_suffix = ''.join(random.sample(string.digits, 8))
        unique_phone = f'138{random_suffix}'
        unique_account = f'testuser_{random_suffix}'
        unique_email = f'test_{random_suffix}@example.com'

        user = User(
            account=unique_account,
            username='测试用户',
            phone=unique_phone,
            email=unique_email,
            role='USER',
            is_deleted=0
        )
        user.set_password('testpass123')  # 使用正确的密码设置方法
        safe_db_session().add(user)
        safe_db_session().commit()
        return user


@pytest.fixture
def test_admin(app):
    """创建测试管理员（使用唯一手机号）"""
    with app.app_context():
        # 生成随机唯一手机号（138开头+8位随机数字）
        random_suffix = ''.join(random.sample(string.digits, 8))
        unique_phone = f'138{random_suffix}'
        unique_account = f'testadmin_{random_suffix}'
        unique_email = f'admin_{random_suffix}@example.com'

        # 先创建用户记录
        admin_user = User(
            account=unique_account,
            username='测试管理员',
            phone=unique_phone,
            email=unique_email,
            role='ADMIN',
            is_deleted=0
        )
        admin_user.set_password('adminpass123')
        safe_db_session().add(admin_user)
        safe_db_session().flush()  # 获取用户ID，但不提交

        # 再创建管理员记录（使用相同的唯一手机号）
        admin = Admin(
            account=unique_account,
            username='测试管理员',
            phone=unique_phone,
            email=unique_email,
            role='ADMIN',
            user_id=admin_user.id
        )
        admin.set_password('adminpass123')
        safe_db_session().add(admin)
        safe_db_session().commit()

        return admin, admin_user  # 返回管理员和关联的用户对象


@pytest.fixture
def test_articles(app, test_user, test_admin):
    """创建测试文章"""
    with app.app_context():
        articles = []

        # 解包test_admin元组（admin, admin_user）
        admin, admin_user = test_admin

        # 创建不同状态的文章
        statuses = ['draft', 'pending', 'published', 'rejected']
        for i, status in enumerate(statuses):
            article = ScienceArticle(
                title=f'测试文章{i+1}',
                content=f'这是测试文章{i+1}的内容',
                status=status,
                author_user_id=test_user.id if status != 'published' else admin_user.id,
                author_display=f'测试用户{i+1}',
                like_count=10 * (i + 1),
                view_count=100 * (i + 1),
                published_at=datetime.utcnow() if status == 'published' else None
            )
            safe_db_session().add(article)
            articles.append(article)

        safe_db_session().commit()
        return articles


@pytest.fixture
def mock_current_user(test_user):
    """模拟当前登录用户"""
    class MockUser:
        def __init__(self, user):
            self.account = user.account
            self.username = user.username
            self.role = user.role
            self.is_deleted = user.is_deleted
            self.id = user.id

    return MockUser(test_user)


@pytest.fixture
def mock_current_admin(test_admin):
    """模拟当前登录管理员"""
    # 解包test_admin元组（admin, admin_user）
    admin, admin_user = test_admin

    class MockAdmin:
        def __init__(self, admin_obj):
            self.account = admin_obj.account
            self.username = admin_obj.username
            self.role = admin_obj.role
            self.id = admin_obj.id

    return MockAdmin(admin)


@pytest.fixture
def sample_article_data():
    """示例文章数据"""
    return {
        'title': '这是一个测试标题',
        'content': '这是测试文章的内容，包含一些描述性文字。',
        'cover_image': 'https://example.com/image.jpg',
        'status': 'draft'
    }


@pytest.fixture
def sample_update_data():
    """示例更新数据"""
    return SAMPLE_UPDATE_DATA


@pytest.fixture
def safe_mock_user():
    """安全的Mock用户对象，避免SQLAlchemy上下文问题"""
    return create_simple_mock('User')


@pytest.fixture
def safe_mock_admin():
    """安全的Mock管理员对象，避免SQLAlchemy上下文问题"""
    return create_simple_mock('Admin')


@pytest.fixture
def safe_mock_article():
    """安全的Mock文章对象，避免SQLAlchemy上下文问题"""
    return create_simple_mock('ScienceArticle')


@pytest.fixture
def safe_mock_activity():
    """安全的Mock活动对象，避免SQLAlchemy上下文问题"""
    return create_simple_mock('Activity')


@pytest.fixture
def safe_mock_booking():
    """安全的Mock预约对象，避免SQLAlchemy上下文问题"""
    return create_simple_mock('ActivityBooking')


@pytest.fixture
def mock_session_data():
    """模拟会话数据，用于替代session_transaction"""
    session_data = {}

    class MockSessionTransaction:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self.data

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    return MockSessionTransaction(session_data)


@pytest.fixture
def mock_token_decorator():
    """统一的token_required装饰器Mock"""
    from unittest.mock import MagicMock

    mock_decorator = MagicMock()

    def mock_wrapper(func):
        def wrapper(*args, **kwargs):
            # 创建mock_user作为第一个参数传递给装饰的函数
            mock_user = Mock()
            mock_user.id = 1
            mock_user.account = "testuser"
            mock_user.username = "测试用户"
            mock_user.role = "user"
            mock_user.is_deleted = 0
            return func(mock_user, *args, **kwargs)
        return wrapper

    # 设置装饰器的行为
    mock_decorator.side_effect = mock_wrapper
    return mock_decorator


@pytest.fixture
def mock_auth_headers():
    """标准的认证请求头"""
    return {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer mock_test_token'
    }


@pytest.fixture
def mock_admin_token_decorator():
    """管理员专用的token_required装饰器Mock"""
    def mock_decorator(func):
        def wrapper(*args, **kwargs):
            # 创建mock_admin作为第一个参数传递给装饰的函数
            mock_admin = Mock()
            mock_admin.id = 1
            mock_admin.account = "testadmin"
            mock_admin.username = "测试管理员"
            mock_admin.role = "admin"
            mock_admin.is_deleted = 0
            return func(mock_admin, *args, **kwargs)
        return wrapper

    return mock_decorator


@pytest.fixture
def app_context():
    """Flask应用上下文夹具"""
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

    with app.app_context():
        yield app