# API_forum 用户操作测试

import pytest
import json
from datetime import datetime
from components import db
from components.models.user_models import User
from components.models.forum_models import ForumPost, ForumFloor, ForumReply, ForumLike

@pytest.fixture
def normal_user():
    """创建普通用户"""
    user = User(
        username='testuser',
        email='test@test.com',
        password='hashed_password',
        role='USER',
        is_deleted=0
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def other_user():
    """创建另一个用户"""
    user = User(
        username='otheruser',
        email='other@test.com',
        password='hashed_password',
        role='USER',
        is_deleted=0
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def auth_headers(normal_user):
    """用户认证头"""
    return {'Authorization': f'Bearer {normal_user.id}_token'}

@pytest.fixture
def other_auth_headers(other_user):
    """其他用户认证头"""
    return {'Authorization': f'Bearer {other_user.id}_token'}

@pytest.fixture
def user_posts(normal_user):
    """创建用户帖子"""
    posts = []
    for i in range(3):
        post = ForumPost(
            title=f'用户帖子 {i}',
            content=f'帖子内容 {i}',
            category='test',
            status='published',
            author_user_id=normal_user.id,
            author_display=normal_user.username
        )
        db.session.add(post)
        posts.append(post)
    db.session.commit()
    return posts

@pytest.fixture
def user_floor(normal_user, user_posts):
    """创建用户楼层"""
    floor = ForumFloor.create_floor(
        post_id=user_posts[0].id,
        user_id=normal_user.id,
        content='这是一个楼层回复'
    )
    floor.update_author_display()
    db.session.commit()
    return floor

@pytest.fixture
def user_reply(normal_user, user_floor):
    """创建用户回复"""
    reply = ForumReply.create_reply(
        floor_id=user_floor.id,
        user_id=normal_user.id,
        content='这是一个回复'
    )
    reply.update_author_display()
    db.session.commit()
    return reply

class TestUserOperations:
    """用户操作测试类"""

    def test_get_my_posts_success(self, client, auth_headers, user_posts):
        """测试获取我的帖子列表成功"""
        response = client.get('/api/forum/user/posts', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'items' in data['data']
        assert len(data['data']['items']) == 3

    def test_get_my_posts_empty(self, client, auth_headers):
        """测试获取空的帖子列表"""
        response = client.get('/api/forum/user/posts', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 0

    def test_get_my_posts_with_filters(self, client, auth_headers, user_posts):
        """测试带筛选条件获取我的帖子"""
        # 按状态筛选
        response = client.get('/api/forum/user/posts?status=published', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 3

        # 按分类筛选
        response = client.get('/api/forum/user/posts?category=test', headers=auth_headers)
        assert response.status_code == 200

        # 按关键词筛选
        response = client.get('/api/forum/user/posts?keyword=用户帖子', headers=auth_headers)
        assert response.status_code == 200

    def test_get_my_floors_success(self, client, auth_headers, user_floor):
        """测试获取我的楼层列表成功"""
        response = client.get('/api/forum/user/floors', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1

        # 检查楼层数据
        floor_item = next((item for item in data['data']['items'] if item['id'] == user_floor.id), None)
        assert floor_item is not None
        assert 'post_title' in floor_item
        assert floor_item['post_id'] == user_floor.post_id

    def test_get_my_replies_success(self, client, auth_headers, user_reply):
        """测试获取我的回复列表成功"""
        response = client.get('/api/forum/user/replies', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) >= 1

        # 检查回复数据
        reply_item = next((item for item in data['data']['items'] if item['id'] == user_reply.id), None)
        assert reply_item is not None
        assert 'post_title' in reply_item
        assert 'floor_number' in reply_item

    def test_create_post_success(self, client, auth_headers):
        """测试用户创建帖子成功"""
        post_data = {
            'title': '用户新帖子',
            'content': '用户创建的帖子内容',
            'category': 'user_test'
        }

        response = client.post(
            '/api/forum/user/posts',
            data=json.dumps(post_data),
            content_type='application/json',
            headers=auth_headers
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == post_data['title']
        assert data['data']['category'] == post_data['category']

    def test_create_post_draft(self, client, auth_headers):
        """测试创建草稿帖子"""
        post_data = {
            'title': '草稿帖子',
            'content': '这是草稿内容',
            'status': 'draft'
        }

        response = client.post(
            '/api/forum/user/posts',
            data=json.dumps(post_data),
            content_type='application/json',
            headers=auth_headers
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['status'] == 'draft'

    def test_update_my_post_success(self, client, auth_headers, user_posts):
        """测试更新我的帖子成功"""
        post = user_posts[0]
        update_data = {
            'title': '更新后的帖子标题',
            'content': '更新后的帖子内容'
        }

        response = client.put(
            f'/api/forum/user/posts/{post.id}',
            data=json.dumps(update_data),
            content_type='application/json',
            headers=auth_headers
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == update_data['title']

    def test_update_other_post_forbidden(self, client, other_auth_headers, user_posts):
        """测试更新他人帖子被拒绝"""
        post = user_posts[0]
        update_data = {
            'title': '尝试更新他人帖子'
        }

        response = client.put(
            f'/api/forum/user/posts/{post.id}',
            data=json.dumps(update_data),
            content_type='application/json',
            headers=other_auth_headers
        )
        assert response.status_code == 403

        data = json.loads(response.data)
        assert data['success'] is False
        assert '无权限' in data['message']

    def test_delete_my_post_success(self, client, auth_headers, user_posts):
        """测试删除我的帖子成功"""
        post = user_posts[0]

        response = client.delete(
            f'/api/forum/user/posts/{post.id}',
            headers=auth_headers
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True

    def test_delete_other_post_forbidden(self, client, other_auth_headers, user_posts):
        """测试删除他人帖子被拒绝"""
        post = user_posts[0]

        response = client.delete(
            f'/api/forum/user/posts/{post.id}',
            headers=other_auth_headers
        )
        assert response.status_code == 403

    def test_get_my_likes_empty(self, client, auth_headers):
        """测试获取空的点赞列表"""
        response = client.get('/api/forum/user/likes', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 0

    def test_get_my_stats(self, client, auth_headers, user_posts, user_floor, user_reply):
        """测试获取我的统计信息"""
        response = client.get('/api/forum/user/stats', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'basic_stats' in data['data']
        assert 'recent_stats' in data['data']
        assert 'recent_posts' in data['data']

        basic_stats = data['data']['basic_stats']
        assert basic_stats['posts_count'] >= 3
        assert basic_stats['floors_count'] >= 1
        assert basic_stats['replies_count'] >= 1

    def test_get_my_visits_empty(self, client, auth_headers):
        """测试获取空的浏览记录"""
        response = client.get('/api/forum/user/visits', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 0

    def test_unauthorized_access(self, client):
        """测试未授权访问用户接口"""
        endpoints = [
            '/api/forum/user/posts',
            '/api/forum/user/floors',
            '/api/forum/user/replies',
            '/api/forum/user/likes',
            '/api/forum/user/stats',
            '/api/forum/user/visits'
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403]

    def test_pagination_user_posts(self, client, auth_headers, app):
        """测试用户帖子分页"""
        # 创建更多帖子
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            for i in range(25):
                post = ForumPost(
                    title=f'分页测试帖子 {i}',
                    content=f'分页测试内容 {i}',
                    category='pagination_test',
                    status='published',
                    author_user_id=user.id,
                    author_display=user.username
                )
                db.session.add(post)
            db.session.commit()

        # 测试分页
        response = client.get('/api/forum/user/posts?page=1&size=10', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['data']['page'] == 1
        assert data['data']['size'] == 10
        assert len(data['data']['items']) == 10

    def test_content_validation_create_post(self, client, auth_headers):
        """测试创建帖子时的内容验证"""
        # 标题过长
        post_data = {
            'title': 'a' * 201,  # 超过200字符限制
            'content': '正常内容'
        }

        response = client.post(
            '/api/forum/user/posts',
            data=json.dumps(post_data),
            content_type='application/json',
            headers=auth_headers
        )
        assert response.status_code == 400

        # 内容过长
        post_data = {
            'title': '正常标题',
            'content': 'a' * 10001  # 超过10000字符限制
        }

        response = client.post(
            '/api/forum/user/posts',
            data=json.dumps(post_data),
            content_type='application/json',
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_content_validation_update_post(self, client, auth_headers, user_posts):
        """测试更新帖子时的内容验证"""
        post = user_posts[0]

        # 更新为空标题
        update_data = {
            'title': '',
            'content': '有内容'
        }

        response = client.put(
            f'/api/forum/user/posts/{post.id}',
            data=json.dumps(update_data),
            content_type='application/json',
            headers=auth_headers
        )
        assert response.status_code == 400

        # 更新为空内容
        update_data = {
            'title': '有标题',
            'content': ''
        }

        response = client.put(
            f'/api/forum/user/posts/{post.id}',
            data=json.dumps(update_data),
            content_type='application/json',
            headers=auth_headers
        )
        assert response.status_code == 400