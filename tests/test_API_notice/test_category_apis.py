# API_notice公告分类接口测试
# 测试公告分类管理的各种接口

import pytest
import json
from datetime import datetime


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
        type_codes = [t['code'] for t in types]
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
        type_codes = [t['code'] for t in types]
        assert 'SYSTEM' in type_codes
        assert 'GENERAL' in type_codes
        assert 'ADMIN' in type_codes  # 管理员可以看到所有类型

    def test_get_notice_type_detail_success(self, client, session, test_user, mock_token_required):
        """测试获取公告类型详情成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/types/SYSTEM')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['code'] == 'SYSTEM'
        assert data['data']['name'] == '系统公告'
        assert 'description' in data['data']
        assert 'statistics' in data['data']

    def test_get_notice_type_detail_not_exist(self, client, session, test_user, mock_token_required):
        """测试获取不存在的公告类型详情"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/types/INVALID_TYPE')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data['success'] is False
        assert "公告类型不存在" in data['message']

    def test_get_notice_type_detail_admin_only(self, client, session, test_user, mock_token_required):
        """测试普通用户查看管理员公告类型详情"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/types/ADMIN')
        assert response.status_code == 403

        data = json.loads(response.data)
        assert data['success'] is False
        assert "无权限查看此公告类型" in data['message']


class TestNoticeTemplatesAPI:
    """测试公告模板接口"""

    def test_get_notice_templates_success(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试获取公告模板列表成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/templates')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'templates' in data['data']
        assert len(data['data']['templates']) > 0

        templates = data['data']['templates']
        for template in templates:
            assert 'id' in template
            assert 'name' in template
            assert 'type' in template
            assert 'variables' in template

    def test_get_notice_template_detail_success(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试获取公告模板详情成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/templates/system_maintenance')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == 'system_maintenance'
        assert data['data']['name'] == '系统维护公告'
        assert 'template' in data['data']
        assert 'variables' in data['data']

    def test_get_notice_template_detail_not_exist(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试获取不存在的公告模板详情"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/templates/nonexistent_template')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data['success'] is False
        assert "模板不存在" in data['message']

    def test_apply_notice_template_success(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试应用公告模板成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        apply_data = {
            'template_id': 'system_maintenance',
            'variables': {
                'maintenance_time': '2024-01-15 02:00-06:00',
                'maintenance_scope': '用户管理系统',
                'impact_content': '用户登录、注册功能',
                'company_name': '某某科技有限公司',
                'date': '2024-01-14'
            }
        }

        response = client.post('/api/notice/templates/apply',
                             data=json.dumps(apply_data),
                             content_type='application/json')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['template_id'] == 'system_maintenance'
        assert data['data']['template_name'] == '系统维护公告'
        assert 'content' in data['data']
        assert data['data']['notice_type'] == 'SYSTEM'

    def test_apply_notice_template_missing_variables(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试应用公告模板缺少必填变量"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        apply_data = {
            'template_id': 'system_maintenance',
            'variables': {
                'maintenance_time': '2024-01-15 02:00-06:00',
                # 缺少其他必填变量
            }
        }

        response = client.post('/api/notice/templates/apply',
                             data=json.dumps(apply_data),
                             content_type='application/json')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert "缺少必填变量" in data['message']

    def test_apply_notice_template_not_exist(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试应用不存在的公告模板"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        apply_data = {
            'template_id': 'nonexistent_template',
            'variables': {
                'test': 'value'
            }
        }

        response = client.post('/api/notice/templates/apply',
                             data=json.dumps(apply_data),
                             content_type='application/json')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data['success'] is False
        assert "模板不存在" in data['message']

    def test_apply_notice_template_invalid_id(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试应用模板时缺少模板ID"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        apply_data = {
            'variables': {
                'test': 'value'
            }
        }

        response = client.post('/api/notice/templates/apply',
                             data=json.dumps(apply_data),
                             content_type='application/json')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert "模板ID不能为空" in data['message']


class TestPushRulesAPI:
    """测试推送规则接口"""

    def test_get_push_rules_success(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试获取推送规则成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/push-rules')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'push_rules' in data['data']
        assert 'user_types' in data['data']
        assert 'push_channels' in data['data']

        push_rules = data['data']['push_rules']
        assert 'SYSTEM' in push_rules
        assert 'ADMIN' in push_rules
        assert 'GENERAL' in push_rules

        # 验证推送规则结构
        for rule_type, rule in push_rules.items():
            assert 'target_users' in rule
            assert 'push_channels' in rule
            assert 'priority' in rule
            assert 'immediate' in rule


class TestNoticeConfigValidationAPI:
    """测试公告配置验证接口"""

    def test_validate_notice_config_success(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试验证公告配置成功"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        config_data = {
            'notice_type': 'GENERAL',
            'target_user_type': 'USER',
            'title': '测试公告标题',
            'content': '这是一条测试公告的内容。',
            'expiration': (datetime.now() + timedelta(days=7)).isoformat() + 'Z'
        }

        response = client.post('/api/notice/validate',
                             data=json.dumps(config_data),
                             content_type='application/json')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'is_valid' in data['data']
        assert 'errors' in data['data']
        assert 'warnings' in data['data']

    def test_validate_notice_config_invalid_type(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试验证公告配置类型无效"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        config_data = {
            'notice_type': 'INVALID_TYPE',
            'target_user_type': 'USER',
            'title': '测试公告标题',
            'content': '这是一条测试公告的内容。'
        }

        response = client.post('/api/notice/validate',
                             data=json.dumps(config_data),
                             content_type='application/json')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['is_valid'] is False
        assert len(data['data']['errors']) > 0
        assert any("无效的公告类型" in error for error in data['data']['errors'])

    def test_validate_notice_config_mismatch_scope(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试验证公告配置推送范围不匹配"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        config_data = {
            'notice_type': 'ADMIN',
            'target_user_type': 'USER',  # 管理员公告推送给普通用户 - 不匹配
            'title': '测试公告标题',
            'content': '这是一条测试公告的内容。'
        }

        response = client.post('/api/notice/validate',
                             data=json.dumps(config_data),
                             content_type='application/json')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['is_valid'] is False
        assert len(data['data']['errors']) > 0
        assert any("推送范围不匹配" in error for error in data['data']['errors'])

    def test_validate_notice_config_missing_fields(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试验证公告配置缺少必填字段"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        config_data = {
            'notice_type': 'GENERAL',
            'target_user_type': 'USER',
            # 缺少title和content
        }

        response = client.post('/api/notice/validate',
                             data=json.dumps(config_data),
                             content_type='application/json')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['is_valid'] is False
        assert len(data['data']['errors']) >= 2  # title和content都缺失

    def test_validate_notice_config_long_title(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试验证公告配置标题过长"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        config_data = {
            'notice_type': 'GENERAL',
            'target_user_type': 'USER',
            'title': 'A' * 200,  # 超过150字符限制
            'content': '这是一条测试公告的内容。'
        }

        response = client.post('/api/notice/validate',
                             data=json.dumps(config_data),
                             content_type='application/json')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['is_valid'] is False
        assert any("标题不能超过150个字符" in error for error in data['data']['errors'])

    def test_validate_notice_config_expired_expiration(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试验证公告配置过期时间无效"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        config_data = {
            'notice_type': 'GENERAL',
            'target_user_type': 'USER',
            'title': '测试公告标题',
            'content': '这是一条测试公告的内容。',
            'expiration': (datetime.now() - timedelta(days=1)).isoformat() + 'Z'  # 过期时间
        }

        response = client.post('/api/notice/validate',
                             data=json.dumps(config_data),
                             content_type='application/json')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['is_valid'] is False
        assert any("到期时间不能早于当前时间" in error for error in data['data']['errors'])

    def test_validate_notice_config_no_data(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试验证公告配置没有数据"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.post('/api/notice/validate',
                             data='',
                             content_type='application/json')
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data['success'] is False
        assert "请求数据不能为空" in data['message']


class TestCategoryAPIsEdgeCases:
    """测试分类接口边界情况"""

    def test_non_admin_access_templates(self, client, session, test_user, mock_token_required):
        """测试非管理员访问模板接口"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/templates')
        assert response.status_code == 403

        data = json.loads(response.data)
        assert data['success'] is False
        assert "需要管理员权限" in data['message']

    def test_non_admin_access_push_rules(self, client, session, test_user, mock_token_required):
        """测试非管理员访问推送规则接口"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/push-rules')
        assert response.status_code == 403

        data = json.loads(response.data)
        assert data['success'] is False
        assert "需要管理员权限" in data['message']

    def test_invalid_json_in_apply_template(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试应用模板时JSON格式错误"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.post('/api/notice/templates/apply',
                             data='invalid json',
                             content_type='application/json')
        assert response.status_code == 400

    def test_template_variable_format_error(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试模板变量格式错误"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        # 创建一个包含格式错误的模板变量
        apply_data = {
            'template_id': 'system_maintenance',
            'variables': {
                'maintenance_time': '2024-01-15 02:00-06:00',
                # 使用一个在模板中不存在的变量
                'nonexistent_variable': 'test value'
            }
        }

        response = client.post('/api/notice/templates/apply',
                             data=json.dumps(apply_data),
                             content_type='application/json')
        # 应该有相应的错误处理
        assert response.status_code in [200, 400]

    def test_concurrent_template_apply(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试并发应用模板"""
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        apply_data = {
            'template_id': 'feature_update',
            'variables': {
                'new_features': '新功能测试',
                'improved_features': '功能优化测试',
                'update_time': '2024-01-15',
                'version_number': '1.0.0',
                'company_name': '测试公司',
                'date': '2024-01-15'
            }
        }

        # 模拟并发应用模板
        response1 = client.post('/api/notice/templates/apply',
                               data=json.dumps(apply_data),
                               content_type='application/json')

        response2 = client.post('/api/notice/templates/apply',
                               data=json.dumps(apply_data),
                               content_type='application/json')

        # 两个请求都应该成功，因为模板应用是只读操作
        assert response1.status_code == 200
        assert response2.status_code == 200