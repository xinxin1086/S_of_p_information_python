# 统一测试配置文件
# 用于所有测试模块的conftest.py内容

import os
import sys
from datetime import datetime, timedelta

# 添加项目根目录到sys.path，确保能正确导入模块
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

def create_simple_mock(model_name):
    """创建简单的Mock对象，避免SQLAlchemy上下文问题"""
    from unittest.mock import Mock

    mock = Mock()

    # 根据模型类型设置默认属性
    if model_name == 'User':
        mock.id = 1
        mock.account = 'testuser'
        mock.username = '测试用户'
        mock.phone = '13800000000'
        mock.email = 'test@example.com'
        mock.avatar = 'avatar.jpg'
        mock.role = 'USER'
        mock.is_deleted = 0

    elif model_name == 'Admin':
        mock.id = 1
        mock.account = 'testadmin'
        mock.username = '测试管理员'
        mock.phone = '13800000001'
        mock.role = 'ADMIN'
        mock.user_id = 1

    elif model_name == 'Activity':
        mock.id = 1
        mock.title = '测试活动'
        mock.description = '这是一个测试活动'
        mock.content = '这是活动内容'
        mock.location = '测试地点'
        mock.start_time = datetime.now() + timedelta(days=1)
        mock.end_time = datetime.now() + timedelta(days=2)
        mock.max_participants = 10
        mock.current_participants = 0
        mock.status = 'published'
        mock.organizer_user_id = 1
        mock.organizer_display = '组织者'
        mock.tags = ['测试']
        mock.cover_image = 'https://example.com/image.jpg'
        mock.view_count = 0
        mock.like_count = 0
        mock.created_at = datetime.now()
        mock.updated_at = datetime.now()

    elif model_name == 'ActivityBooking':
        mock.id = 1
        mock.activity_id = 1
        mock.user_account = 'testuser'
        mock.user_id = 1
        mock.status = 'booked'
        mock.notes = '测试备注'
        mock.booking_time = datetime.now()
        mock.updated_at = datetime.now()

    elif model_name == 'ActivityRating':
        mock.id = 1
        mock.activity_id = 1
        mock.user_account = 'testuser'
        mock.user_id = 1
        mock.rating = 5
        mock.comment = '很好的活动'
        mock.created_at = datetime.now()
        mock.updated_at = datetime.now()

    elif model_name == 'ScienceArticle':
        mock.id = 1
        mock.title = '测试文章'
        mock.content = '这是测试文章的内容'
        mock.author_user_id = 1
        mock.author_display = '测试用户'
        mock.status = 'published'
        mock.like_count = 0
        mock.view_count = 0
        mock.cover_image = 'https://example.com/image.jpg'
        mock.tags = ['测试']
        mock.created_at = datetime.now()
        mock.updated_at = datetime.now()
        mock.published_at = datetime.now()

    elif model_name == 'ScienceArticleLike':
        mock.id = 1
        mock.article_id = 1
        mock.user_account = 'testuser'
        mock.user_id = 1
        mock.created_at = datetime.now()

    elif model_name == 'ScienceArticleVisit':
        mock.id = 1
        mock.article_id = 1
        mock.user_account = 'testuser'
        mock.user_id = 1
        mock.visited_at = datetime.now()

    return mock

# 通用的测试数据
SAMPLE_ARTICLE_DATA = {
    'title': '这是一个测试标题',
    'content': '这是测试文章的内容，包含一些描述性文字。',
    'cover_image': 'https://example.com/image.jpg',
    'status': 'draft'
}

SAMPLE_UPDATE_DATA = {
    'title': '更新后的标题',
    'content': '更新后的内容',
    'status': 'published'
}

SAMPLE_ACTIVITY_DATA = {
    'title': '测试活动',
    'description': '这是一个测试活动',
    'content': '这是活动的详细内容',
    'location': '测试地点',
    'start_time': (datetime.now() + timedelta(days=1)).isoformat(),
    'end_time': (datetime.now() + timedelta(days=2)).isoformat(),
    'max_participants': 10,
    'tags': ['测试'],
    'cover_image': 'https://example.com/image.jpg'
}

SAMPLE_BOOKING_DATA = {
    'notes': '测试预约备注'
}