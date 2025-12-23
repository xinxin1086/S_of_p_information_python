# 公共工具模块测试

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from API_admin.common.utils import (
    super_admin_required,
    log_admin_operation,
    export_to_csv,
    validate_date_range,
    encrypt_sensitive_data,
    batch_update_user_display,
    check_system_security
)

class TestValidateDateRange:
    """日期范围验证测试"""

    def test_valid_date_range(self):
        """测试有效日期范围"""
        is_valid, error_msg = validate_date_range('2024-01-01', '2024-12-31')
        assert is_valid is True
        assert error_msg is None

    def test_start_date_after_end_date(self):
        """测试开始日期晚于结束日期"""
        is_valid, error_msg = validate_date_range('2024-12-31', '2024-01-01')
        assert is_valid is False
        assert '开始日期不能晚于结束日期' in error_msg

    def test_start_date_in_future(self):
        """测试开始日期在未来"""
        future_date = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
        is_valid, error_msg = validate_date_range(future_date, '2024-12-31')
        assert is_valid is False
        assert '开始日期不能晚于当前日期' in error_msg

    def test_date_range_too_long(self):
        """测试日期范围超过1年"""
        is_valid, error_msg = validate_date_range('2023-01-01', '2024-12-31')
        assert is_valid is False
        assert '查询时间范围不能超过1年' in error_msg

    def test_invalid_date_format(self):
        """测试无效日期格式"""
        is_valid, error_msg = validate_date_range('2024-13-01', '2024-12-31')
        assert is_valid is False
        assert '日期格式不正确' in error_msg

    def test_empty_date_range(self):
        """测试空日期范围"""
        is_valid, error_msg = validate_date_range('', '')
        assert is_valid is True
        assert error_msg is None

    def test_partial_date_range(self):
        """测试部分日期范围"""
        is_valid, error_msg = validate_date_range('2024-01-01', '')
        assert is_valid is True
        assert error_msg is None

class TestEncryptSensitiveData:
    """敏感数据加密测试"""

    def test_encrypt_string(self):
        """测试字符串加密"""
        data = "sensitive_password"
        encrypted = encrypt_sensitive_data(data)
        assert encrypted is not None
        assert isinstance(encrypted, str)
        assert encrypted != data  # 加密后应该与原数据不同

    def test_encrypt_empty_string(self):
        """测试空字符串加密"""
        data = ""
        encrypted = encrypt_sensitive_data(data)
        assert encrypted is not None
        assert isinstance(encrypted, str)

    def test_encrypt_unicode(self):
        """测试Unicode字符串加密"""
        data = "敏感信息测试123"
        encrypted = encrypt_sensitive_data(data)
        assert encrypted is not None
        assert isinstance(encrypted, str)

class TestExportToCSV:
    """CSV导出功能测试"""

    def test_export_dict_data(self):
        """测试导出字典数据"""
        data = [
            {'name': '测试1', 'value': 100, 'status': 'active'},
            {'name': '测试2', 'value': 200, 'status': 'inactive'}
        ]
        headers = ['姓名', '数值', '状态']

        with patch('flask.Response') as mock_response:
            mock_response_instance = MagicMock()
            mock_response.return_value = mock_response_instance

            result = export_to_csv(data, 'test.csv', headers)
            assert result == mock_response_instance
            mock_response.assert_called_once()

    def test_export_list_data(self):
        """测试导出列表数据"""
        data = [
            ['测试1', 100, 'active'],
            ['测试2', 200, 'inactive']
        ]
        headers = ['姓名', '数值', '状态']

        with patch('flask.Response') as mock_response:
            mock_response_instance = MagicMock()
            mock_response.return_value = mock_response_instance

            result = export_to_csv(data, 'test.csv', headers)
            assert result == mock_response_instance

    def test_export_no_headers(self):
        """测试无头部导出"""
        data = [['测试1', 100], ['测试2', 200]]

        with patch('flask.Response') as mock_response:
            mock_response_instance = MagicMock()
            mock_response.return_value = mock_response_instance

            result = export_to_csv(data, 'test.csv')
            assert result == mock_response_instance

    def test_export_empty_data(self):
        """测试空数据导出"""
        data = []

        with patch('flask.Response') as mock_response:
            mock_response_instance = MagicMock()
            mock_response.return_value = mock_response_instance

            result = export_to_csv(data, 'empty.csv')
            assert result == mock_response_instance

