# 论坛帖子路由测试

import pytest
import json
from datetime import datetime, timedelta
from test_API_admin.conftest import (
    get_auth_headers, assert_success_response, assert_error_response,
    assert_permission_denied, create_test_post_data
)

class TestForumPostRetrieval:
    """论坛帖子获取接口测试"""

    def test_get_posts_default_success(self, client):
        """测试默认获取帖子列表成功"""
        response = client.get('/api/forum/post')

        data = assert_success_response(response)
        assert 'items' in data['data']
        assert 'pagination' in data['data']

        # 验证分页信息
        pagination = data['data']['pagination']
        required_pagination_fields = ['total', 'page', 'per_page', 'pages', 'has_prev', 'has_next']
        for field in required_pagination_fields:
            assert field in pagination

        # 验证帖子数据结构
        if data['data']['items']:
            post = data['data']['items'][0]
            required_post_fields = ['id', 'title', 'category', 'view_count',
                                   'like_count', 'comment_count', 'status',
                                   'author_display', 'created_at', 'updated_at']
            for field in required_post_fields:
                assert field in post

    def test_get_posts_with_category_filter(self, client):
        """测试按分类筛选帖子"""
        categories = ['健康养生', '心理关怀', '社交活动', '经验分享']

        for category in categories:
            params = {'category': category}
            response = client.get('/api/forum/post', query_string=params)

            data = assert_success_response(response)
            assert 'items' in data['data']

            # 验证返回的帖子都属于指定分类
            for post in data['data']['items']:
                assert post['category'] == category

    def test_get_posts_with_status_filter(self, client):
        """测试按状态筛选帖子"""
        statuses = ['published', 'pending', 'approved', 'rejected']

        for status in statuses:
            params = {'status': status}
            response = client.get('/api/forum/post', query_string=params)

            data = assert_success_response(response)
            assert 'items' in data['data']

    def test_get_posts_with_keyword_search(self, client):
        """测试按关键词搜索帖子"""
        keywords = ['健康', '养生', '心理', '活动']

        for keyword in keywords:
            params = {'keyword': keyword}
            response = client.get('/api/forum/post', query_string=params)

            data = assert_success_response(response)
            assert 'items' in data['data']

    def test_get_posts_with_sort_options(self, client):
        """测试不同排序选项"""
        sort_options = ['latest', 'hottest', 'most_viewed', 'most_liked']

        for sort_option in sort_options:
            params = {'sort': sort_option}
            response = client.get('/api/forum/post', query_string=params)

            data = assert_success_response(response)
            assert 'items' in data['data']

    def test_get_posts_pagination(self, client):
        """测试帖子列表分页功能"""
        test_pages = [
            {'page': 1, 'per_page': 5},
            {'page': 2, 'per_page': 10},
            {'page': 1, 'per_page': 20}
        ]

        for page_config in test_pages:
            response = client.get('/api/forum/post', query_string=page_config)

            data = assert_success_response(response)
            pagination = data['data']['pagination']
            assert pagination['page'] == page_config['page']
            assert pagination['per_page'] == page_config['per_page']

    def test_get_posts_combined_filters(self, client):
        """测试组合筛选条件"""
        params = {
            'category': '健康养生',
            'status': 'published',
            'keyword': '健康',
            'sort': 'latest',
            'page': 1,
            'per_page': 10
        }

        response = client.get('/api/forum/post', query_string=params)

        data = assert_success_response(response)
        assert 'items' in data['data']
        pagination = data['data']['pagination']
        assert pagination['page'] == 1
        assert pagination['per_page'] == 10

    def test_get_posts_no_results(self, client):
        """测试无结果情况"""
        params = {
            'keyword': '不存在的关键词xyz123',
            'category': '不存在的分类'
        }

        response = client.get('/api/forum/post', query_string=params)

        data = assert_success_response(response)
        assert data['data']['pagination']['total'] == 0
        assert len(data['data']['items']) == 0

