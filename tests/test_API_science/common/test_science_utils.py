# tests/API_science/common/test_utils.py

"""
测试公共工具函数
"""

import pytest
from datetime import datetime
from API_science.common.utils import (
    validate_article_data,
    get_user_identifier,
    format_article_data,
    build_article_query,
    record_article_visit,
    toggle_article_like,
    get_like_status,
    check_article_permission
)


class TestValidateArticleData:
    """测试文章数据校验"""

    def test_validate_complete_valid_data(self):
        """测试完整有效数据"""
        data = {
            'title': '测试标题',
            'content': '测试内容',
            'status': 'published',
            'cover_image': 'https://example.com/image.jpg'
        }
        is_valid, error = validate_article_data(data, require_all=True)
        assert is_valid is True
        assert error is None

    def test_validate_missing_title(self):
        """测试缺少标题"""
        data = {
            'content': '测试内容'
        }
        is_valid, error = validate_article_data(data, require_all=True)
        assert is_valid is False
        assert error == "标题不能为空"

    def test_validate_missing_content(self):
        """测试缺少内容"""
        data = {
            'title': '测试标题'
        }
        is_valid, error = validate_article_data(data, require_all=True)
        assert is_valid is False
        assert error == "内容不能为空"

    def test_validate_invalid_status(self):
        """测试无效状态"""
        data = {
            'title': '测试标题',
            'content': '测试内容',
            'status': 'invalid_status'
        }
        is_valid, error = validate_article_data(data, require_all=True)
        assert is_valid is False
        assert "状态无效" in error

    def test_validate_title_too_long(self):
        """测试标题过长"""
        data = {
            'title': 'a' * 201,  # 超过200字符
            'content': '测试内容'
        }
        is_valid, error = validate_article_data(data, require_all=True)
        assert is_valid is False
        assert "标题长度不能超过200" in error

    def test_validate_partial_data(self):
        """测试部分数据（require_all=False）"""
        data = {
            'title': '测试标题'
        }
        is_valid, error = validate_article_data(data, require_all=False)
        assert is_valid is True
        assert error is None

    def test_validate_empty_data(self):
        """测试空数据"""
        is_valid, error = validate_article_data(None, require_all=True)
        assert is_valid is False
        assert error == "请求数据不能为空"


class TestFormatArticleData:
    """测试文章数据格式化"""

    def test_format_basic_article(self, test_articles):
        """测试基础文章格式化"""
        article = test_articles[0]  # draft 状态文章
        data = format_article_data(article)

        assert 'id' in data
        assert 'title' in data
        assert 'content' not in data  # 默认不包含内容
        assert 'status' in data
        assert 'like_count' in data
        assert 'view_count' in data
        assert 'author_display' in data
        assert 'created_at' in data
        assert 'updated_at' in data

    def test_format_article_with_content(self, test_articles):
        """测试包含内容的文章格式化"""
        article = test_articles[0]
        data = format_article_data(article, include_content=True)

        assert 'content' in data
        assert data['content'] == article.content

    def test_format_article_with_like_status(self, test_articles, mock_current_user):
        """测试包含点赞状态的文章格式化"""
        article = test_articles[0]
        data = format_article_data(article, include_like_status=True, current_user=mock_current_user)

        assert 'is_liked' in data
        assert isinstance(data['is_liked'], bool)

    def test_format_published_article_dates(self, test_articles):
        """测试已发布文章的日期格式化"""
        published_article = None
        for article in test_articles:
            if article.status == 'published':
                published_article = article
                break

        if published_article:
            data = format_article_data(published_article)
            assert 'published_at' in data
            assert data['published_at'] is not None


class TestBuildArticleQuery:
    """测试文章查询构建"""

    def test_build_basic_query(self):
        """测试基础查询构建"""
        query = build_article_query()
        # 应该返回一个查询对象
        assert query is not None

    def test_build_query_with_status(self):
        """测试带状态的查询构建"""
        query = build_article_query(status='published')
        # 验证查询包含状态筛选
        assert query is not None

    def test_build_query_with_keyword(self):
        """测试带关键词的查询构建"""
        query = build_article_query(keyword='测试')
        assert query is not None

    def test_build_query_with_author(self):
        """测试带作者的查询构建"""
        query = build_article_query(author_id=1)
        assert query is not None

    def test_build_query_combined(self):
        """测试组合条件查询构建"""
        query = build_article_query(
            status='published',
            keyword='测试',
            author_id=1
        )
        assert query is not None


class TestUserIdentifier:
    """测试用户标识符获取"""

    def test_get_user_identifier_from_regular_user(self, test_user):
        """测试从普通用户获取标识符"""
        class MockUser:
            def __init__(self, user):
                self.account = user.account
                self.is_deleted = user.is_deleted
                self.id = user.id

        mock_user = MockUser(test_user)
        user_id, user_type, user_obj = get_user_identifier(mock_user)

        assert user_id == test_user.id
        assert user_type == 'user'

    def test_get_user_identifier_from_admin(self, test_admin):
        """测试从管理员获取标识符"""
        class MockAdmin:
            def __init__(self, admin):
                self.account = admin.account
                self.role = admin.role
                self.id = admin.id

        mock_admin = MockAdmin(test_admin)
        # 注意：这里需要数据库中有对应的管理员记录
        # 在实际测试中需要使用适当的测试夹具


