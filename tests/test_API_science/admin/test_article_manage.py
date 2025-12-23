# 科普文章管理员接口测试

import pytest
import json
from datetime import datetime, timedelta
from test_API_admin.conftest import (
    get_auth_headers, assert_success_response, assert_error_response,
    assert_permission_denied, create_test_article_data
)

class TestAdminArticleManagement:
    """管理员科普文章管理接口测试"""

    def test_get_all_articles_success(self, client, admin_token):
        """测试管理员成功获取所有文章列表"""
        response = client.get('/API_science/admin/articles',
                            headers=get_auth_headers(admin_token))

        data = assert_success_response(response)
        assert 'items' in data['data']
        assert 'pagination' in data['data']

        # 验证分页信息
        pagination = data['data']['pagination']
        required_pagination_fields = ['total', 'page', 'per_page', 'pages', 'has_prev', 'has_next']
        for field in required_pagination_fields:
            assert field in pagination

        # 验证文章数据结构
        if data['data']['items']:
            article = data['data']['items'][0]
            required_article_fields = ['id', 'title', 'status', 'author_display',
                                     'created_at', 'updated_at', 'view_count', 'like_count']
            for field in required_article_fields:
                assert field in article

    def test_get_articles_with_filters(self, client, admin_token):
        """测试带筛选条件获取文章列表"""
        test_filters = [
            {'status': 'published', 'description': '筛选已发布文章'},
            {'status': 'pending', 'description': '筛选待审核文章'},
            {'status': 'draft', 'description': '筛选草稿文章'},
            {'status': 'rejected', 'description': '筛选已拒绝文章'},
            {'keyword': '测试', 'description': '按关键词搜索'},
        ]

        for filter_config in test_filters:
            response = client.get('/API_science/admin/articles',
                                headers=get_auth_headers(admin_token),
                                query_string=filter_config)

            data = assert_success_response(response)
            assert 'items' in data['data']

    def test_get_articles_with_author_filter(self, client, admin_token):
        """测试按作者ID筛选文章"""
        params = {'author_id': '1'}

        response = client.get('/API_science/admin/articles',
                            headers=get_auth_headers(admin_token),
                            query_string=params)

        data = assert_success_response(response)
        assert 'items' in data['data']

    def test_get_articles_pagination(self, client, admin_token):
        """测试文章列表分页功能"""
        test_pages = [
            {'page': 1, 'size': 5},
            {'page': 2, 'size': 10},
            {'page': 1, 'size': 20}
        ]

        for page_config in test_pages:
            response = client.get('/API_science/admin/articles',
                                headers=get_auth_headers(admin_token),
                                query_string=page_config)

            data = assert_success_response(response)
            pagination = data['data']['pagination']
            assert pagination['page'] == page_config['page']
            assert pagination['per_page'] == page_config['size']

    def test_get_articles_size_limit(self, client, admin_token):
        """测试每页数量限制"""
        # 测试超出限制的size参数
        response = client.get('/API_science/admin/articles',
                            headers=get_auth_headers(admin_token),
                            query_string={'size': 100})  # 超出50的限制

        data = assert_success_response(response)
        # 应该被限制为50
        assert data['data']['pagination']['per_page'] <= 50

    def test_get_articles_unauthorized(self, client, user_token):
        """测试普通用户无权访问管理员文章列表"""
        response = client.get('/API_science/admin/articles',
                            headers=get_auth_headers(user_token))

        assert_permission_denied(response)

    def test_get_articles_no_auth(self, client):
        """测试未认证访问文章列表"""
        response = client.get('/API_science/admin/articles')
        assert response.status_code == 401