class TestForumPostDetail:
    """论坛帖子详情接口测试"""

    def test_get_post_detail_success(self, client):
        """测试成功获取帖子详情"""
        response = client.get('/api/forum/post/1')

        data = assert_success_response(response)
        assert 'data' in data
        post = data['data']

        # 验证帖子详情字段
        required_fields = ['id', 'title', 'content', 'category', 'view_count',
                          'like_count', 'comment_count', 'status', 'author_display',
                          'author_user_id', 'created_at', 'updated_at']

        for field in required_fields:
            assert field in post

    def test_get_post_detail_with_content(self, client):
        """测试获取帖子详情包含内容"""
        response = client.get('/api/forum/post/1')

        data = assert_success_response(response)
        post = data['data']

        assert 'content' in post
        assert len(post['content']) > 0

    def test_get_post_detail_not_found(self, client):
        """测试获取不存在的帖子详情"""
        response = client.get('/api/forum/post/999999')

        assert_error_response(response, 404, '帖子不存在')

    def test_get_post_detail_invalid_id(self, client):
        """测试无效的帖子ID"""
        invalid_ids = ['abc', -1, 0]

        for post_id in invalid_ids:
            response = client.get(f'/api/forum/post/{post_id}')
            # 应该返回404或400错误
            assert response.status_code in [400, 404]

