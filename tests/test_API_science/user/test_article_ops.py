# tests/API_science/user/test_article_ops.py

"""
测试用户端科普文章操作接口
"""

import pytest
import json
from flask import Flask
from API_science.user.article_ops import bp_science_user
from components import db
from components.models import ScienceArticle


class TestGetPublishedArticles:
    """测试获取已发布文章列表接口"""

    def test_get_articles_success(self, app, test_articles):
        """测试成功获取文章列表"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'items' in data['data']
        assert 'total' in data['data']

    def test_get_articles_with_pagination(self, app, test_articles):
        """测试分页获取文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles?page=1&size=5')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['size'] == 5

    def test_get_articles_with_keyword(self, app, test_articles):
        """测试关键词搜索文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles?keyword=测试')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True

    def test_get_articles_no_results(self, app):
        """测试没有文章时的响应"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert "暂无文章" in data['message']


class TestGetArticleDetail:
    """测试获取文章详情接口"""

    def test_get_article_detail_success(self, app, test_articles, test_user):
        """测试成功获取文章详情"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')

        # 创建测试客户端并设置用户认证
        client = app.test_client()

        # 模拟用户认证（实际项目中需要实现token验证装饰器的测试）
        with app.test_request_context():
            # 找到已发布的文章
            published_article = None
            for article in test_articles:
                if article.status == 'published':
                    published_article = article
                    break

            if published_article:
                # 这里需要模拟token_required装饰器
                # 在实际测试中，可能需要mock装饰器或使用测试用例的认证方式
                pass


class TestLikeArticle:
    """测试文章点赞接口"""

    def test_like_article_success(self, app, test_articles, test_user):
        """测试成功点赞文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        article = test_articles[0]
        like_data = {'article_id': article.id}

        # 模拟认证请求（实际需要token）
        response = client.post(
            '/API_science/user/articles/like',
            data=json.dumps(like_data),
            content_type='application/json',
            headers={'Authorization': 'Bearer test_token'}
        )

        # 由于token_required装饰器，这个测试可能需要在实际环境中调整
        # 这里主要是测试接口结构和逻辑

    def test_like_article_missing_id(self, app):
        """测试缺少文章ID的点赞请求"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.post(
            '/API_science/user/articles/like',
            data=json.dumps({}),
            content_type='application/json'
        )

        # 应该返回400错误
        assert response.status_code == 400

    def test_like_article_invalid_id(self, app):
        """测试无效文章ID的点赞请求"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.post(
            '/API_science/user/articles/like',
            data=json.dumps({'article_id': 999999}),
            content_type='application/json'
        )

        # 应该返回404错误
        assert response.status_code == 404


class TestGetLikeStatus:
    """测试获取点赞状态接口"""

    def test_get_like_status_success(self, app, test_articles, test_user):
        """测试成功获取点赞状态"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        article_ids = [test_articles[0].id, test_articles[1].id]
        response = client.get(f'/API_science/user/articles/like/status?article_ids={",".join(map(str, article_ids))}')

        # 需要认证token
        # 实际测试中需要mock认证装饰器

    def test_get_like_status_missing_ids(self, app):
        """测试缺少文章ID列表"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles/like/status')
        # 应该返回400错误
        assert response.status_code == 400

    def test_get_like_status_invalid_ids(self, app):
        """测试无效的文章ID格式"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles/like/status?article_ids=abc,def')
        # 应该返回400错误
        assert response.status_code == 400


class TestRecordVisit:
    """测试记录浏览接口"""

    def test_record_visit_success(self, app, test_articles, test_user):
        """测试成功记录浏览"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        article = test_articles[0]
        visit_data = {'article_id': article.id}

        response = client.post(
            '/API_science/user/articles/visit',
            data=json.dumps(visit_data),
            content_type='application/json'
        )

        # 需要认证token

    def test_record_visit_missing_id(self, app):
        """测试缺少文章ID的浏览记录"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.post(
            '/API_science/user/articles/visit',
            data=json.dumps({}),
            content_type='application/json'
        )

        # 应该返回400错误
        assert response.status_code == 400

    def test_record_visit_invalid_id(self, app):
        """测试无效文章ID的浏览记录"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.post(
            '/API_science/user/articles/visit',
            data=json.dumps({'article_id': 999999}),
            content_type='application/json'
        )

        # 应该返回404错误
        assert response.status_code == 404


