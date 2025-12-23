# API_user 用户个人信息模块测试用例

import pytest
import json
from io import BytesIO

class TestUserProfile:
    """用户个人信息模块测试"""

    def test_get_user_profile_success(self, client, auth_headers):
        """测试获取用户个人信息成功"""
        response = client.get('/api/user/profile', headers=auth_headers)

        data = assert_success_response(response)
        assert 'account' in data
        assert 'username' in data
        assert 'email' in data
        assert data['account'] == 'testuser'

    def test_get_user_profile_no_auth(self, client):
        """测试未认证获取用户个人信息"""
        response = client.get('/api/user/profile')
        assert_permission_denied(response)

    def test_update_user_profile_success(self, client, auth_headers):
        """测试更新用户个人信息成功"""
        update_data = {
            'username': '更新后的用户名',
            'email': 'updated@example.com',
            'phone': '13900139999'
        }

        response = client.put('/api/user/profile',
                            json=update_data,
                            headers=auth_headers)

        data = assert_success_response(response)
        assert data['username'] == '更新后的用户名'
        assert data['email'] == 'updated@example.com'

    def test_update_profile_invalid_email(self, client, auth_headers):
        """测试更新用户信息使用无效邮箱"""
        update_data = {
            'email': 'invalid-email-format'
        }

        response = client.put('/api/user/profile',
                            json=update_data,
                            headers=auth_headers)

        assert_error_response(response, 400, '邮箱格式不正确')

    def test_update_profile_no_auth(self, client):
        """测试未认证更新用户个人信息"""
        update_data = {'username': '未认证更新'}

        response = client.put('/api/user/profile', json=update_data)
        assert_permission_denied(response)

    def test_get_user_activity_history(self, client, auth_headers):
        """测试获取用户活动历史"""
        response = client.get('/api/user/profile/activity',
                            headers=auth_headers)

        data = assert_success_response(response)
        assert 'activities' in data
        assert isinstance(data['activities'], list)

    def test_get_user_activity_history_with_pagination(self, client, auth_headers):
        """测试分页获取用户活动历史"""
        params = {'page': 1, 'size': 5}
        response = client.get('/api/user/profile/activity',
                           query_string=params,
                           headers=auth_headers)

        data = assert_success_response(response)
        assert 'activities' in data
        assert len(data['activities']) <= 5

    def test_get_user_preferences_success(self, client, auth_headers):
        """测试获取用户偏好设置成功"""
        response = client.get('/api/user/profile/preferences',
                            headers=auth_headers)

        data = assert_success_response(response)
        # 偏好设置可能包含各种配置项
        assert isinstance(data, dict)

    def test_update_user_preferences_success(self, client, auth_headers):
        """测试更新用户偏好设置成功"""
        preferences_data = {
            'theme': 'dark',
            'language': 'zh-CN',
            'notifications': True
        }

        response = client.put('/api/user/profile/preferences',
                            json=preferences_data,
                            headers=auth_headers)

        assert_success_response(response)

    def test_update_user_preferences_partial(self, client, auth_headers):
        """测试部分更新用户偏好设置"""
        preferences_data = {
            'theme': 'light'
        }

        response = client.put('/api/user/profile/preferences',
                            json=preferences_data,
                            headers=auth_headers)

        assert_success_response(response)

    def test_get_user_preferences_no_auth(self, client):
        """测试未认证获取用户偏好设置"""
        response = client.get('/api/user/profile/preferences')
        assert_permission_denied(response)

    def test_deactivate_user_account_success(self, client, auth_headers):
        """测试用户注销账号成功"""
        # 注意：这个测试可能会影响其他测试，实际使用时需要谨慎
        deactivation_data = {
            'password': 'password123',
            'reason': '测试注销'
        }

        response = client.post('/api/user/profile/deactivate',
                             json=deactivation_data,
                             headers=auth_headers)

        # 某些实现可能返回200或202
        assert response.status_code in [200, 202]

    def test_deactivate_user_account_wrong_password(self, client, auth_headers):
        """测试用户注销账号密码错误"""
        deactivation_data = {
            'password': 'wrongpassword',
            'reason': '测试注销'
        }

        response = client.post('/api/user/profile/deactivate',
                             json=deactivation_data,
                             headers=auth_headers)

        assert_error_response(response, 400, '密码不正确')

    def test_deactivate_user_account_no_reason(self, client, auth_headers):
        """测试用户注销账号没有原因"""
        deactivation_data = {
            'password': 'password123'
        }

        response = client.post('/api/user/profile/deactivate',
                             json=deactivation_data,
                             headers=auth_headers)

        assert_error_response(response, 400, '请提供注销原因')

    def test_upload_profile_image_success(self, client, auth_headers):
        """测试上传个人资料图片成功"""
        img_data = BytesIO(b'fake profile image data')
        img_data.name = 'profile_image.jpg'

        response = client.post('/api/user/profile/image',
                             data={'image': (img_data, 'profile_image.jpg')},
                             headers=auth_headers,
                             content_type='multipart/form-data')

        data = assert_success_response(response)
        assert 'image_url' in data

    def test_upload_profile_image_no_file(self, client, auth_headers):
        """测试上传个人资料图片没有文件"""
        response = client.post('/api/user/profile/image',
                             data={},
                             headers=auth_headers,
                             content_type='multipart/form-data')

        assert_error_response(response, 400, '缺少图片文件')

    def test_delete_profile_image_success(self, client, auth_headers):
        """测试删除个人资料图片成功"""
        # 先上传图片
        img_data = BytesIO(b'fake profile image data')
        img_data.name = 'profile_image.jpg'

        upload_response = client.post('/api/user/profile/image',
                                   data={'image': (img_data, 'profile_image.jpg')},
                                   headers=auth_headers,
                                   content_type='multipart/form-data')

        if upload_response.status_code == 200:
            # 再删除图片
            response = client.delete('/api/user/profile/image',
                                   headers=auth_headers)

            assert_success_response(response)

    def test_get_user_statistics_success(self, client, auth_headers):
        """测试获取用户统计信息成功"""
        response = client.get('/api/user/profile/statistics',
                            headers=auth_headers)

        data = assert_success_response(response)
        # 统计信息可能包含各种用户数据
        assert isinstance(data, dict)

    def test_export_user_data_success(self, client, auth_headers):
        """测试导出用户数据成功"""
        response = client.get('/api/user/profile/export',
                            headers=auth_headers)

        # 检查响应是否是文件下载格式
        assert response.status_code == 200
        assert 'attachment' in response.headers.get('Content-Disposition', '')

    def test_export_user_data_no_auth(self, client):
        """测试未认证导出用户数据"""
        response = client.get('/api/user/profile/export')
        assert_permission_denied(response)