class TestSuperAdminRequired:
    """超级管理员权限装饰器测试"""

    def test_super_admin_required_success(self, app):
        """测试超级管理员权限验证成功"""
        with app.test_request_context():
            # 模拟超级管理员用户
            mock_user = MagicMock()
            mock_user.role = 'SUPER_ADMIN'
            mock_user.id = 1

            @super_admin_required
            def test_function(current_user):
                return {'success': True, 'user': current_user.username}

            # 模拟 token_required 装饰器已经通过
            from functools import wraps
            def mock_token_required(f):
                @wraps(f)
                def decorated_function(*args, **kwargs):
                    return f(mock_user, *args, **kwargs)
                return decorated_function

            # 临时替换装饰器
            with patch('API_admin.common.utils.token_required', mock_token_required):
                with patch('flask.request'):
                    result = test_function()
                    assert result['success'] is True

    def test_super_admin_required_regular_admin(self, app):
        """测试普通管理员权限被拒绝"""
        with app.test_request_context():
            # 模拟普通管理员用户
            mock_user = MagicMock()
            mock_user.role = 'ADMIN'
            mock_user.id = 2

            @super_admin_required
            def test_function(current_user):
                return {'success': True}

            # 模拟 token_required 装饰器
            from functools import wraps
            def mock_token_required(f):
                @wraps(f)
                def decorated_function(*args, **kwargs):
                    return f(mock_user, *args, **kwargs)
                return decorated_function

            with patch('API_admin.common.utils.token_required', mock_token_required):
                with patch('flask.request'), \
                     patch('flask.jsonify') as mock_jsonify:
                    mock_jsonify.return_value = ({'success': False}, 403)
                    result = test_function()
                    assert result[1] == 403

    def test_super_admin_required_no_role(self, app):
        """测试无角色属性用户被拒绝"""
        with app.test_request_context():
            # 模拟无角色属性的用户
            mock_user = MagicMock()
            del mock_user.role  # 删除role属性
            mock_user.id = 3

            @super_admin_required
            def test_function(current_user):
                return {'success': True}

            from functools import wraps
            def mock_token_required(f):
                @wraps(f)
                def decorated_function(*args, **kwargs):
                    return f(mock_user, *args, **kwargs)
                return decorated_function

            with patch('API_admin.common.utils.token_required', mock_token_required):
                with patch('flask.request'), \
                     patch('flask.jsonify') as mock_jsonify:
                    mock_jsonify.return_value = ({'success': False}, 403)
                    result = test_function()
                    assert result[1] == 403

class TestLogAdminOperation:
    """管理员操作日志记录测试"""

    def test_log_admin_operation_basic(self):
        """测试基本操作日志记录"""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = 'test_admin'

        # 测试日志记录（应该不会抛出异常）
        try:
            log_admin_operation(
                mock_user,
                'CREATE',
                'test_table',
                target_id=123,
                details={'action': 'test'}
            )
        except Exception as e:
            pytest.fail(f"日志记录抛出异常: {e}")

    def test_log_admin_operation_minimal_data(self):
        """测试最小数据日志记录"""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = 'test_admin'

        try:
            log_admin_operation(mock_user, 'VIEW', 'test_table')
        except Exception as e:
            pytest.fail(f"最小数据日志记录抛出异常: {e}")

class TestBatchUpdateUserDisplay:
    """批量更新用户显示信息测试"""

    def test_batch_update_user_display_structure(self):
        """测试批量更新用户显示信息的返回结构"""
        # 这个测试需要数据库连接，所以主要测试函数结构
        with patch('API_admin.common.utils.db') as mock_db:
            mock_db.session.execute.return_value.rowcount = 5
            mock_db.session.commit.return_value = None

            result = batch_update_user_display()

            assert 'success' in result
            assert 'total_updated' in result
            assert 'updates_by_type' in result

class TestCheckSystemSecurity:
    """系统安全检查测试"""

    def test_check_system_security_structure(self):
        """测试系统安全检查返回结构"""
        with patch('API_admin.common.utils.Admin') as mock_admin, \
             patch('API_admin.common.utils.os') as mock_os:

            # 模拟没有默认密码的管理员
            mock_admin.query.filter_by.return_value.count.return_value = 0
            mock_os.exists.return_value = True
            mock_os.stat.return_value.st_mode = 0o644

            result = check_system_security()

            assert 'overall_status' in result
            assert 'checks' in result
            assert isinstance(result['overall_status'], str)
            assert isinstance(result['checks'], dict)

    def test_check_system_security_with_default_password(self):
        """测试检测默认密码的安全检查"""
        with patch('API_admin.common.utils.Admin') as mock_admin:
            # 模拟有管理员使用默认密码
            mock_admin.query.filter_by.return_value.count.return_value = 2

            result = check_system_security()

            assert result['overall_status'] == 'critical'
            assert 'default_password' in result['checks']
            assert result['checks']['default_password']['status'] == 'critical'

class TestIntegration:
    """集成测试"""

    def test_super_admin_required_with_log_operation(self, app):
        """测试超级管理员装饰器与日志记录的集成"""
        with app.test_request_context():
            mock_user = MagicMock()
            mock_user.role = 'SUPER_ADMIN'
            mock_user.id = 1
            mock_user.username = 'integration_admin'

            @super_admin_required
            def integration_test(current_user):
                # 在权限通过后记录操作日志
                log_admin_operation(current_user, 'TEST', 'integration_table')
                return {'success': True}

            from functools import wraps
            def mock_token_required(f):
                @wraps(f)
                def decorated_function(*args, **kwargs):
                    return f(mock_user, *args, **kwargs)
                return decorated_function

            with patch('API_admin.common.utils.token_required', mock_token_required):
                with patch('flask.request'):
                    try:
                        result = integration_test()
                        assert result['success'] is True
                    except Exception as e:
                        pytest.fail(f"集成测试失败: {e}")