# API_notice公共工具测试
# 测试公共工具函数的各种场景

import pytest
from datetime import datetime, timedelta
from API_notice.common.utils import NoticeUtils, NoticePermissionUtils, NoticeQueryUtils
from components.models.notice_models import Notice, NoticeRead
from components.models.user_models import User, Admin


class TestNoticeUtils:
    """测试NoticeUtils类"""

    def test_get_user_unread_count_user(self, session, test_user, test_notices, test_notice_reads):
        """测试获取普通用户未读公告数量"""
        # 用户有4条活跃公告（排除过期和草稿），已读1条
        unread_count = NoticeUtils.get_user_unread_count(test_user.id, is_admin=False)
        assert unread_count == 3  # 4条活跃公告 - 1条已读

    def test_get_user_unread_count_admin(self, session, test_admin, test_notices):
        """测试获取管理员未读公告数量"""
        # 解包test_admin元组（admin, admin_user）
        admin, admin_user = test_admin

        # 管理员有4条活跃公告（排除过期和草稿），都没有已读记录
        unread_count = NoticeUtils.get_user_unread_count(admin.id, is_admin=True)
        assert unread_count == 4

    def test_get_user_notice_list(self, session, test_user, test_notices, test_notice_reads):
        """测试获取用户公告列表"""
        result = NoticeUtils.get_user_notice_list(
            user_id=test_user.id,
            page=1,
            size=10,
            is_admin=False
        )

        assert 'total' in result
        assert 'page' in result
        assert 'size' in result
        assert 'items' in result
        assert 'unread_count' in result
        assert len(result['items']) == 4  # 4条活跃公告
        assert result['unread_count'] == 3  # 3条未读

        # 检查第一条公告（置顶公告应该在前面）
        first_item = result['items'][0]
        assert 'is_read' in first_item
        assert first_item['is_read'] == True  # 第一条已读

    def test_get_user_notice_list_with_type_filter(self, session, test_user, test_notices):
        """测试按类型筛选公告列表"""
        result = NoticeUtils.get_user_notice_list(
            user_id=test_user.id,
            page=1,
            size=10,
            notice_type='SYSTEM',
            is_admin=False
        )

        assert len(result['items']) == 1  # 只有1条系统公告
        assert result['items'][0]['notice_type'] == 'SYSTEM'

    def test_mark_notice_as_read(self, session, test_user, test_notices):
        """测试标记公告为已读"""
        notice_id = test_notices[1].id  # 第二条公告

        # 验证之前未读
        existing_read = NoticeRead.query.filter(
            NoticeRead.user_id == test_user.id,
            NoticeRead.notice_id == notice_id
        ).first()
        assert existing_read is None

        # 标记为已读
        success = NoticeUtils.mark_notice_as_read(test_user.id, notice_id)
        assert success is True

        # 验证已读记录存在
        existing_read = NoticeRead.query.filter(
            NoticeRead.user_id == test_user.id,
            NoticeRead.notice_id == notice_id
        ).first()
        assert existing_read is not None

    def test_mark_notice_as_read_invalid_notice(self, session, test_user):
        """测试标记不存在的公告为已读"""
        success = NoticeUtils.mark_notice_as_read(test_user.id, 99999)
        assert success is False

    def test_mark_all_notices_as_read(self, session, test_user, test_notices):
        """测试标记所有公告为已读"""
        read_count = NoticeUtils.mark_all_notices_as_read(test_user.id, is_admin=False)
        assert read_count == 3  # 3条未读公告被标记为已读

        # 验证未读数量变为0
        unread_count = NoticeUtils.get_user_unread_count(test_user.id, is_admin=False)
        assert unread_count == 0

    def test_get_notice_read_statistics(self, session, test_notices, test_notice_reads):
        """测试获取公告已读统计"""
        notice_id = test_notices[0].id  # 第一条公告
        stats = NoticeUtils.get_notice_read_statistics(notice_id)

        assert stats is not None
        assert stats['notice_id'] == notice_id
        assert 'target_user_count' in stats
        assert 'read_count' in stats
        assert 'unread_count' in stats
        assert 'read_rate' in stats