class TestAdminArticleDetail:
    """管理员文章详情接口测试"""

    def test_get_article_detail_success(self, client, admin_token):
        """测试管理员成功获取文章详情"""
        response = client.get('/API_science/admin/articles/1',
                            headers=get_auth_headers(admin_token))

        data = assert_success_response(response)
        assert 'data' in data
        article = data['data']

        # 验证文章详情字段
        required_fields = ['id', 'title', 'content', 'summary', 'author_display',
                          'author_user_id', 'status', 'tags', 'category', 'cover_image',
                          'view_count', 'like_count', 'created_at', 'updated_at']

        for field in required_fields:
            assert field in article

        # 验证作者信息字段
        if 'author' in article:
            author = article['author']
            assert 'id' in author
            assert 'username' in author
            assert 'role' in author
            assert 'is_deleted' in author

    def test_get_article_detail_not_found(self, client, admin_token):
        """测试获取不存在的文章详情"""
        response = client.get('/API_science/admin/articles/999999',
                            headers=get_auth_headers(admin_token))

        assert_error_response(response, 404, '文章不存在')

    def test_get_article_detail_invalid_id(self, client, admin_token):
        """测试无效的文章ID"""
        invalid_ids = ['abc', -1, 0]

        for article_id in invalid_ids:
            response = client.get(f'/API_science/admin/articles/{article_id}',
                                headers=get_auth_headers(admin_token))

            # 应该返回404或400错误
            assert response.status_code in [400, 404]

    def test_get_article_detail_permission_denied(self, client, user_token):
        """测试普通用户无权获取管理员文章详情"""
        response = client.get('/API_science/admin/articles/1',
                            headers=get_auth_headers(user_token))

        assert_permission_denied(response)