class TestRecordArticleVisit:
    """测试文章浏览记录"""

    def test_record_new_visit(self, app, test_user, test_articles):
        """测试记录新的浏览"""
        with app.app_context():
            article = test_articles[0]
            class MockUser:
                account = test_user.account
                is_deleted = test_user.is_deleted
                id = test_user.id

            success, message, visit_data = record_article_visit(article.id, MockUser())
            assert success is True
            assert "成功" in message
            assert visit_data is not None
            assert visit_data['article_id'] == article.id

    def test_record_duplicate_visit(self, app, test_user, test_articles):
        """测试重复浏览记录"""
        with app.app_context():
            article = test_articles[0]
            class MockUser:
                account = test_user.account
                is_deleted = test_user.is_deleted
                id = test_user.id

            # 第一次记录
            record_article_visit(article.id, MockUser())
            # 第二次记录（应该更新时间）
            success, message, visit_data = record_article_visit(article.id, MockUser())
            assert success is True
            assert "更新浏览记录" in message

    def test_record_visit_invalid_article(self, test_user):
        """测试浏览不存在的文章"""
        class MockUser:
            account = test_user.account
            is_deleted = test_user.is_deleted
            id = test_user.id

        success, message, visit_data = record_article_visit(999999, MockUser())
        assert success is False
        assert "不存在" in message


class TestToggleArticleLike:
    """测试文章点赞切换"""

    def test_like_article(self, app, test_user, test_articles):
        """测试点赞文章"""
        with app.app_context():
            article = test_articles[0]
            class MockUser:
                account = test_user.account
                is_deleted = test_user.is_deleted
                id = test_user.id

            success, message, like_data = toggle_article_like(article.id, MockUser())
            assert success is True
            assert "点赞成功" in message
            assert like_data['is_liked'] is True
            assert like_data['article_id'] == article.id

    def test_unlike_article(self, app, test_user, test_articles):
        """测试取消点赞文章"""
        with app.app_context():
            article = test_articles[0]
            class MockUser:
                account = test_user.account
                is_deleted = test_user.is_deleted
                id = test_user.id

            # 先点赞
            toggle_article_like(article.id, MockUser())
            # 再取消点赞
            success, message, like_data = toggle_article_like(article.id, MockUser())
            assert success is True
            assert "取消点赞成功" in message
            assert like_data['is_liked'] is False

    def test_like_invalid_article(self, test_user):
        """测试点赞不存在的文章"""
        class MockUser:
            account = test_user.account
            is_deleted = test_user.is_deleted
            id = test_user.id

        success, message, like_data = toggle_article_like(999999, MockUser())
        assert success is False
        assert "不存在" in message


class TestGetLikeStatus:
    """测试获取点赞状态"""

    def test_get_like_status_single_article(self, app, test_user, test_articles):
        """测试获取单篇文章点赞状态"""
        with app.app_context():
            article = test_articles[0]
            class MockUser:
                account = test_user.account
                is_deleted = test_user.is_deleted
                id = test_user.id

            # 先点赞
            toggle_article_like(article.id, MockUser())
            # 获取状态
            success, message, status_data = get_like_status([article.id], MockUser())
            assert success is True
            assert status_data is not None
            assert status_data['article_like_status'][article.id] is True

    def test_get_like_status_multiple_articles(self, app, test_user, test_articles):
        """测试获取多篇文章点赞状态"""
        with app.app_context():
            article_ids = [test_articles[0].id, test_articles[1].id]
            class MockUser:
                account = test_user.account
                is_deleted = test_user.is_deleted
                id = test_user.id

            success, message, status_data = get_like_status(article_ids, MockUser())
            assert success is True
            assert status_data is not None
            assert status_data['total_articles'] == len(article_ids)


class TestCheckArticlePermission:
    """测试文章权限检查"""

    def test_author_permission(self, test_articles, mock_current_user):
        """测试作者权限"""
        # 创建一个属于测试用户的文章
        article = test_articles[0]
        article.author_user_id = mock_current_user.id

        has_permission, error = check_article_permission(article, mock_current_user)
        assert has_permission is True
        assert error is None

    def test_non_author_permission_denied(self, test_articles, mock_current_user):
        """测试非作者权限被拒绝"""
        # 确保文章不属于当前用户
        article = test_articles[0]
        article.author_user_id = 999999  # 不同的用户ID

        has_permission, error = check_article_permission(article, mock_current_user)
        assert has_permission is False
        assert "无权限" in error

    def test_admin_permission(self, test_articles, mock_current_admin):
        """测试管理员权限"""
        # 管理员应该可以操作所有文章
        article = test_articles[0]

        has_permission, error = check_article_permission(article, mock_current_admin, require_admin=False)
        assert has_permission is True
        assert error is None

    def test_admin_required_permission(self, test_articles, mock_current_user):
        """测试需要管理员权限的检查"""
        article = test_articles[0]

        has_permission, error = check_article_permission(article, mock_current_user, require_admin=True)
        assert has_permission is False
        assert "需要管理员权限" in error