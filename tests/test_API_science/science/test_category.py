# tests/API_science/science/test_category.py

"""
测试科普业务公共接口
"""

import pytest
import json
from flask import Flask
from API_science.science.category import bp_science_category
from components import db
from components.models import ScienceArticle


class TestGetPopularArticles:
    """测试获取热门文章接口"""

    def test_get_popular_articles_success(self, app, test_articles):
        """测试成功获取热门文章"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/popular')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'articles' in data['data']
        assert 'total' in data['data']

    def test_get_popular_articles_with_limit(self, app, test_articles):
        """测试指定限制数量获取热门文章"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/popular?limit=5')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            assert len(data['data']['articles']) <= 5

    def test_get_popular_articles_with_time_range(self, app, test_articles):
        """测试指定时间范围获取热门文章"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/popular?days=7')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            assert data['data']['time_range_days'] == 7

    def test_get_popular_articles_large_limit(self, app, test_articles):
        """测试过大的限制数量"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/popular?limit=1000')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            assert data['data']['limit'] == 50  # 应该被限制到50

    def test_get_popular_articles_no_articles(self, app):
        """测试没有文章时的热门文章获取"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/popular')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['articles']) == 0


class TestGetLatestArticles:
    """测试获取最新文章接口"""

    def test_get_latest_articles_success(self, app, test_articles):
        """测试成功获取最新文章"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/latest')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'articles' in data['data']
        assert 'total' in data['data']

    def test_get_latest_articles_with_limit(self, app, test_articles):
        """测试指定限制数量获取最新文章"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/latest?limit=3')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            assert len(data['data']['articles']) <= 3

    def test_get_latest_articles_ordering(self, app, test_articles):
        """测试最新文章排序"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/latest')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success'] and data['data']['articles']:
            # 验证文章按发布时间降序排列
            articles = data['data']['articles']
            for i in range(len(articles) - 1):
                current = articles[i]
                next_article = articles[i + 1]
                if current['published_at'] and next_article['published_at']:
                    assert current['published_at'] >= next_article['published_at']

    def test_get_latest_articles_publish_desc(self, app, test_articles):
        """测试最新文章发布描述"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/latest')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success'] and data['data']['articles']:
            # 验证每篇文章都有发布描述
            for article in data['data']['articles']:
                assert 'publish_desc' in article


class TestGetFeaturedArticles:
    """测试获取精选文章接口"""

    def test_get_featured_articles_success(self, app, test_articles):
        """测试成功获取精选文章"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/featured')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'articles' in data['data']
        assert 'total' in data['data']

    def test_get_featured_articles_with_min_likes(self, app, test_articles):
        """测试指定最小点赞数获取精选文章"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/featured?min_likes=20')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            assert data['data']['min_likes'] == 20
            # 验证返回的文章都符合最小点赞数要求
            for article in data['data']['articles']:
                assert article['like_count'] >= 20

    def test_get_featured_articles_with_limit(self, app, test_articles):
        """测试指定限制数量获取精选文章"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/featured?limit=5')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            assert len(data['data']['articles']) <= 5

    def test_get_featured_articles_scoring(self, app, test_articles):
        """测试精选文章评分"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/featured')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success'] and data['data']['articles']:
            # 验证每篇文章都有精选评分
            for article in data['data']['articles']:
                assert 'featured_score' in article
                assert isinstance(article['featured_score'], int)


class TestSearchArticles:
    """测试高级搜索文章接口"""

    def test_search_articles_basic(self, app, test_articles):
        """测试基础搜索功能"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/search?keyword=测试')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True

    def test_search_articles_with_all_parameters(self, app, test_articles):
        """测试使用所有搜索参数"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        params = {
            'keyword': '测试',
            'status': 'published',
            'min_likes': '5',
            'max_likes': '50',
            'min_views': '10',
            'max_views': '1000',
            'sort_by': 'like_count',
            'sort_order': 'desc',
            'page': '1',
            'size': '10'
        }

        response = client.get(f'/API_science/science/articles/search?{ "&".join([f"{k}={v}" for k, v in params.items()])}')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True

    def test_search_articles_with_date_range(self, app, test_articles):
        """测试日期范围搜索"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/search?date_from=2023-01-01&date_to=2023-12-31')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True

    def test_search_articles_invalid_date_format(self, app):
        """测试无效日期格式"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/search?date_from=invalid-date')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert "日期格式错误" in data['message']

    def test_search_articles_invalid_sort_order(self, app, test_articles):
        """测试无效排序方向"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/search?sort_order=invalid')
        assert response.status_code == 200  # 应该默认处理为合法值

    def test_search_articles_pagination(self, app, test_articles):
        """测试搜索结果分页"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/search?page=1&size=5')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            assert 'page' in data['data']
            assert 'size' in data['data']
            assert 'total' in data['data']

    def test_search_large_page_size(self, app, test_articles):
        """测试过大的分页大小"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/search?size=1000')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            assert data['data']['size'] == 50  # 应该被限制到50

    def test_search_no_results(self, app):
        """测试搜索无结果"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/search?keyword=不存在的关键词')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert "没有找到" in data['message']


class TestGetArticlesStatistics:
    """测试获取文章统计信息接口"""

    def test_get_statistics_success(self, app, test_articles):
        """测试成功获取统计信息"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/statistics')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'overview' in data['data']
        assert 'status_distribution' in data['data']
        assert 'recent_activity' in data['data']
        assert 'popular_keywords' in data['data']

    def test_get_statistics_data_structure(self, app, test_articles):
        """测试统计信息数据结构"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/statistics')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            overview = data['data']['overview']
            expected_overview_fields = [
                'total_published', 'total_likes', 'total_views',
                'avg_likes_per_article', 'avg_views_per_article'
            ]
            for field in expected_overview_fields:
                assert field in overview

            status_distribution = data['data']['status_distribution']
            assert isinstance(status_distribution, dict)

            recent_activity = data['data']['recent_activity']
            expected_activity_fields = [
                'published_last_30_days', 'likes_last_30_days', 'views_last_30_days'
            ]
            for field in expected_activity_fields:
                assert field in recent_activity

    def test_get_statistics_empty_database(self, app):
        """测试空数据库的统计信息"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/statistics')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        # 应该处理零值情况，不出现除零错误


