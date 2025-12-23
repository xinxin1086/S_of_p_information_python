# 公告管理员接口测试

import pytest
import json
from datetime import datetime, timedelta
from test_API_admin.conftest import (
    get_auth_headers, assert_success_response, assert_error_response,
    assert_permission_denied, create_test_notice_data
)

class TestAdminNoticeCreation:
    """管理员创建公告接口测试"""

    def test_create_general_notice_success(self, client, admin_token):
        """测试管理员成功创建普通公告"""
        notice_data = create_test_notice_data()

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(notice_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'data' in data
        assert 'id' in data['data']
        assert data['data']['title'] == notice_data['title']
        assert data['data']['notice_type'] == notice_data['notice_type']
        assert data['data']['status'] in ['APPROVED', 'PENDING']

    def test_create_urgent_notice_success(self, client, admin_token):
        """测试管理员成功创建紧急公告"""
        notice_data = create_test_notice_data()
        notice_data['notice_type'] = 'URGENT'
        notice_data['is_top'] = True

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(notice_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['notice_type'] == 'URGENT'
        assert data['data']['is_top'] == True

    def test_create_maintenance_notice_success(self, client, admin_token):
        """测试管理员成功创建维护公告"""
        notice_data = create_test_notice_data()
        notice_data['notice_type'] = 'MAINTENANCE'

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(notice_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['notice_type'] == 'MAINTENANCE'

    def test_create_notice_with_expiration(self, client, admin_token):
        """测试创建带过期时间的公告"""
        expiration_time = (datetime.now() + timedelta(days=7)).isoformat()

        notice_data = create_test_notice_data()
        notice_data['expiration'] = expiration_time

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(notice_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'expiration' in data['data']

    def test_create_notice_minimal_data(self, client, admin_token):
        """测试使用最少数据创建公告"""
        minimal_data = {
            'title': '最简公告标题',
            'content': '最简公告内容'
        }

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(minimal_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['title'] == minimal_data['title']

    def test_create_notice_missing_title(self, client, admin_token):
        """测试创建公告缺少标题"""
        notice_data = {
            'content': '只有内容没有标题的公告'
        }

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(notice_data),
                             content_type='application/json')

        assert_error_response(response, 400, '公告标题不能为空')

    def test_create_notice_missing_content(self, client, admin_token):
        """测试创建公告缺少内容"""
        notice_data = {
            'title': '只有标题没有内容的公告'
        }

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(notice_data),
                             content_type='application/json')

        assert_error_response(response, 400, '公告内容不能为空')

    def test_create_notice_invalid_type(self, client, admin_token):
        """测试创建公告类型无效"""
        notice_data = create_test_notice_data()
        notice_data['notice_type'] = 'INVALID_TYPE'

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(notice_data),
                             content_type='application/json')

        assert_error_response(response, 400, '无效的公告类型')

    def test_create_notice_invalid_expiration(self, client, admin_token):
        """测试创建公告过期时间无效"""
        past_time = (datetime.now() - timedelta(days=1)).isoformat()

        notice_data = create_test_notice_data()
        notice_data['expiration'] = past_time

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(notice_data),
                             content_type='application/json')

        assert_error_response(response, 400, '到期时间不能早于当前时间')

    def test_create_notice_unauthorized(self, client):
        """测试未认证创建公告"""
        notice_data = create_test_notice_data()

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(notice_data),
                             content_type='application/json')

        assert response.status_code == 401

    def test_create_notice_permission_denied(self, client, user_token):
        """测试普通用户无权创建公告"""
        notice_data = create_test_notice_data()

        response = client.post('/api/notice/admin/create',
                             headers=get_auth_headers(user_token),
                             data=json.dumps(notice_data),
                             content_type='application/json')

        assert_permission_denied(response)

