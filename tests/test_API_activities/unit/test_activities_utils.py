# API_activities 公共工具模块测试用例

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from API_activities.common.utils import (
    ActivityValidator,
    ActivityStatistics,
    ActivityStatusManager,
    ActivitySearchHelper
)
from components.models import Activity, ActivityBooking, ActivityRating


class TestActivityValidator:
    """活动验证器测试"""

    @pytest.fixture
    def sample_activity(self):
        """创建示例活动对象"""
        activity = Mock()
        activity.id = 1
        activity.title = "测试活动"
        activity.status = "published"
        activity.end_time = datetime.now() + timedelta(days=1)
        activity.max_participants = 10
        activity.organizer_user_id = None
        return activity

    @pytest.fixture
    def expired_activity(self):
        """创建已结束的活动对象"""
        activity = Mock()
        activity.id = 2
        activity.title = "已结束活动"
        activity.status = "published"
        activity.end_time = datetime.now() - timedelta(days=1)
        activity.max_participants = 10
        activity.organizer_user_id = None
        return activity

    @pytest.fixture
    def cancelled_activity(self):
        """创建已取消的活动对象"""
        activity = Mock()
        activity.id = 3
        activity.title = "已取消活动"
        activity.status = "cancelled"
        activity.end_time = datetime.now() + timedelta(days=1)
        activity.max_participants = 10
        activity.organizer_user_id = None
        return activity

    def test_is_activity_bookable_success(self, sample_activity):
        """测试活动可预约验证 - 成功案例"""
        # Mock查询返回值为0（当前预约人数）
        with patch('API_activities.common.utils.ActivityBooking') as mock_booking_model:
            mock_query = Mock()
            mock_booking_model.query = mock_query
            mock_query.filter_by.return_value.count.return_value = 0

            can_book, error_msg = ActivityValidator.is_activity_bookable(sample_activity)

            assert can_book is True
            assert error_msg == ""

    def test_is_activity_bookable_activity_not_exist(self):
        """测试活动可预约验证 - 活动不存在"""
        can_book, error_msg = ActivityValidator.is_activity_bookable(None)

        assert can_book is False
        assert error_msg == "活动不存在"

    def test_is_activity_bookable_wrong_status(self, cancelled_activity):
        """测试活动可预约验证 - 状态错误"""
        can_book, error_msg = ActivityValidator.is_activity_bookable(cancelled_activity)

        assert can_book is False
        assert "当前活动状态(cancelled)不允许预约" in error_msg

    def test_is_activity_bookable_expired(self, expired_activity):
        """测试活动可预约验证 - 活动已结束"""
        can_book, error_msg = ActivityValidator.is_activity_bookable(expired_activity)

        assert can_book is False
        assert error_msg == "活动已结束，无法预约"

    def test_is_activity_bookable_full(self, sample_activity):
        """测试活动可预约验证 - 人数已满"""
        with patch('API_activities.common.utils.ActivityBooking') as mock_booking_model:
            mock_query = Mock()
            mock_booking_model.query = mock_query
            # Mock查询返回值等于最大参与人数
            mock_query.filter_by.return_value.count.return_value = sample_activity.max_participants

            can_book, error_msg = ActivityValidator.is_activity_bookable(sample_activity)

            assert can_book is False
            assert error_msg == "活动预约人数已满"

    def test_check_user_booking_conflict_has_conflict(self):
        """检查用户预约冲突 - 有冲突"""
        existing_booking = Mock()
        existing_booking.status = "booked"

        with patch('API_activities.common.utils.ActivityBooking') as mock_booking_model:
            mock_query = Mock()
            mock_booking_model.query = mock_query
            mock_query.filter_by.return_value.first.return_value = existing_booking

            has_conflict, booking = ActivityValidator.check_user_booking_conflict("test_user", 1)

            assert has_conflict is True
            assert booking == existing_booking

    def test_check_user_booking_conflict_no_conflict(self):
        """检查用户预约冲突 - 无冲突"""
        with patch('API_activities.common.utils.ActivityBooking') as mock_booking_model:
            mock_query = Mock()
            mock_booking_model.query = mock_query
            mock_query.filter_by.return_value.first.return_value = None

            has_conflict, booking = ActivityValidator.check_user_booking_conflict("test_user", 1)

            assert has_conflict is False
            assert booking is None

    def test_check_user_booking_conflict_cancelled_booking(self):
        """检查用户预约冲突 - 有已取消的预约记录"""
        cancelled_booking = Mock()
        cancelled_booking.status = "cancelled"

        with patch('API_activities.common.utils.ActivityBooking') as mock_booking_model:
            mock_query = Mock()
            mock_booking_model.query = mock_query
            mock_query.filter_by.return_value.first.return_value = cancelled_booking

            has_conflict, booking = ActivityValidator.check_user_booking_conflict("test_user", 1)

            assert has_conflict is False
            assert booking == cancelled_booking

    def test_can_user_rate_activity_success(self):
        """测试用户评分权限验证 - 成功案例"""
        with patch('API_activities.common.utils.Activity') as mock_activity_model, \
             patch('API_activities.common.utils.ActivityBooking') as mock_booking_model, \
             patch('API_activities.common.utils.ActivityRating') as mock_rating_model:

            # Mock活动存在
            mock_activity = Mock()
            mock_query = Mock()
            mock_activity_model.query = mock_query
            mock_query.get.return_value = mock_activity

            # Mock用户已参与活动
            mock_participation = Mock()
            mock_participation.status = "attended"
            mock_booking_query = Mock()
            mock_booking_model.query = mock_booking_query
            mock_booking_query.filter_by.return_value.first.return_value = mock_participation

            # Mock用户未评分过
            mock_rating_query = Mock()
            mock_rating_model.query = mock_rating_query
            mock_rating_query.filter_by.return_value.first.return_value = None

            can_rate, error_msg = ActivityValidator.can_user_rate_activity(1, 1)

            assert can_rate is True
            assert error_msg == ""

    def test_can_user_rate_activity_not_participated(self):
        """测试用户评分权限验证 - 用户未参与活动"""
        with patch('API_activities.common.utils.Activity') as mock_activity_model, \
             patch('API_activities.common.utils.ActivityBooking') as mock_booking_model:

            # Mock活动存在
            mock_activity = Mock()
            mock_query = Mock()
            mock_activity_model.query = mock_query
            mock_query.get.return_value = mock_activity

            # Mock用户未参与活动
            mock_booking_query = Mock()
            mock_booking_model.query = mock_booking_query
            mock_booking_query.filter_by.return_value.first.return_value = None

            can_rate, error_msg = ActivityValidator.can_user_rate_activity(1, 1)

            assert can_rate is False
            assert error_msg == "您需要参与活动后才能评分"

    def test_can_user_rate_activity_already_rated(self):
        """测试用户评分权限验证 - 用户已评分"""
        with patch('API_activities.common.utils.Activity') as mock_activity_model, \
             patch('API_activities.common.utils.ActivityBooking') as mock_booking_model, \
             patch('API_activities.common.utils.ActivityRating') as mock_rating_model:

            # Mock活动存在
            mock_activity = Mock()
            mock_query = Mock()
            mock_activity_model.query = mock_query
            mock_query.get.return_value = mock_activity

            # Mock用户已参与活动
            mock_participation = Mock()
            mock_participation.status = "attended"
            mock_booking_query = Mock()
            mock_booking_model.query = mock_booking_query
            mock_booking_query.filter_by.return_value.first.return_value = mock_participation

            # Mock用户已评分过
            existing_rating = Mock()
            mock_rating_query = Mock()
            mock_rating_model.query = mock_rating_query
            mock_rating_query.filter_by.return_value.first.return_value = existing_rating

            can_rate, error_msg = ActivityValidator.can_user_rate_activity(1, 1)

            assert can_rate is False
            assert error_msg == "您已经为该活动评过分"

    def test_is_activity_manageable_success(self, sample_activity):
        """测试活动管理权限验证 - 成功案例"""
        can_manage, error_msg = ActivityValidator.is_activity_manageable(sample_activity, 1)

        # 因为organizer_user_id Mock返回None，这个测试会失败，但我们需要测试逻辑
        sample_activity.organizer_user_id = 1
        can_manage, error_msg = ActivityValidator.is_activity_manageable(sample_activity, 1)

        assert can_manage is True
        assert error_msg == ""

    def test_is_activity_manageable_no_permission(self, sample_activity):
        """测试活动管理权限验证 - 无权限"""
        sample_activity.organizer_user_id = 1
        can_manage, error_msg = ActivityValidator.is_activity_manageable(sample_activity, 2)

        assert can_manage is False
        assert error_msg == "无权限管理此活动"

    def test_is_activity_manageable_activity_not_exist(self):
        """测试活动管理权限验证 - 活动不存在"""
        can_manage, error_msg = ActivityValidator.is_activity_manageable(None, 1)

        assert can_manage is False
        assert error_msg == "活动不存在"