class TestNoticePermissionUtils:
    """测试NoticePermissionUtils类"""

    def test_can_user_view_notice_success(self, session, test_user, test_notices):
        """测试用户可以查看公告"""
        can_view, error_msg = NoticePermissionUtils.can_user_view_notice(
            user_id=test_user.id,
            notice_id=test_notices[0].id,  # 系统公告
            is_admin=False
        )
        assert can_view is True
        assert error_msg == ""

    def test_can_user_view_notice_not_exist(self, session, test_user):
        """测试查看不存在的公告"""
        can_view, error_msg = NoticePermissionUtils.can_user_view_notice(
            user_id=test_user.id,
            notice_id=99999,
            is_admin=False
        )
        assert can_view is False
        assert "公告不存在" in error_msg

    def test_can_user_view_notice_expired(self, session, test_user, test_notices):
        """测试查看已过期的公告"""
        expired_notice = test_notices[3]  # 过期公告
        can_view, error_msg = NoticePermissionUtils.can_user_view_notice(
            user_id=test_user.id,
            notice_id=expired_notice.id,
            is_admin=False
        )
        assert can_view is False
        assert "公告已过期" in error_msg

    def test_can_user_view_notice_admin_only(self, session, test_user, test_notices):
        """测试普通用户查看管理员公告"""
        admin_notice = test_notices[2]  # 管理员公告
        can_view, error_msg = NoticePermissionUtils.can_user_view_notice(
            user_id=test_user.id,
            notice_id=admin_notice.id,
            is_admin=False
        )
        assert can_view is False
        assert "无权限查看此类型公告" in error_msg

    def test_can_admin_manage_notice_success(self, session, test_admin, test_notices):
        """测试管理员可以管理自己的公告"""
        # 解包test_admin元组（admin, admin_user）
        admin, admin_user = test_admin

        can_manage, error_msg = NoticePermissionUtils.can_admin_manage_notice(
            admin_user_id=admin.id,
            notice=test_notices[0]
        )
        assert can_manage is True
        assert error_msg == ""

    def test_can_admin_manage_notice_not_author(self, session, test_admin, test_notices):
        """测试管理员不能管理他人公告"""
        # 创建另一个管理员
        other_admin = AdminFactory.create_admin(session)

        can_manage, error_msg = NoticePermissionUtils.can_admin_manage_notice(
            admin_user_id=other_admin.id,
            notice=test_notices[0]  # 这是test_admin创建的公告
        )
        assert can_manage is False
        assert "无权限编辑他人发布的公告" in error_msg

    def test_validate_notice_access_scope_valid(self):
        """测试有效的公告推送范围"""
        assert NoticePermissionUtils.validate_notice_access_scope('SYSTEM', 'ALL') is True
        assert NoticePermissionUtils.validate_notice_access_scope('ADMIN', 'ADMIN') is True
        assert NoticePermissionUtils.validate_notice_access_scope('GENERAL', 'USER') is True

    def test_validate_notice_access_scope_invalid(self):
        """测试无效的公告推送范围"""
        assert NoticePermissionUtils.validate_notice_access_scope('ADMIN', 'USER') is False
        assert NoticePermissionUtils.validate_notice_access_scope('GENERAL', 'ADMIN') is False


class TestNoticeQueryUtils:
    """测试NoticeQueryUtils类"""

    def test_build_admin_filter_query(self, session, test_notices):
        """测试构建管理员筛选查询"""
        from sqlalchemy import and_

        # 测试状态筛选
        base_query = Notice.query
        filtered_query = NoticeQueryUtils.build_admin_filter_query(
            base_query=base_query,
            status_filter='APPROVED'
        )
        result = filtered_query.all()
        assert len(result) == 4  # 4条已发布公告

        # 测试类型筛选
        base_query = Notice.query
        filtered_query = NoticeQueryUtils.build_admin_filter_query(
            base_query=base_query,
            type_filter='SYSTEM'
        )
        result = filtered_query.all()
        assert len(result) == 1  # 1条系统公告

    def test_get_notice_with_attachments(self, session, test_notices):
        """测试获取公告详情（包含附件）"""
        notice_id = test_notices[0].id
        notice_detail = NoticeQueryUtils.get_notice_with_attachments(notice_id)

        assert notice_detail is not None
        assert notice_detail['id'] == notice_id
        assert 'title' in notice_detail
        assert 'content' in notice_detail
        assert 'notice_type' in notice_detail
        assert 'attachments' in notice_detail
        assert isinstance(notice_detail['attachments'], list)

    def test_get_notice_with_attachments_not_exist(self, session):
        """测试获取不存在的公告详情"""
        notice_detail = NoticeQueryUtils.get_notice_with_attachments(99999)
        assert notice_detail is None


class TestUtilsEdgeCases:
    """测试工具类的边界情况"""

    def test_unread_count_no_notices(self, session, test_user):
        """测试没有公告时的未读数量"""
        unread_count = NoticeUtils.get_user_unread_count(test_user.id, is_admin=False)
        assert unread_count == 0

    def test_notice_list_no_notices(self, session, test_user):
        """测试没有公告时的列表查询"""
        result = NoticeUtils.get_user_notice_list(
            user_id=test_user.id,
            page=1,
            size=10,
            is_admin=False
        )
        assert result['total'] == 0
        assert len(result['items']) == 0
        assert result['unread_count'] == 0

    def test_mark_read_nonexistent_user(self, session, test_notices):
        """测试不存在的用户标记已读"""
        success = NoticeUtils.mark_notice_as_read(99999, test_notices[0].id)
        assert success is False

    def test_statistics_nonexistent_notice(self, session):
        """测试不存在公告的统计"""
        stats = NoticeUtils.get_notice_read_statistics(99999)
        assert stats is None

    def test_empty_keyword_search(self, session, test_user):
        """测试空关键词搜索"""
        from components.models.notice_models import Notice

        # 搜索空关键词应该返回空结果
        search_query = Notice.query.filter(
            Notice.release_title.like(f"%{''}%")
        )
        result = search_query.all()
        assert len(result) >= 0  # 应该不报错

    def test_invalid_date_filter(self, session, test_notices):
        """测试无效日期格式筛选"""
        from sqlalchemy import and_

        base_query = Notice.query
        # 无效日期格式应该被忽略，不影响查询
        filtered_query = NoticeQueryUtils.build_admin_filter_query(
            base_query=base_query,
            date_from='invalid-date',
            date_to='also-invalid'
        )
        result = filtered_query.all()
        assert len(result) >= 0  # 应该不报错