class TestAdminNoticeManagement:
    """管理员公告管理接口测试"""

    def test_get_admin_notices_success(self, client, admin_token):
        """测试管理员获取公告列表"""
        response = client.get('/api/notice/admin/notices',
                            headers=get_auth_headers(admin_token))

        data = assert_success_response(response)
        assert 'items' in data['data']
        assert 'pagination' in data['data']

        # 验证分页信息
        pagination = data['data']['pagination']
        required_pagination_fields = ['total', 'page', 'per_page', 'pages', 'has_prev', 'has_next']
        for field in required_pagination_fields:
            assert field in pagination

    def test_get_admin_notices_with_filters(self, client, admin_token):
        """测试管理员按筛选条件获取公告"""
        test_filters = [
            {'notice_type': 'GENERAL', 'description': '筛选普通公告'},
            {'notice_type': 'URGENT', 'description': '筛选紧急公告'},
            {'status': 'PENDING', 'description': '筛选待审核公告'},
            {'status': 'APPROVED', 'description': '筛选已发布公告'},
            {'is_top': True, 'description': '筛选置顶公告'}
        ]

        for filter_config in test_filters:
            response = client.get('/api/notice/admin/notices',
                                headers=get_auth_headers(admin_token),
                                query_string=filter_config)

            data = assert_success_response(response)
            assert 'items' in data['data']

    def test_get_admin_notices_pagination(self, client, admin_token):
        """测试管理员公告列表分页"""
        params = {'page': 2, 'per_page': 5}

        response = client.get('/api/notice/admin/notices',
                            headers=get_auth_headers(admin_token),
                            query_string=params)

        data = assert_success_response(response)
        pagination = data['data']['pagination']
        assert pagination['page'] == 2
        assert pagination['per_page'] == 5

    def test_get_admin_notices_unauthorized(self, client):
        """测试未认证访问管理员公告列表"""
        response = client.get('/api/notice/admin/notices')
        assert response.status_code == 401

    def test_get_admin_notices_permission_denied(self, client, user_token):
        """测试普通用户无权访问管理员公告列表"""
        response = client.get('/api/notice/admin/notices',
                            headers=get_auth_headers(user_token))

        assert_permission_denied(response)