class TestAdminArticleCreation:
    """管理员创建文章接口测试"""

    def test_create_article_success(self, client, admin_token):
        """测试管理员成功创建文章"""
        article_data = create_test_article_data()

        response = client.post('/API_science/admin/articles',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(article_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'data' in data
        assert 'id' in data['data']
        assert data['data']['title'] == article_data['title']
        assert data['data']['status'] == article_data.get('status', 'draft')

    def test_create_article_as_published(self, client, admin_token):
        """测试管理员创建并直接发布文章"""
        article_data = create_test_article_data()
        article_data['status'] = 'published'

        response = client.post('/API_science/admin/articles',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(article_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['status'] == 'published'

    def test_create_article_as_pending(self, client, admin_token):
        """测试管理员创建待审核文章"""
        article_data = create_test_article_data()
        article_data['status'] = 'pending'

        response = client.post('/API_science/admin/articles',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(article_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['status'] == 'pending'

    def test_create_article_minimal_data(self, client, admin_token):
        """测试使用最少数据创建文章"""
        minimal_data = {
            'title': '最简文章标题',
            'content': '最简文章内容'
        }

        response = client.post('/API_science/admin/articles',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(minimal_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['title'] == minimal_data['title']

    def test_create_article_invalid_title(self, client, admin_token):
        """测试创建文章标题无效"""
        invalid_titles = ['', '   ']  # 空标题或空白标题

        for title in invalid_titles:
            article_data = create_test_article_data()
            article_data['title'] = title

            response = client.post('/API_science/admin/articles',
                                 headers=get_auth_headers(admin_token),
                                 data=json.dumps(article_data),
                                 content_type='application/json')

            assert_error_response(response, 400, '标题不能为空')

    def test_create_article_invalid_status(self, client, admin_token):
        """测试创建文章状态无效"""
        article_data = create_test_article_data()
        article_data['status'] = 'invalid_status'

        response = client.post('/API_science/admin/articles',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(article_data),
                             content_type='application/json')

        assert_error_response(response, 400)

    def test_create_article_missing_content(self, client, admin_token):
        """测试创建文章缺少内容"""
        article_data = {
            'title': '测试标题'
            # 缺少content字段
        }

        response = client.post('/API_science/admin/articles',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(article_data),
                             content_type='application/json')

        assert_error_response(response, 400, '内容不能为空')

    def test_create_article_permission_denied(self, client, user_token):
        """测试普通用户无权创建文章"""
        article_data = create_test_article_data()

        response = client.post('/API_science/admin/articles',
                             headers=get_auth_headers(user_token),
                             data=json.dumps(article_data),
                             content_type='application/json')

        assert_permission_denied(response)

    def test_create_article_malformed_json(self, client, admin_token):
        """测试格式错误的JSON数据"""
        malformed_json = '{"title": "test", '  # 不完整的JSON

        response = client.post('/API_science/admin/articles',
                             headers=get_auth_headers(admin_token),
                             data=malformed_json,
                             content_type='application/json')

        assert response.status_code == 400


class TestAdminArticleUpdate:
    """管理员更新文章接口测试"""

    def test_update_article_success(self, client, admin_token):
        """测试管理员成功更新文章"""
        update_data = {
            'title': '更新后的标题',
            'content': '更新后的内容',
            'summary': '更新后的摘要',
            'status': 'published'
        }

        response = client.put('/API_science/admin/articles/1',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['title'] == update_data['title']

    def test_update_article_status_only(self, client, admin_token):
        """测试只更新文章状态"""
        update_data = {'status': 'published'}

        response = client.put('/API_science/admin/articles/1',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['status'] == 'published'

    def test_update_article_tags_and_category(self, client, admin_token):
        """测试更新文章标签和分类"""
        update_data = {
            'tags': ['健康', '养生', '科普'],
            'category': '健康知识'
        }

        response = client.put('/API_science/admin/articles/1',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['tags'] == update_data['tags']

    def test_update_article_not_found(self, client, admin_token):
        """测试更新不存在的文章"""
        update_data = {'title': '更新标题'}

        response = client.put('/API_science/admin/articles/999999',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        assert_error_response(response, 404, '文章不存在')

    def test_update_article_invalid_data(self, client, admin_token):
        """测试更新文章数据无效"""
        update_data = {
            'title': '',  # 空标题
            'status': 'invalid_status'
        }

        response = client.put('/API_science/admin/articles/1',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        assert_error_response(response, 400)

    def test_update_article_permission_denied(self, client, user_token):
        """测试普通用户无权更新文章"""
        update_data = {'title': '更新标题'}

        response = client.put('/API_science/admin/articles/1',
                            headers=get_auth_headers(user_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        assert_permission_denied(response)

class TestAdminArticleDeletion:
    """管理员删除文章接口测试"""

    def test_delete_article_success(self, client, admin_token):
        """测试管理员成功删除文章"""
        response = client.delete('/API_science/admin/articles/1',
                               headers=get_auth_headers(admin_token))

        assert_success_response(response)

    def test_delete_article_not_found(self, client, admin_token):
        """测试删除不存在的文章"""
        response = client.delete('/API_science/admin/articles/999999',
                               headers=get_auth_headers(admin_token))

        assert_error_response(response, 404, '文章不存在')

    def test_delete_article_permission_denied(self, client, user_token):
        """测试普通用户无权删除文章"""
        response = client.delete('/API_science/admin/articles/1',
                               headers=get_auth_headers(user_token))

        assert_permission_denied(response)

class TestAdminArticleApproval:
    """管理员文章审核接口测试"""

    def test_approve_article_success(self, client, admin_token):
        """测试成功审核通过文章"""
        response = client.post('/API_science/admin/articles/1/approve',
                             headers=get_auth_headers(admin_token))

        assert_success_response(response)
        data = response.get_json()
        if data['success']:
            assert data['data']['status'] == 'published'

    def test_approve_article_with_comment(self, client, admin_token):
        """测试审核通过文章并添加评论"""
        approval_data = {
            'review_comment': '内容优秀，审核通过'
        }

        response = client.post('/API_science/admin/articles/1/approve',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(approval_data),
                             content_type='application/json')

        assert_success_response(response)

    def test_approve_non_pending_article(self, client, admin_token):
        """测试审核非待审核状态的文章"""
        response = client.post('/API_science/admin/articles/1/approve',
                             headers=get_auth_headers(admin_token))

        # 应该处理这种情况，可能返回错误或保持原状态
        assert response.status_code in [200, 400, 422]

    def test_approve_article_not_found(self, client, admin_token):
        """测试审核不存在的文章"""
        response = client.post('/API_science/admin/articles/999999/approve',
                             headers=get_auth_headers(admin_token))

        assert_error_response(response, 404, '文章不存在')

    def test_approve_article_permission_denied(self, client, user_token):
        """测试普通用户无权审核文章"""
        response = client.post('/API_science/admin/articles/1/approve',
                             headers=get_auth_headers(user_token))

        assert_permission_denied(response)

class TestAdminArticleRejection:
    """管理员文章驳回接口测试"""

    def test_reject_article_success(self, client, admin_token):
        """测试成功驳回文章"""
        rejection_data = {
            'reason': '内容不符合规范，需要修改'
        }

        response = client.post('/API_science/admin/articles/1/reject',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(rejection_data),
                             content_type='application/json')

        assert_success_response(response)
        data = response.get_json()
        if data['success']:
            assert data['data']['status'] == 'rejected'

    def test_reject_article_without_reason(self, client, admin_token):
        """测试驳回文章不提供原因"""
        response = client.post('/API_science/admin/articles/1/reject',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps({}),
                             content_type='application/json')

        # 可能接受也可能拒绝，取决于实现
        assert response.status_code in [200, 400]

    def test_reject_article_not_found(self, client, admin_token):
        """测试驳回不存在的文章"""
        rejection_data = {'reason': '测试驳回'}

        response = client.post('/API_science/admin/articles/999999/reject',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(rejection_data),
                             content_type='application/json')

        assert_error_response(response, 404, '文章不存在')

    def test_reject_article_permission_denied(self, client, user_token):
        """测试普通用户无权驳回文章"""
        rejection_data = {'reason': '测试驳回'}

        response = client.post('/API_science/admin/articles/1/reject',
                             headers=get_auth_headers(user_token),
                             data=json.dumps(rejection_data),
                             content_type='application/json')

        assert_permission_denied(response)

class TestAdminBatchOperations:
    """管理员批量操作接口测试"""

    def test_batch_update_status_success(self, client, admin_token):
        """测试批量更新文章状态"""
        batch_data = {
            'article_ids': [1, 2, 3],
            'status': 'published',
            'review_comment': '批量审核通过'
        }

        response = client.post('/API_science/admin/articles/batch-status',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(batch_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'updated_count' in data['data']
        assert 'failed_count' in data['data']

    def test_batch_update_status_invalid_status(self, client, admin_token):
        """测试批量更新无效状态"""
        batch_data = {
            'article_ids': [1, 2],
            'status': 'invalid_status'
        }

        response = client.post('/API_science/admin/articles/batch-status',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(batch_data),
                             content_type='application/json')

        assert_error_response(response, 400)

    def test_batch_update_empty_ids(self, client, admin_token):
        """测试批量更新空ID列表"""
        batch_data = {
            'article_ids': [],
            'status': 'published'
        }

        response = client.post('/API_science/admin/articles/batch-status',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(batch_data),
                             content_type='application/json')

        assert_error_response(response, 400, '请提供要操作的文章ID列表')

    def test_batch_delete_articles(self, client, admin_token):
        """测试批量删除文章"""
        batch_data = {
            'article_ids': [1, 2, 3]
        }

        response = client.post('/API_science/admin/articles/batch-delete',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(batch_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'deleted_count' in data['data']

    def test_batch_operations_permission_denied(self, client, user_token):
        """测试普通用户无权执行批量操作"""
        batch_data = {
            'article_ids': [1, 2],
            'status': 'published'
        }

        response = client.post('/API_science/admin/articles/batch-status',
                             headers=get_auth_headers(user_token),
                             data=json.dumps(batch_data),
                             content_type='application/json')

        assert_permission_denied(response)

class TestAdminArticleStatistics:
    """管理员文章统计接口测试"""

    def test_get_article_statistics_success(self, client, admin_token):
        """测试成功获取文章统计信息"""
        response = client.get('/API_science/admin/articles/statistics',
                            headers=get_auth_headers(admin_token))

        data = assert_success_response(response)
        stats = data['data']

        # 验证基础统计字段
        required_basic_fields = ['total_articles', 'published_articles', 'pending_articles',
                               'draft_articles', 'rejected_articles']
        for field in required_basic_fields:
            assert field in stats

        # 验证交互统计字段
        if 'interaction_stats' in stats:
            interaction_stats = stats['interaction_stats']
            required_interaction_fields = ['total_views', 'total_likes', 'avg_views_per_article']
            for field in required_interaction_fields:
                assert field in interaction_stats

    def test_get_article_statistics_with_date_range(self, client, admin_token):
        """测试按日期范围获取文章统计"""
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }

        response = client.get('/API_science/admin/articles/statistics',
                            headers=get_auth_headers(admin_token),
                            query_string=params)

        assert_success_response(response)

    def test_get_article_statistics_permission_denied(self, client, user_token):
        """测试普通用户无权获取文章统计"""
        response = client.get('/API_science/admin/articles/statistics',
                            headers=get_auth_headers(user_token))

        assert_permission_denied(response)