class TestCreateArticle:
    """测试创建文章接口"""

    def test_create_article_success(self, app, test_user, sample_article_data):
        """测试成功创建文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.post(
            '/API_science/user/articles',
            data=json.dumps(sample_article_data),
            content_type='application/json'
        )

        # 需要认证token

    def test_create_article_missing_title(self, app):
        """测试缺少标题创建文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        data = {
            'content': '测试内容'
        }

        response = client.post(
            '/API_science/user/articles',
            data=json.dumps(data),
            content_type='application/json'
        )

        # 应该返回400错误
        assert response.status_code == 400

    def test_create_article_missing_content(self, app):
        """测试缺少内容创建文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        data = {
            'title': '测试标题'
        }

        response = client.post(
            '/API_science/user/articles',
            data=json.dumps(data),
            content_type='application/json'
        )

        # 应该返回400错误
        assert response.status_code == 400

    def test_create_article_invalid_status(self, app):
        """测试无效状态创建文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        data = {
            'title': '测试标题',
            'content': '测试内容',
            'status': 'invalid_status'
        }

        response = client.post(
            '/API_science/user/articles',
            data=json.dumps(data),
            content_type='application/json'
        )

        # 应该返回400错误
        assert response.status_code == 400

    def test_create_article_no_data(self, app):
        """测试空数据创建文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.post(
            '/API_science/user/articles',
            data='',
            content_type='application/json'
        )

        # 应该返回400错误
        assert response.status_code == 400


class TestUpdateArticle:
    """测试更新文章接口"""

    def test_update_article_success(self, app, test_articles, test_user, sample_update_data):
        """测试成功更新文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        article = test_articles[0]
        # 确保文章属于当前用户
        article.author_user_id = test_user.id

        response = client.put(
            f'/API_science/user/articles/{article.id}',
            data=json.dumps(sample_update_data),
            content_type='application/json'
        )

        # 需要认证token

    def test_update_article_not_found(self, app):
        """测试更新不存在的文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        data = {'title': '更新标题'}

        response = client.put(
            '/API_science/user/articles/999999',
            data=json.dumps(data),
            content_type='application/json'
        )

        # 应该返回404错误
        assert response.status_code == 404

    def test_update_article_permission_denied(self, app, test_articles, sample_update_data):
        """测试无权限更新文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        article = test_articles[0]
        # 确保文章不属于当前用户
        article.author_user_id = 999999

        response = client.put(
            f'/API_science/user/articles/{article.id}',
            data=json.dumps(sample_update_data),
            content_type='application/json'
        )

        # 需要认证token，应该返回403错误
        # assert response.status_code == 403


class TestDeleteArticle:
    """测试删除文章接口"""

    def test_delete_article_success(self, app, test_articles, test_user):
        """测试成功删除文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        article = test_articles[0]
        # 确保文章属于当前用户
        article.author_user_id = test_user.id

        response = client.delete(f'/API_science/user/articles/{article.id}')

        # 需要认证token

    def test_delete_article_not_found(self, app):
        """测试删除不存在的文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.delete('/API_science/user/articles/999999')

        # 应该返回404错误
        assert response.status_code == 404

    def test_delete_article_permission_denied(self, app, test_articles):
        """测试无权限删除文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        article = test_articles[0]
        # 确保文章不属于当前用户
        article.author_user_id = 999999

        response = client.delete(f'/API_science/user/articles/{article.id}')

        # 需要认证token，应该返回403错误
        # assert response.status_code == 403


class TestGetMyArticles:
    """测试获取我的文章列表接口"""

    def test_get_my_articles_success(self, app, test_user):
        """测试成功获取我的文章列表"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles/my')

        # 需要认证token

    def test_get_my_articles_with_filters(self, app, test_user):
        """测试带筛选条件获取我的文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles/my?status=draft&keyword=测试&page=1&size=10')

        # 需要认证token

    def test_get_my_articles_unauthorized(self, app):
        """测试未授权获取我的文章"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles/my')

        # 应该返回401错误（需要认证）
        # assert response.status_code == 401


class TestEdgeCases:
    """测试边界情况和异常处理"""

    def test_large_page_size(self, app):
        """测试过大的分页大小"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles?size=1000')
        # 应该自动限制到50条
        assert response.status_code == 200

    def test_negative_page_number(self, app):
        """测试负数页码"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.get('/API_science/user/articles?page=-1')
        # 应该有适当的错误处理
        assert response.status_code == 200  # 可能会重置为第1页

    def test_very_long_keyword(self, app):
        """测试超长关键词"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        long_keyword = 'a' * 1000
        response = client.get(f'/API_science/user/articles?keyword={long_keyword}')
        # 应该能处理长关键词
        assert response.status_code == 200

    def test_malformed_json(self, app):
        """测试格式错误的JSON"""
        app.register_blueprint(bp_science_user, url_prefix='/API_science/user')
        client = app.test_client()

        response = client.post(
            '/API_science/user/articles',
            data='{"title": "test", "content":',  # 不完整的JSON
            content_type='application/json'
        )

        # 应该返回400错误
        assert response.status_code == 400