class TestForumPostCreation:
    """论坛帖子创建接口测试"""

    def test_create_post_success(self, client, user_token):
        """测试用户成功创建帖子"""
        post_data = create_test_post_data()

        response = client.post('/api/forum/post',
                             headers=get_auth_headers(user_token),
                             data=json.dumps(post_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'data' in data
        assert 'id' in data['data']
        assert data['data']['title'] == post_data['title']
        assert data['data']['content'] == post_data['content']

    def test_create_post_with_tags(self, client, user_token):
        """测试创建带标签的帖子"""
        post_data = create_test_post_data()
        post_data['tags'] = ['健康', '养生', '分享']

        response = client.post('/api/forum/post',
                             headers=get_auth_headers(user_token),
                             data=json.dumps(post_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'tags' in data['data']
        assert data['data']['tags'] == post_data['tags']

    def test_create_post_minimal_data(self, client, user_token):
        """测试使用最少数据创建帖子"""
        minimal_data = {
            'title': '最简帖子标题',
            'content': '最简帖子内容',
            'category': '经验分享'
        }

        response = client.post('/api/forum/post',
                             headers=get_auth_headers(user_token),
                             data=json.dumps(minimal_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['title'] == minimal_data['title']

    def test_create_post_invalid_title(self, client, user_token):
        """测试创建帖子标题无效"""
        invalid_titles = ['', '   ']  # 空标题或空白标题

        for title in invalid_titles:
            post_data = create_test_post_data()
            post_data['title'] = title

            response = client.post('/api/forum/post',
                                 headers=get_auth_headers(user_token),
                                 data=json.dumps(post_data),
                                 content_type='application/json')

            assert_error_response(response, 400, '标题不能为空')

    def test_create_post_missing_content(self, client, user_token):
        """测试创建帖子缺少内容"""
        post_data = {
            'title': '测试标题',
            'category': '健康养生'
            # 缺少content字段
        }

        response = client.post('/api/forum/post',
                             headers=get_auth_headers(user_token),
                             data=json.dumps(post_data),
                             content_type='application/json')

        assert_error_response(response, 400, '内容不能为空')

    def test_create_post_invalid_category(self, client, user_token):
        """测试创建帖子分类无效"""
        post_data = create_test_post_data()
        post_data['category'] = 'invalid_category'

        response = client.post('/api/forum/post',
                             headers=get_auth_headers(user_token),
                             data=json.dumps(post_data),
                             content_type='application/json')

        # 可能接受自定义分类或返回错误
        assert response.status_code in [200, 400]

    def test_create_post_unauthorized(self, client):
        """测试未认证创建帖子"""
        post_data = create_test_post_data()

        response = client.post('/api/forum/post',
                             data=json.dumps(post_data),
                             content_type='application/json')

        assert response.status_code == 401

    def test_create_post_malformed_json(self, client, user_token):
        """测试格式错误的JSON数据"""
        malformed_json = '{"title": "test", '  # 不完整的JSON

        response = client.post('/api/forum/post',
                             headers=get_auth_headers(user_token),
                             data=malformed_json,
                             content_type='application/json')

        assert response.status_code == 400

class TestForumPostUpdate:
    """论坛帖子更新接口测试"""

    def test_update_post_success(self, client, user_token):
        """测试用户成功更新自己的帖子"""
        update_data = {
            'title': '更新后的标题',
            'content': '更新后的内容'
        }

        response = client.put('/api/forum/post/1',
                            headers=get_auth_headers(user_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['title'] == update_data['title']

    def test_update_post_add_tags(self, client, user_token):
        """测试更新帖子添加标签"""
        update_data = {
            'tags': ['心理健康', '情绪管理', '经验分享']
        }

        response = client.put('/api/forum/post/1',
                            headers=get_auth_headers(user_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['tags'] == update_data['tags']

    def test_update_post_change_category(self, client, user_token):
        """测试更新帖子分类"""
        update_data = {'category': '社交活动'}

        response = client.put('/api/forum/post/1',
                            headers=get_auth_headers(user_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['category'] == update_data['category']

    def test_update_post_not_found(self, client, user_token):
        """测试更新不存在的帖子"""
        update_data = {'title': '更新标题'}

        response = client.put('/api/forum/post/999999',
                            headers=get_auth_headers(user_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        assert_error_response(response, 404, '帖子不存在')

    def test_update_post_unauthorized(self, client):
        """测试未认证更新帖子"""
        update_data = {'title': '更新标题'}

        response = client.put('/api/forum/post/1',
                            data=json.dumps(update_data),
                            content_type='application/json')

        assert response.status_code == 401

    def test_update_post_invalid_data(self, client, user_token):
        """测试更新帖子数据无效"""
        update_data = {
            'title': '',  # 空标题
            'content': ''  # 空内容
        }

        response = client.put('/api/forum/post/1',
                            headers=get_auth_headers(user_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        assert_error_response(response, 400)

class TestForumPostDeletion:
    """论坛帖子删除接口测试"""

    def test_delete_post_success(self, client, user_token):
        """测试用户成功删除自己的帖子"""
        response = client.delete('/api/forum/post/1',
                               headers=get_auth_headers(user_token))

        assert_success_response(response)

    def test_delete_post_not_found(self, client, user_token):
        """测试删除不存在的帖子"""
        response = client.delete('/api/forum/post/999999',
                               headers=get_auth_headers(user_token))

        assert_error_response(response, 404, '帖子不存在')

    def test_delete_post_unauthorized(self, client):
        """测试未认证删除帖子"""
        response = client.delete('/api/forum/post/1')
        assert response.status_code == 401

    def test_delete_post_admin(self, client, admin_token):
        """测试管理员删除帖子"""
        response = client.delete('/api/forum/post/1',
                               headers=get_auth_headers(admin_token))

        # 管理员可能可以删除任何帖子
        assert response.status_code in [200, 403]

    def test_get_post_detail_success(self, client, sample_post):
        """测试获取帖子详情成功"""
        response = client.get(f'/api/forum/post/{sample_post.id}')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == sample_post.id
        assert data['data']['title'] == sample_post.title
        assert 'content' in data['data']

    def test_get_post_detail_not_found(self, client):
        """测试获取不存在的帖子详情"""
        response = client.get('/api/forum/post/999999')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data['success'] is False
        assert '帖子不存在' in data['message']

    def test_create_post_success(self, client, auth_headers_user):
        """测试创建帖子成功"""
        post_data = {
            'title': '新帖子标题',
            'content': '这是一个新帖子的内容',
            'category': 'test'
        }

        response = client.post(
            '/api/forum/post',
            data=json.dumps(post_data),
            content_type='application/json',
            headers=auth_headers_user
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == post_data['title']
        assert data['data']['content'] == post_data['content']

    def test_create_post_missing_title(self, client, auth_headers_user):
        """测试创建帖子缺少标题"""
        post_data = {
            'content': '只有内容没有标题'
        }

        response = client.post(
            '/api/forum/post',
            data=json.dumps(post_data),
            content_type='application/json',
            headers=auth_headers_user
        )
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert '标题不能为空' in data['message']

    def test_create_post_missing_content(self, client, auth_headers_user):
        """测试创建帖子缺少内容"""
        post_data = {
            'title': '只有标题没有内容'
        }

        response = client.post(
            '/api/forum/post',
            data=json.dumps(post_data),
            content_type='application/json',
            headers=auth_headers_user
        )
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert '内容不能为空' in data['message']

    def test_create_post_unauthorized(self, client):
        """测试未授权创建帖子"""
        post_data = {
            'title': '未授权的帖子',
            'content': '没有认证的帖子内容'
        }

        response = client.post(
            '/api/forum/post',
            data=json.dumps(post_data),
            content_type='application/json'
        )
        # 根据实际的token_required装饰器实现，这里可能返回401或403
        assert response.status_code in [401, 403]

    def test_update_post_success(self, client, auth_headers_user, sample_post):
        """测试更新帖子成功"""
        update_data = {
            'title': '更新后的标题',
            'content': '更新后的内容'
        }

        response = client.put(
            f'/api/forum/post/{sample_post.id}',
            data=json.dumps(update_data),
            content_type='application/json',
            headers=auth_headers_user
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['title'] == update_data['title']

    def test_update_post_not_found(self, client, auth_headers_user):
        """测试更新不存在的帖子"""
        update_data = {
            'title': '更新不存在的帖子'
        }

        response = client.put(
            '/api/forum/post/999999',
            data=json.dumps(update_data),
            content_type='application/json',
            headers=auth_headers_user
        )
        assert response.status_code == 404

    def test_update_post_unauthorized(self, client, auth_headers_admin, sample_post):
        """测试无权限更新帖子"""
        update_data = {
            'title': '管理员尝试更新用户帖子'
        }

        response = client.put(
            f'/api/forum/post/{sample_post.id}',
            data=json.dumps(update_data),
            content_type='application/json',
            headers=auth_headers_admin
        )
        # 根据实际的权限检查实现，这里可能返回403
        assert response.status_code == 403

    def test_delete_post_success(self, client, auth_headers_user, sample_post):
        """测试删除帖子成功"""
        response = client.delete(
            f'/api/forum/post/{sample_post.id}',
            headers=auth_headers_user
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert '删除成功' in data['message']

    def test_delete_post_not_found(self, client, auth_headers_user):
        """测试删除不存在的帖子"""
        response = client.delete('/api/forum/post/999999', headers=auth_headers_user)
        assert response.status_code == 404

    def test_get_hot_posts(self, client, sample_post):
        """测试获取热门帖子"""
        response = client.get('/api/forum/post/hot')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert isinstance(data['data'], list)

    def test_get_categories(self, client, sample_post):
        """测试获取分类列表"""
        response = client.get('/api/forum/post/categories')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert isinstance(data['data'], list)
        assert 'test' in data['data']

    def test_search_posts(self, client, sample_post):
        """测试搜索帖子"""
        response = client.get('/api/forum/post/search?q=测试')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'items' in data['data']

    def test_search_posts_missing_keyword(self, client):
        """测试搜索帖子缺少关键词"""
        response = client.get('/api/forum/post/search')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert '关键词不能为空' in data['message']

    def test_pagination(self, client, app):
        """测试分页功能"""
        # 创建多个帖子用于分页测试
        with app.app_context():
            for i in range(25):
                post = ForumPost(
                    title=f'测试帖子 {i}',
                    content=f'内容 {i}',
                    category='test',
                    status='published',
                    author_user_id=1,
                    author_display='测试用户'
                )
                db.session.add(post)
            db.session.commit()

        # 测试第一页
        response = client.get('/api/forum/post?page=1&size=10')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['data']['page'] == 1
        assert data['data']['size'] == 10
        assert len(data['data']['items']) == 10

    def test_sensitive_word_filter(self, client, auth_headers_user):
        """测试敏感词过滤"""
        # 包含敏感词的帖子内容
        post_data = {
            'title': '包含违禁词的标题',
            'content': '这里有违禁词1和垃圾信息'
        }

        response = client.post(
            '/api/forum/post',
            data=json.dumps(post_data),
            content_type='application/json',
            headers=auth_headers_user
        )

        # 根据敏感词过滤配置，可能返回400（拒绝）或200（过滤后通过）
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert data['success'] is True
            # 检查敏感词是否被过滤
            assert '***' in data['data']['content'] or '违禁词' not in data['data']['content']