# API_user 管理员用户管理测试用例

import pytest
import json

class TestAdminManagement:
    """管理员用户管理功能测试"""

    def test_get_user_list_success(self, client, admin_auth_headers):
        """测试管理员获取用户列表成功"""
        response = client.get('/api/user/admin/users', headers=admin_auth_headers)

        data = assert_success_response(response)
        assert 'users' in data
        assert 'total' in data
        assert isinstance(data['users'], list)

    def test_get_user_list_with_pagination(self, client, admin_auth_headers):
        """测试分页获取用户列表"""
        params = {'page': 1, 'size': 5}
        response = client.get('/api/user/admin/users',
                           query_string=params,
                           headers=admin_auth_headers)

        data = assert_success_response(response)
        assert len(data['users']) <= 5

    def test_get_user_list_with_search(self, client, admin_auth_headers):
        """测试搜索获取用户列表"""
        params = {'search': 'test'}
        response = client.get('/api/user/admin/users',
                           query_string=params,
                           headers=admin_auth_headers)

        data = assert_success_response(response)
        assert 'users' in data

    def test_get_user_detail_success(self, client, admin_auth_headers):
        """测试管理员获取用户详情成功"""
        # 先获取用户列表找到用户ID
        list_response = client.get('/api/user/admin/users', headers=admin_auth_headers)
        if list_response.status_code == 200:
            users = list_response.get_json()['data']['users']
            if users:
                user_id = users[0]['id']
                response = client.get(f'/api/user/admin/users/{user_id}',
                                    headers=admin_auth_headers)

                data = assert_success_response(response)
                assert 'account' in data
                assert 'username' in data

    def test_get_user_detail_not_found(self, client, admin_auth_headers):
        """测试获取不存在的用户详情"""
        response = client.get('/api/user/admin/users/99999',
                            headers=admin_auth_headers)

        assert_error_response(response, 404, '用户不存在')

    def test_create_user_success(self, client, admin_auth_headers):
        """测试管理员创建用户成功"""
        user_data = {
            'account': 'newadminuser',
            'password': 'newpass123',
            'username': '新建用户',
            'email': 'newadmin@example.com',
            'phone': '13700137000'
        }

        response = client.post('/api/user/admin/users',
                             json=user_data,
                             headers=admin_auth_headers)

        data = assert_success_response(response, 201)
        assert data['account'] == 'newadminuser'
        assert data['username'] == '新建用户'

    def test_create_user_duplicate_account(self, client, admin_auth_headers):
        """测试管理员创建重复账号用户"""
        user_data = {
            'account': 'testuser',  # 已存在的账号
            'password': 'password123',
            'username': '重复用户',
            'email': 'duplicate@example.com'
        }

        response = client.post('/api/user/admin/users',
                             json=user_data,
                             headers=admin_auth_headers)

        assert_error_response(response, 400, '账号已存在')

    def test_get_user_list_no_auth(self, client):
        """测试未认证获取用户列表"""
        response = client.get('/api/user/admin/users')
        assert_permission_denied(response)

    def test_get_user_list_regular_user(self, client, auth_headers):
        """测试普通用户访问管理员接口"""
        response = client.get('/api/user/admin/users', headers=auth_headers)
        assert_permission_denied(response)