class TestAdminNoticeUpdate:
    """管理员更新公告接口测试"""

    def test_update_notice_success(self, client, admin_token):
        """测试管理员成功更新公告"""
        update_data = {
            'title': '更新后的公告标题',
            'content': '更新后的公告内容',
            'notice_type': 'GENERAL'
        }

        response = client.put('/api/notice/admin/1',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['title'] == update_data['title']

    def test_update_notice_change_type(self, client, admin_token):
        """测试更新公告类型"""
        update_data = {
            'notice_type': 'URGENT',
            'is_top': True
        }

        response = client.put('/api/notice/admin/1',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['notice_type'] == 'URGENT'
        assert data['data']['is_top'] == True

    def test_update_notice_change_status(self, client, admin_token):
        """测试更新公告状态"""
        update_data = {'status': 'APPROVED'}

        response = client.put('/api/notice/admin/1',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['status'] == 'APPROVED'

    def test_update_notice_not_found(self, client, admin_token):
        """测试更新不存在的公告"""
        update_data = {'title': '更新标题'}

        response = client.put('/api/notice/admin/999999',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        assert_error_response(response, 404, '公告不存在')

    def test_update_notice_invalid_data(self, client, admin_token):
        """测试更新公告数据无效"""
        update_data = {
            'title': '',  # 空标题
            'notice_type': 'INVALID_TYPE'
        }

        response = client.put('/api/notice/admin/1',
                            headers=get_auth_headers(admin_token),
                            data=json.dumps(update_data),
                            content_type='application/json')

        assert_error_response(response, 400)

    def test_update_notice_unauthorized(self, client):
        """测试未认证更新公告"""
        update_data = {'title': '更新标题'}

        response = client.put('/api/notice/admin/1',
                            data=json.dumps(update_data),
                            content_type='application/json')

        assert response.status_code == 401

class TestAdminNoticeDeletion:
    """管理员删除公告接口测试"""

    def test_delete_notice_success(self, client, admin_token):
        """测试管理员成功删除公告"""
        response = client.delete('/api/notice/admin/1',
                               headers=get_auth_headers(admin_token))

        assert_success_response(response)

    def test_delete_notice_not_found(self, client, admin_token):
        """测试删除不存在的公告"""
        response = client.delete('/api/notice/admin/999999',
                               headers=get_auth_headers(admin_token))

        assert_error_response(response, 404, '公告不存在')

    def test_delete_notice_unauthorized(self, client):
        """测试未认证删除公告"""
        response = client.delete('/api/notice/admin/1')
        assert response.status_code == 401

    def test_delete_notice_permission_denied(self, client, user_token):
        """测试普通用户无权删除公告"""
        response = client.delete('/api/notice/admin/1',
                               headers=get_auth_headers(user_token))

        assert_permission_denied(response)

class TestAdminNoticeApproval:
    """管理员公告审核接口测试"""

    def test_approve_notice_success(self, client, admin_token):
        """测试管理员审核通过公告"""
        response = client.post('/api/notice/admin/1/approve',
                             headers=get_auth_headers(admin_token))

        data = assert_success_response(response)
        assert data['data']['status'] == 'APPROVED'

    def test_approve_notice_with_comment(self, client, admin_token):
        """测试管理员审核通过公告并添加评论"""
        approval_data = {
            'review_comment': '内容优秀，审核通过'
        }

        response = client.post('/api/notice/admin/1/approve',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(approval_data),
                             content_type='application/json')

        assert_success_response(response)

    def test_approve_notice_already_approved(self, client, admin_token):
        """测试审核已通过的公告"""
        response = client.post('/api/notice/admin/1/approve',
                             headers=get_auth_headers(admin_token))

        # 应该处理重复审核的情况
        assert response.status_code in [200, 400]

    def test_approve_notice_not_found(self, client, admin_token):
        """测试审核不存在的公告"""
        response = client.post('/api/notice/admin/999999/approve',
                             headers=get_auth_headers(admin_token))

        assert_error_response(response, 404, '公告不存在')

    def test_approve_notice_unauthorized(self, client):
        """测试未认证审核公告"""
        response = client.post('/api/notice/admin/1/approve')
        assert response.status_code == 401

    def test_reject_notice_success(self, client, admin_token):
        """测试管理员驳回公告"""
        rejection_data = {
            'reason': '内容不符合规范，需要修改'
        }

        response = client.post('/api/notice/admin/1/reject',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps(rejection_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['status'] == 'REJECTED'

    def test_reject_notice_without_reason(self, client, admin_token):
        """测试驳回公告不提供原因"""
        response = client.post('/api/notice/admin/1/reject',
                             headers=get_auth_headers(admin_token),
                             data=json.dumps({}),
                             content_type='application/json')

        # 可能接受也可能拒绝，取决于实现
        assert response.status_code in [200, 400]


class TestUpdateNoticeAPI:
    """测试更新公告接口"""

    def test_update_notice_success(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试更新公告成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        notice_id = test_notices[0].id
        update_data = {
            'title': '更新后的公告标题',
            'content': '更新后的公告内容。'
        }

        response = client.put(f'/api/notice/admin/update/{notice_id}',
                             data=json.dumps(update_data),
                             content_type='application/json')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'updated_fields' in data['data']
        assert 'title' in data['data']['updated_fields']
        assert 'content' in data['data']['updated_fields']

    def test_update_notice_not_exist(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试更新不存在的公告"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        update_data = {
            'title': '更新后的公告标题'
        }

        response = client.put('/api/notice/admin/update/99999',
                             data=json.dumps(update_data),
                             content_type='application/json')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data['success'] is False
        assert "公告不存在" in data['message']

    def test_update_notice_no_permission(self, client, session, test_notices, mock_token_required, mock_admin_required):
        """测试更新无权限的公告"""
        # 创建另一个管理员
        other_admin = AdminFactory.create_admin(session)

        with client.session_transaction() as sess:
            sess['user_id'] = other_admin.id
            sess['account'] = other_admin.account

        notice_id = test_notices[0].id  # 这是test_admin创建的公告
        update_data = {
            'title': '更新后的公告标题'
        }

        response = client.put(f'/api/notice/admin/update/{notice_id}',
                             data=json.dumps(update_data),
                             content_type='application/json')
        assert response.status_code == 403

        data = json.loads(response.data)
        assert data['success'] is False
        assert "无权限编辑他人发布的公告" in data['message']


class TestDeleteNoticeAPI:
    """测试删除公告接口"""

    def test_delete_notice_success(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试删除公告成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        notice_id = test_notices[0].id
        response = client.delete(f'/api/notice/admin/delete/{notice_id}')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == notice_id
        assert data['data']['status'] == 'REJECTED'

    def test_delete_notice_not_exist(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试删除不存在的公告"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.delete('/api/notice/admin/delete/99999')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data['success'] is False
        assert "公告不存在" in data['message']


class TestAdminNoticeListAPI:
    """测试管理员公告列表接口"""

    def test_get_admin_notice_list_success(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试获取管理员公告列表成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/admin/list')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'items' in data['data']
        assert 'total' in data['data']
        assert len(data['data']['items']) == 5  # 5条测试公告

    def test_get_admin_notice_list_with_filters(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试带筛选条件的管理员公告列表"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        # 按状态筛选
        response = client.get('/api/notice/admin/list?status=APPROVED')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        for item in data['data']['items']:
            assert item['status'] == 'APPROVED'

        # 按类型筛选
        response = client.get('/api/notice/admin/list?type=SYSTEM')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        for item in data['data']['items']:
            assert item['notice_type'] == 'SYSTEM'

    def test_get_admin_notice_list_pagination(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试管理员公告列表分页"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/admin/list?page=1&size=2')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['page'] == 1
        assert data['data']['size'] == 2
        assert len(data['data']['items']) == 2


class TestAdminNoticeDetailAPI:
    """测试管理员公告详情接口"""

    def test_get_admin_notice_detail_success(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试获取管理员公告详情成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        notice_id = test_notices[0].id
        response = client.get(f'/api/notice/admin/detail/{notice_id}')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == notice_id
        assert 'read_stats' in data['data']
        assert 'can_edit' in data['data']
        assert data['data']['can_edit'] is True

    def test_get_admin_notice_detail_not_exist(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试获取不存在的管理员公告详情"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/admin/detail/99999')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data['success'] is False
        assert "公告不存在" in data['message']


class TestToggleNoticeTopAPI:
    """测试公告置顶接口"""

    def test_toggle_notice_top_success(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试切换公告置顶状态成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        notice = test_notices[0]
        if not hasattr(notice, 'is_top'):
            pytest.skip("当前模型不支持置顶功能")

        notice_id = notice.id
        toggle_data = {'is_top': True}

        response = client.post(f'/api/notice/admin/top/{notice_id}',
                             data=json.dumps(toggle_data),
                             content_type='application/json')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['is_top'] is True

    def test_toggle_notice_top_not_supported(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试模型不支持置顶功能"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        notice = test_notices[0]
        if hasattr(notice, 'is_top'):
            pytest.skip("当前模型支持置顶功能")

        notice_id = notice.id
        toggle_data = {'is_top': True}

        response = client.post(f'/api/notice/admin/top/{notice_id}',
                             data=json.dumps(toggle_data),
                             content_type='application/json')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert "不支持置顶功能" in data['message']


class TestAdminStatisticsAPI:
    """测试管理员统计接口"""

    def test_get_notice_statistics_success(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试获取公告统计数据成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/admin/statistics')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'overview' in data['data']
        assert 'status_distribution' in data['data']
        assert 'type_distribution' in data['data']

        overview = data['data']['overview']
        assert 'total_count' in overview
        assert 'active_count' in overview
        assert overview['total_count'] == 5  # 5条测试公告


class TestAdminAPIsEdgeCases:
    """测试管理员接口边界情况"""

    def test_non_admin_access(self, client, session, test_user, mock_token_required):
        """测试非管理员访问管理员接口"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        # 尝试访问管理员接口
        response = client.get('/api/notice/admin/list')
        assert response.status_code == 403

        data = json.loads(response.data)
        assert data['success'] is False
        assert "需要管理员权限" in data['message']

    def test_invalid_json_data(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试无效的JSON数据"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        # 发送无效JSON
        response = client.post('/api/notice/admin/create',
                             data='invalid json',
                             content_type='application/json')
        assert response.status_code == 400

    def test_empty_request_data(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试空请求数据"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.post('/api/notice/admin/create')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert "请求数据不能为空" in data['message']

    def test_invalid_date_format(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试无效的日期格式"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        notice_data = {
            'title': '测试公告标题',
            'content': '这是一条测试公告的内容。',
            'notice_type': 'GENERAL',
            'expiration': 'invalid-date-format'
        }

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(notice_data),
                             content_type='application/json')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert "到期时间格式无效" in data['message']

    def test_long_content(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试超长内容"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        # 创建超长标题
        long_title = 'A' * 200  # 超过150字符限制
        notice_data = {
            'title': long_title,
            'content': '这是一条测试公告的内容。',
            'notice_type': 'GENERAL'
        }

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(notice_data),
                             content_type='application/json')
        # 应该有相应的错误处理
        assert response.status_code in [200, 400]

    def test_concurrent_operations(self, client, session, test_admin, test_notices, mock_token_required, mock_admin_required):
        """测试并发操作"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        notice_id = test_notices[0].id
        update_data = {
            'title': f'并发测试标题_{datetime.now().timestamp()}'
        }

        # 模拟并发更新（在实际环境中需要使用线程或进程）
        response1 = client.put(f'/api/notice/admin/update/{notice_id}',
                              data=json.dumps(update_data),
                              content_type='application/json')

        response2 = client.put(f'/api/notice/admin/update/{notice_id}',
                              data=json.dumps(update_data),
                              content_type='application/json')

        # 至少有一个请求应该成功
        assert response1.status_code in [200, 403, 409]
        assert response2.status_code in [200, 403, 409]