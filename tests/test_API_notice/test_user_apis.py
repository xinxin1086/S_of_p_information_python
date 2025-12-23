# API_notice用户端接口测试
# 测试用户端公告操作的各种接口

import pytest
import json
from datetime import datetime, timedelta
from flask import Flask


class TestNoticeListAPI:
    """测试公告列表接口"""

    def test_get_notice_list_success(self, client, session, test_user, test_notices, mock_token_required):
        """测试获取公告列表成功"""
        # 模拟用户登录
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/list?page=1&size=5')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'items' in data['data']
        assert 'unread_count' in data['data']
        assert len(data['data']['items']) == 4  # 4条活跃公告

    def test_get_notice_list_with_type_filter(self, client, session, test_user, test_notices, mock_token_required):
        """测试按类型筛选公告列表"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/list?type=SYSTEM')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 1  # 只有1条系统公告
        assert data['data']['items'][0]['notice_type'] == 'SYSTEM'

    def test_get_notice_list_pagination(self, client, session, test_user, test_notices, mock_token_required):
        """测试公告列表分页"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/list?page=1&size=2')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['page'] == 1
        assert data['data']['size'] == 2
        assert len(data['data']['items']) == 2


class TestNoticeDetailAPI:
    """测试公告详情接口"""

    def test_get_notice_detail_success(self, client, session, test_user, test_notices, mock_token_required):
        """测试获取公告详情成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        notice_id = test_notices[0].id
        response = client.get(f'/api/notice/detail/{notice_id}')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert data['data']['id'] == notice_id
        assert 'title' in data['data']
        assert 'content' in data['data']
        assert 'unread_count' in data['data']

    def test_get_notice_detail_auto_mark_read(self, client, session, test_user, test_notices, mock_token_required):
        """测试查看公告详情自动标记已读"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        notice_id = test_notices[1].id  # 第二条公告（之前未读）

        # 验证之前未读
        from components.models.notice_models import NoticeRead
        existing_read = NoticeRead.query.filter(
            NoticeRead.user_id == test_user.id,
            NoticeRead.notice_id == notice_id
        ).first()
        assert existing_read is None

        # 获取详情（应该自动标记已读）
        response = client.get(f'/api/notice/detail/{notice_id}')
        assert response.status_code == 200

        # 验证已读记录存在
        existing_read = NoticeRead.query.filter(
            NoticeRead.user_id == test_user.id,
            NoticeRead.notice_id == notice_id
        ).first()
        assert existing_read is not None

    def test_get_notice_detail_not_exist(self, client, session, test_user, mock_token_required):
        """测试获取不存在的公告详情"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/detail/99999')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data['success'] is False
        assert "公告不存在" in data['message']

    def test_get_notice_detail_no_permission(self, client, session, test_user, test_notices, mock_token_required):
        """测试获取无权限查看的公告详情"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        admin_notice = test_notices[2]  # 管理员公告
        response = client.get(f'/api/notice/detail/{admin_notice.id}')
        assert response.status_code == 403

        data = json.loads(response.data)
        assert data['success'] is False
        assert "无权限查看此类型公告" in data['message']