class TestGetArticleRecommendations:
    """测试获取文章推荐接口"""

    def test_get_recommendations_with_article_id(self, app, test_articles):
        """测试基于文章ID获取推荐"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        article = test_articles[0]
        response = client.get(f'/API_science/science/articles/recommendations?article_id={article.id}')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'recommendations' in data['data']
        assert 'based_on' in data['data']

    def test_get_recommendations_without_article_id(self, app, test_articles):
        """测试不指定文章ID获取推荐（热门文章）"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/recommendations')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'recommendations' in data['data']
        assert 'based_on' in data['data']

    def test_get_recommendations_with_limit(self, app, test_articles):
        """测试指定限制数量获取推荐"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/recommendations?limit=3')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            assert len(data['data']['recommendations']) <= 3

    def test_get_recommendations_invalid_article_id(self, app):
        """测试无效文章ID获取推荐"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/articles/recommendations?article_id=999999')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        # 应该返回热门文章作为推荐


class TestHealthCheck:
    """测试健康检查接口"""

    def test_health_check_success(self, app, test_articles):
        """测试健康检查成功"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/health')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'status' in data['data']
        assert 'module' in data['data']
        assert 'database' in data['data']
        assert 'endpoints' in data['data']

    def test_health_check_data_structure(self, app, test_articles):
        """测试健康检查数据结构"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        response = client.get('/API_science/science/health')
        assert response.status_code == 200

        data = json.loads(response.data)
        if data['success']:
            health_data = data['data']
            assert health_data['status'] == 'healthy'
            assert health_data['module'] == 'science_category'
            assert 'timestamp' in health_data
            assert health_data['database']['connected'] is True
            assert 'article_count' in health_data['database']
            assert isinstance(health_data['endpoints'], list)


class TestEdgeCases:
    """测试边界情况和异常处理"""

    def test_negative_parameters(self, app, test_articles):
        """测试负数参数"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        # 测试负数限制
        response = client.get('/API_science/science/articles/popular?limit=-5')
        assert response.status_code == 200

        # 测试负数天数
        response = client.get('/API_science/science/articles/popular?days=-30')
        assert response.status_code == 200

        # 测试负数最小点赞数
        response = client.get('/API_science/science/articles/featured?min_likes=-10')
        assert response.status_code == 200

    def test_very_long_parameters(self, app, test_articles):
        """测试超长参数"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        long_keyword = 'a' * 1000
        response = client.get(f'/API_science/science/articles/search?keyword={long_keyword}')
        assert response.status_code == 200

    def test_special_characters(self, app, test_articles):
        """测试特殊字符"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        special_chars = '!@#$%^&*()[]{}|\\:";\'<>?,./'
        response = client.get(f'/API_science/science/articles/search?keyword={special_chars}')
        assert response.status_code == 200

    def test_unicode_characters(self, app, test_articles):
        """测试Unicode字符"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        unicode_chars = '测试🚀emoji'
        response = client.get(f'/API_science/science/articles/search?keyword={unicode_chars}')
        assert response.status_code == 200

    def test_sql_injection_attempts(self, app):
        """测试SQL注入尝试"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        # 尝试SQL注入
        malicious_keyword = "'; DROP TABLE science_articles; --"
        response = client.get(f'/API_science/science/articles/search?keyword={malicious_keyword}')
        assert response.status_code == 200  # 应该安全处理

    def test_xss_attempts(self, app):
        """测试XSS攻击尝试"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        # 尝试XSS攻击
        xss_payload = '<script>alert("xss")</script>'
        response = client.get(f'/API_science/science/articles/search?keyword={xss_payload}')
        assert response.status_code == 200  # 应该安全处理

    def test_concurrent_requests(self, app, test_articles):
        """测试并发请求（简单的重复请求测试）"""
        app.register_blueprint(bp_science_category, url_prefix='/API_science/science')
        client = app.test_client()

        # 发送多个相同请求
        for _ in range(10):
            response = client.get('/API_science/science/articles/popular')
            assert response.status_code == 200

    def test_database_error_simulation(self, app):
        """测试数据库错误模拟"""
        # 这个测试需要特定的数据库错误模拟
        # 在实际测试中可能需要mock数据库操作
        pass