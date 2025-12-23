# API_user 认证模块测试用例

import pytest
import json
import tempfile
import os
from io import BytesIO

class TestAuth:
    """用户认证功能测试"""

    def test_user_login_success(self, client):
        """测试用户登录成功"""
        response = client.post('/api/user/login', json={
            'account': 'testuser',
            'password': 'password123'
        })

        data = assert_success_response(response)
        assert 'token' in data
        assert 'user' in data
        assert data['user']['account'] == 'testuser'
        assert data['user']['username'] == '测试用户'

    def test_admin_login_success(self, client):
        """测试管理员登录成功"""
        response = client.post('/api/user/login', json={
            'account': 'testadmin',
            'password': 'admin123'
        })

        data = assert_success_response(response)
        assert 'token' in data
        assert 'user' in data
        assert data['user']['account'] == 'testadmin'
        assert data['user']['role'] == 'ADMIN'

    def test_login_wrong_password(self, client):
        """测试密码错误"""
        response = client.post('/api/user/login', json={
            'account': 'testuser',
            'password': 'wrongpassword'
        })

        assert_error_response(response, 401)

    def test_login_user_not_exists(self, client):
        """测试用户不存在"""
        response = client.post('/api/user/login', json={
            'account': 'nonexistent',
            'password': 'password123'
        })

        assert_error_response(response, 401)

    def test_login_missing_fields(self, client):
        """测试缺少必要字段"""
        # 缺少账号
        response = client.post('/api/user/login', json={
            'password': 'password123'
        })
        assert_error_response(response, 400)

        # 缺少密码
        response = client.post('/api/user/login', json={
            'account': 'testuser'
        })
        assert_error_response(response, 400)

    def test_user_register_success(self, client):
        """测试用户注册成功"""
        response = client.post('/api/user/register', json={
            'account': 'newuser',
            'password': 'newpass123',
            'username': '新用户',
            'email': 'newuser@example.com',
            'phone': '13900139000'
        })

        data = assert_success_response(response, 201)
        assert data['account'] == 'newuser'
        assert data['username'] == '新用户'

    def test_register_duplicate_account(self, client):
        """测试注册重复账号"""
        response = client.post('/api/user/register', json={
            'account': 'testuser',  # 已存在的账号
            'password': 'password123',
            'username': '重复用户',
            'email': 'duplicate@example.com'
        })

        assert_error_response(response, 400)

    def test_register_invalid_email(self, client):
        """测试注册无效邮箱"""
        response = client.post('/api/user/register', json={
            'account': 'invaliduser',
            'password': 'password123',
            'username': '无效邮箱用户',
            'email': 'invalid-email'
        })

        assert_error_response(response, 400)

    def test_upload_avatar_success(self, client, auth_headers):
        """测试头像上传成功"""
        # 创建模拟图片文件
        img_data = BytesIO(b'fake image data')
        img_data.name = 'test_avatar.jpg'

        response = client.post('/api/user/avatar',
                             data={'avatar': (img_data, 'test_avatar.jpg')},
                             headers=auth_headers,
                             content_type='multipart/form-data')

        data = assert_success_response(response)
        assert 'avatar_url' in data

    def test_upload_avatar_no_file(self, client, auth_headers):
        """测试上传头像没有文件"""
        response = client.post('/api/user/avatar',
                             data={},
                             headers=auth_headers,
                             content_type='multipart/form-data')

        assert_error_response(response, 400, '缺少头像文件')

    def test_upload_avatar_no_auth(self, client):
        """测试未认证上传头像"""
        img_data = BytesIO(b'fake image data')
        img_data.name = 'test_avatar.jpg'

        response = client.post('/api/user/avatar',
                             data={'avatar': (img_data, 'test_avatar.jpg')},
                             content_type='multipart/form-data')

        assert_permission_denied(response)

    def test_delete_avatar_success(self, client, auth_headers):
        """测试删除头像成功"""
        # 先上传头像
        img_data = BytesIO(b'fake image data')
        img_data.name = 'test_avatar.jpg'

        upload_response = client.post('/api/user/avatar',
                                   data={'avatar': (img_data, 'test_avatar.jpg')},
                                   headers=auth_headers,
                                   content_type='multipart/form-data')

        if upload_response.status_code == 200:
            # 再删除头像
            response = client.delete('/api/user/avatar', headers=auth_headers)
            assert_success_response(response)

    def test_get_user_info_success(self, client, auth_headers):
        """测试获取用户信息成功"""
        response = client.get('/api/user/info', headers=auth_headers)

        data = assert_success_response(response)
        assert data['account'] == 'testuser'
        assert data['username'] == '测试用户'
        assert 'email' in data

    def test_get_user_info_no_auth(self, client):
        """测试未认证获取用户信息"""
        response = client.get('/api/user/info')
        assert_permission_denied(response)

    def test_update_user_info_success(self, client, auth_headers):
        """测试更新用户信息成功"""
        update_data = {
            'username': '更新后的用户名',
            'email': 'updated@example.com'
        }

        response = client.post('/api/user/update',
                             json=update_data,
                             headers=auth_headers)

        data = assert_success_response(response)
        assert data['username'] == '更新后的用户名'
        assert data['email'] == 'updated@example.com'

    def test_update_user_info_invalid_email(self, client, auth_headers):
        """测试更新用户信息使用无效邮箱"""
        update_data = {
            'email': 'invalid-email-format'
        }

        response = client.post('/api/user/update',
                             json=update_data,
                             headers=auth_headers)

        assert_error_response(response, 400, '邮箱格式不正确')

    def test_change_password_success(self, client, auth_headers):
        """测试修改密码成功"""
        password_data = {
            'old_password': 'password123',
            'new_password': 'newpassword456'
        }

        response = client.post('/api/user/change-password',
                             json=password_data,
                             headers=auth_headers)

        assert_success_response(response)

    def test_change_password_wrong_old_password(self, client, auth_headers):
        """测试修改密码时旧密码错误"""
        password_data = {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword456'
        }

        response = client.post('/api/user/change-password',
                             json=password_data,
                             headers=auth_headers)

        assert_error_response(response, 400, '旧密码不正确')

    def test_user_logout_success(self, client, auth_headers):
        """测试用户登出成功"""
        response = client.post('/api/user/logout', headers=auth_headers)
        assert_success_response(response)