class TestMarkReadAPI:
    """测试标记已读接口"""

    def test_mark_notice_as_read_success(self, client, session, test_user, test_notices, mock_token_required):
        """测试标记公告为已读成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        notice_id = test_notices[1].id
        response = client.post(f'/api/notice/read/{notice_id}')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['notice_id'] == notice_id
        assert 'unread_count' in data['data']

    def test_mark_notice_as_read_already_read(self, client, session, test_user, test_notices, test_notice_reads, mock_token_required):
        """测试标记已读的公告"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        # 第一条公告已经读过
        notice_id = test_notices[0].id
        response = client.post(f'/api/notice/read/{notice_id}')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['notice_id'] == notice_id

    def test_mark_notice_as_read_not_exist(self, client, session, test_user, mock_token_required):
        """测试标记不存在的公告为已读"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.post('/api/notice/read/99999')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert "公告可能不存在或已失效" in data['message']


class TestMarkAllReadAPI:
    """测试全部标记已读接口"""

    def test_mark_all_notices_as_read_success(self, client, session, test_user, test_notices, test_notice_reads, mock_token_required):
        """测试标记所有公告为已读成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.post('/api/notice/read/all')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['marked_count'] > 0
        assert data['data']['unread_count'] == 0

    def test_mark_all_notices_as_read_no_unread(self, client, session, test_user, test_notices, mock_token_required):
        """测试没有未读公告时的全部标记已读"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        # 先标记所有为已读
        client.post('/api/notice/read/all')

        # 再次标记应该返回0
        response = client.post('/api/notice/read/all')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['marked_count'] == 0
        assert data['data']['unread_count'] == 0


class TestUnreadCountAPI:
    """测试未读数量接口"""

    def test_get_unread_count_success(self, client, session, test_user, test_notices, test_notice_reads, mock_token_required):
        """测试获取未读公告数量成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/unread/count')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'unread_count' in data['data']
        assert data['data']['unread_count'] == 3  # 4条活跃公告 - 1条已读

    def test_get_unread_count_no_unread(self, client, session, test_user, test_notices, mock_token_required):
        """测试没有未读公告时的数量"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        # 先标记所有为已读
        client.post('/api/notice/read/all')

        response = client.get('/api/notice/unread/count')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['unread_count'] == 0


class TestNoticeTypesAPI:
    """测试公告类型接口"""

    def test_get_notice_types_user(self, client, session, test_user, mock_token_required):
        """测试用户获取公告类型"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/types')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'types' in data['data']
        assert data['data']['is_admin'] is False

        types = data['data']['types']
        type_codes = [t['value'] for t in types]
        assert 'SYSTEM' in type_codes
        assert 'GENERAL' in type_codes
        assert 'ADMIN' not in type_codes  # 普通用户不能看到管理员公告类型

    def test_get_notice_types_admin(self, client, session, test_admin, mock_token_required):
        """测试管理员获取公告类型"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/types')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'types' in data['data']
        assert data['data']['is_admin'] is True

        types = data['data']['types']
        type_codes = [t['value'] for t in types]
        assert 'SYSTEM' in type_codes
        assert 'GENERAL' in type_codes
        assert 'ADMIN' in type_codes  # 管理员可以看到所有类型


class TestNoticeSearchAPI:
    """测试公告搜索接口"""

    def test_search_notices_success(self, client, session, test_user, test_notices, mock_token_required):
        """测试搜索公告成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/search?keyword=系统')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'items' in data['data']
        assert 'keyword' in data['data']
        assert data['data']['keyword'] == '系统'

    def test_search_notices_no_keyword(self, client, session, test_user, mock_token_required):
        """测试搜索关键词为空"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/search?keyword=')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert "搜索关键词不能为空" in data['message']

    def test_search_notices_with_type(self, client, session, test_user, test_notices, mock_token_required):
        """测试按类型搜索公告"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/search?keyword=公告&type=SYSTEM')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        for item in data['data']['items']:
            assert item['notice_type'] == 'SYSTEM'

    def test_search_notices_no_results(self, client, session, test_user, mock_token_required):
        """测试搜索无结果"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/search?keyword=不存在的内容')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 0


class TestUserAPIsEdgeCases:
    """测试用户端接口边界情况"""

    def test_unauthorized_access(self, client, session):
        """测试未授权访问"""
        # 不登录的情况下访问接口
        response = client.get('/api/notice/list')
        # 根据装饰器实现，可能返回401或其他状态码
        assert response.status_code in [401, 403, 302]

    def test_invalid_page_parameters(self, client, session, test_user, mock_token_required):
        """测试无效的分页参数"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        # 测试负数页码
        response = client.get('/api/notice/list?page=-1')
        # 应该有错误处理或默认值处理
        assert response.status_code in [200, 400]

        # 测试过大的页大小
        response = client.get('/api/notice/list?size=1000')
        # 应该有错误处理或默认值处理
        assert response.status_code in [200, 400]

    def test_invalid_notice_id(self, client, session, test_user, mock_token_required):
        """测试无效的公告ID"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        # 测试非数字ID
        response = client.get('/api/notice/detail/abc')
        assert response.status_code == 404

        # 测试负数ID
        response = client.get('/api/notice/detail/-1')
        assert response.status_code == 404

    def test_empty_database(self, client, session, test_user, mock_token_required):
        """测试空数据库情况"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        # 删除所有公告
        from components.models.notice_models import Notice
        Notice.query.delete()
        session.commit()

        response = client.get('/api/notice/list')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 0
        assert data['data']['unread_count'] == 0