class TestActivityStatusManager:
    """活动状态管理器测试"""

    @pytest.fixture
    def sample_activity(self):
        """创建示例活动对象"""
        activity = Mock()
        activity.id = 1
        activity.status = "draft"
        activity.end_time = datetime.now() - timedelta(days=1)  # 已结束
        return activity

    def test_update_activity_status_valid_transition(self, sample_activity):
        """测试更新活动状态 - 有效状态转换"""
        success, error_msg = ActivityStatusManager.update_activity_status(
            sample_activity, "published", 1
        )

        assert success is True
        assert "活动状态已从" in error_msg
        assert sample_activity.status == "published"

    def test_update_activity_status_invalid_status(self, sample_activity):
        """测试更新活动状态 - 无效状态"""
        success, error_msg = ActivityStatusManager.update_activity_status(
            sample_activity, "invalid_status", 1
        )

        assert success is False
        assert "无效的活动状态" in error_msg

    def test_update_activity_status_invalid_transition(self, sample_activity):
        """测试更新活动状态 - 无效状态转换"""
        sample_activity.status = "completed"
        success, error_msg = ActivityStatusManager.update_activity_status(
            sample_activity, "draft", 1
        )

        assert success is False
        assert "无法从状态" in error_msg

    def test_update_activity_status_completed_validation(self, sample_activity):
        """测试更新活动状态 - 完成状态特殊验证"""
        sample_activity.status = "published"
        sample_activity.end_time = datetime.now() + timedelta(days=1)  # 未结束

        success, error_msg = ActivityStatusManager.update_activity_status(
            sample_activity, "completed", 1
        )

        assert success is False
        assert error_msg == "活动尚未结束，无法标记为完成"

    def test_get_status_flow_info(self):
        """测试获取状态流转信息"""
        flow_info = ActivityStatusManager.get_status_flow_info()

        assert isinstance(flow_info, dict)
        assert "draft" in flow_info
        assert "published" in flow_info
        assert "cancelled" in flow_info
        assert "completed" in flow_info

        # 检查草稿状态信息
        draft_info = flow_info["draft"]
        assert draft_info["description"] == "草稿状态"
        assert "published" in draft_info["next_statuses"]
        assert draft_info["can_book"] is False
        assert draft_info["can_rate"] is False


