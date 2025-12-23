# API_notice模块pytest配置文件
# 包含测试夹具和测试配置

import pytest
from datetime import datetime, timedelta
from flask import Flask

from components import db, compat_session
from components.models.notice_models import Notice, NoticeRead, NoticeAttachment
from components.models.user_models import User, Admin
from components.models.base import BaseUser


def safe_db_session():
    """安全获取数据库会话"""
    try:
        return db.session
    except AttributeError:
        return compat_session()


@pytest.fixture(scope='session')
def app():
    """创建测试应用"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 初始化数据库
    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """创建测试客户端"""
    return app.test_client()


@pytest.fixture(scope='function')
def session(app):
    """创建数据库会话"""
    with app.app_context():
        # Flask-SQLAlchemy 3.x兼容性处理
        try:
            # 尝试使用旧方式创建session
            connection = db.engine.connect()
            transaction = connection.begin()
            session = db.session(bind=connection)

            yield session

            session.close()
            transaction.rollback()
            connection.close()
        except (TypeError, AttributeError):
            # Flask-SQLAlchemy 3.x使用直接session
            session = safe_db_session()
            yield session


@pytest.fixture
def test_user(session):
    """创建测试用户"""
    user = User(
        account='testuser',
        username='测试用户',
        phone='13800138001',
        email='test@example.com',
        role='USER',
        is_deleted=0
    )
    user.set_password('testpass123')
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def test_admin(session):
    """创建测试管理员"""
    # 先创建用户记录
    admin_user = User(
        account='testadmin',
        username='测试管理员',
        phone='13800138002',
        email='admin@example.com',
        role='ADMIN',
        is_deleted=0
    )
    admin_user.set_password('adminpass123')
    session.add(admin_user)
    session.flush()

    # 再创建管理员记录
    admin = Admin(
        account='testadmin',
        username='测试管理员',
        phone='13800138002',
        email='admin@example.com',
        role='ADMIN',
        user_id=admin_user.id
    )
    admin.set_password('adminpass123')
    session.add(admin)
    session.commit()

    return admin


@pytest.fixture
def test_notices(session, test_admin):
    """创建测试公告数据"""
    notices = []

    # 系统公告（置顶）
    notice1 = Notice(
        release_title='系统维护公告',
        release_notice='系统将于今晚进行维护，请提前保存数据。',
        notice_type='SYSTEM',
        author_user_id=test_admin.id,
        author_display='测试管理员（管理员）',
        status='APPROVED',
        release_time=datetime.now() - timedelta(days=1)
    )
    if hasattr(notice1, 'is_top'):
        notice1.is_top = True
    session.add(notice1)

    # 一般公告
    notice2 = Notice(
        release_title='新功能发布',
        release_notice='我们很高兴地通知大家，新功能已经上线！',
        notice_type='GENERAL',
        author_user_id=test_admin.id,
        author_display='测试管理员（管理员）',
        status='APPROVED',
        release_time=datetime.now() - timedelta(days=2)
    )
    session.add(notice2)

    # 管理员公告
    notice3 = Notice(
        release_title='内部会议通知',
        release_notice='请各位管理员参加明天上午的内部会议。',
        notice_type='ADMIN',
        author_user_id=test_admin.id,
        author_display='测试管理员（管理员）',
        status='APPROVED',
        release_time=datetime.now() - timedelta(days=3)
    )
    session.add(notice3)

    # 过期公告
    notice4 = Notice(
        release_title='已过期公告',
        release_notice='这是一条已经过期的公告。',
        notice_type='GENERAL',
        author_user_id=test_admin.id,
        author_display='测试管理员（管理员）',
        status='APPROVED',
        release_time=datetime.now() - timedelta(days=10),
        expiration=datetime.now() - timedelta(days=1)
    )
    session.add(notice4)

    # 草稿公告
    notice5 = Notice(
        release_title='草稿公告',
        release_notice='这是一条还未发布的公告。',
        notice_type='GENERAL',
        author_user_id=test_admin.id,
        author_display='测试管理员（管理员）',
        status='DRAFT',
        release_time=datetime.now() - timedelta(days=1)
    )
    session.add(notice5)

    session.commit()

    # 刷新获取所有公告
    notices = [notice1, notice2, notice3, notice4, notice5]
    return notices


@pytest.fixture
def test_notice_reads(session, test_user, test_notices):
    """创建测试公告已读记录"""
    # 用户只读了第一条公告
    notice_read = NoticeRead(
        user_id=test_user.id,
        notice_id=test_notices[0].id,
        read_time=datetime.now()
    )
    session.add(notice_read)
    session.commit()
    return notice_read


@pytest.fixture
def mock_token_required(monkeypatch):
    """模拟token_required装饰器"""
    def mock_decorator(f):
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        return wrapper

    import API_notice.user.notice_ops
    import API_notice.admin.notice_manage
    import API_notice.notice.category

    monkeypatch.setattr(API_notice.user.notice_ops, 'token_required', mock_decorator)
    monkeypatch.setattr(API_notice.admin.notice_manage, 'token_required', mock_decorator)
    monkeypatch.setattr(API_notice.notice.category, 'token_required', mock_decorator)


@pytest.fixture
def mock_admin_required(monkeypatch):
    """模拟admin_required装饰器"""
    def mock_decorator(f):
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        return wrapper

    import API_notice.admin.notice_manage
    import API_notice.notice.category

    monkeypatch.setattr(API_notice.admin.notice_manage, 'admin_required', mock_decorator)
    monkeypatch.setattr(API_notice.notice.category, 'admin_required', mock_decorator)


# 测试数据工厂
class NoticeFactory:
    """公告数据工厂"""

    @staticmethod
    def create_notice(session, **kwargs):
        """创建公告"""
        defaults = {
            'release_title': '测试公告',
            'release_notice': '这是一条测试公告。',
            'notice_type': 'GENERAL',
            'status': 'APPROVED',
            'release_time': datetime.now(),
            'author_display': '系统发布'
        }
        defaults.update(kwargs)

        notice = Notice(**defaults)
        session.add(notice)
        session.commit()
        return notice


class UserFactory:
    """用户数据工厂"""

    @staticmethod
    def create_user(session, **kwargs):
        """创建用户"""
        defaults = {
            'account': f'testuser_{datetime.now().timestamp()}',
            'username': '测试用户',
            'phone': f'138{int(datetime.now().timestamp()) % 100000000:08d}',
            'email': 'test@example.com',
            'role': 'USER',
            'is_deleted': 0
        }
        defaults.update(kwargs)

        user = User(**defaults)
        user.set_password('testpass123')
        session.add(user)
        session.commit()
        return user


class AdminFactory:
    """管理员数据工厂"""

    @staticmethod
    def create_admin(session, **kwargs):
        """创建管理员"""
        # 先创建用户
        user_defaults = {
            'account': f'testadmin_{datetime.now().timestamp()}',
            'username': '测试管理员',
            'phone': f'139{int(datetime.now().timestamp()) % 100000000:08d}',
            'email': 'admin@example.com',
            'role': 'ADMIN',
            'is_deleted': 0
        }

        user = User(**user_defaults)
        user.set_password('adminpass123')
        session.add(user)
        session.flush()

        # 再创建管理员
        admin_defaults = {
            'account': user.account,
            'username': user.username,
            'phone': user.phone,
            'email': user.email,
            'role': 'ADMIN',
            'user_id': user.id
        }
        admin_defaults.update(kwargs)

        admin = Admin(**admin_defaults)
        admin.set_password('adminpass123')
        session.add(admin)
        session.commit()
        return admin