class TestActivitySearchHelper:
    """活动搜索辅助工具测试"""

    def test_build_activity_query_with_filters(self):
        """测试构建活动查询 - 带筛选条件"""
        filters = {
            'status': 'published',
            'organizer_user_id': 1,
            'keyword': 'test',
            'tags': ['sports'],
            'start_time_from': datetime.now(),
            'start_time_to': datetime.now() + timedelta(days=7)
        }

        with patch('API_activities.common.utils.Activity') as mock_activity_model:
            # 创建链式Mock对象 - 每次filter调用都返回同一个mock对象
            mock_query = Mock()

            # 确保链式调用正常工作：query.filter().filter()...返回同一个对象
            mock_query.filter.return_value = mock_query

            # 设置Activity.query
            mock_activity_model.query = mock_query

            # Mock Activity模型的字段以支持比较操作
            mock_activity_model.status = Mock()
            mock_activity_model.organizer_user_id = Mock()
            mock_activity_model.title = Mock()
            mock_activity_model.description = Mock()
            mock_activity_model.location = Mock()
            mock_activity_model.tags = Mock()
            mock_activity_model.start_time = Mock()
            mock_activity_model.end_time = Mock()

            # Mock like和contains方法
            mock_activity_model.title.like.return_value = Mock()
            mock_activity_model.description.like.return_value = Mock()
            mock_activity_model.location.like.return_value = Mock()
            mock_activity_model.tags.contains.return_value = Mock()

            # Mock比较操作符 - 创建比较表达式对象
            mock_activity_model.start_time.__ge__ = Mock(return_value=Mock())
            mock_activity_model.start_time.__le__ = Mock(return_value=Mock())
            mock_activity_model.end_time.__ge__ = Mock(return_value=Mock())
            mock_activity_model.end_time.__le__ = Mock(return_value=Mock())

            result = ActivitySearchHelper.build_activity_query(filters)

            # 验证链式调用
            assert mock_query.filter.called
            # build_activity_query应该返回最终的查询对象
            assert result == mock_query

    def test_build_activity_query_empty_filters(self):
        """测试构建活动查询 - 空筛选条件"""
        with patch('API_activities.common.utils.Activity') as mock_activity_model:
            mock_query_instance = Mock()
            mock_activity_model.query = mock_query_instance

            result = ActivitySearchHelper.build_activity_query({})

            assert result == mock_query_instance
            # 确保没有调用filter
            mock_query_instance.filter.assert_not_called()

    def test_build_activity_query_keyword_search(self):
        """测试构建活动查询 - 关键词搜索"""
        filters = {'keyword': '测试活动'}

        with patch('API_activities.common.utils.Activity') as mock_activity_model:
            mock_query_instance = Mock()
            mock_activity_model.query = mock_query_instance

            result = ActivitySearchHelper.build_activity_query(filters)

            # 验证关键词搜索逻辑
            assert mock_query_instance.filter.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])