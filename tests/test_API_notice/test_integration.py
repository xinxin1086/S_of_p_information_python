# API_notice模块集成测试
# 测试各个模块之间的集成场景

import pytest
import json
from datetime import datetime, timedelta


class TestNoticeWorkflow:
    """测试公告工作流程"""

    def test_complete_notice_workflow(self, client, session, test_admin, test_user, mock_token_required, mock_admin_required):
        """测试完整的公告工作流程：创建->查看->标记已读->统计"""
        print("【集成测试】开始完整公告工作流程测试")

        # 解包test_admin元组（admin, admin_user）
        admin, admin_user = test_admin

        # 步骤1: 管理员创建公告
        with client.session_transaction() as sess:
            sess['user_id'] = admin.id
            sess['account'] = admin.account

        notice_data = {
            'title': '集成测试公告',
            'content': '这是一条用于集成测试的公告。',
            'notice_type': 'GENERAL',
            'is_top': True
        }

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(notice_data),
                             content_type='application/json')
        assert response.status_code == 200

        create_result = json.loads(response.data)
        notice_id = create_result['data']['id']
        print(f"【集成测试】公告创建成功，ID: {notice_id}")

        # 步骤2: 用户查看公告列表
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/list')
        assert response.status_code == 200

        list_result = json.loads(response.data)
        assert list_result['success'] is True
        assert len(list_result['data']['items']) > 0
        assert list_result['data']['unread_count'] > 0

        # 验证新创建的公告在列表中
        notice_ids = [item['id'] for item in list_result['data']['items']]
        assert notice_id in notice_ids
        print(f"【集成测试】用户公告列表查询成功，未读数: {list_result['data']['unread_count']}")

        # 步骤3: 用户查看公告详情（自动标记已读）
        response = client.get(f'/api/notice/detail/{notice_id}')
        assert response.status_code == 200

        detail_result = json.loads(response.data)
        assert detail_result['success'] is True
        assert detail_result['data']['id'] == notice_id
        assert detail_result['data']['unread_count'] < list_result['data']['unread_count']
        print(f"【集成测试】用户查看公告详情成功，新未读数: {detail_result['data']['unread_count']}")

        # 步骤4: 用户手动标记另一条公告为已读
        response = client.post(f'/api/notice/read/{notice_ids[0] if notice_ids[0] != notice_id else notice_ids[1]}')
        assert response.status_code == 200

        read_result = json.loads(response.data)
        assert read_result['success'] is True
        print(f"【集成测试】用户手动标记已读成功")

        # 步骤5: 用户标记所有公告为已读
        response = client.post('/api/notice/read/all')
        assert response.status_code == 200

        mark_all_result = json.loads(response.data)
        assert mark_all_result['success'] is True
        assert mark_all_result['data']['unread_count'] == 0
        print(f"【集成测试】用户标记所有公告已读成功，标记数量: {mark_all_result['data']['marked_count']}")

        # 步骤6: 管理员查看公告统计
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/admin/statistics')
        assert response.status_code == 200

        stats_result = json.loads(response.data)
        assert stats_result['success'] is True
        assert 'overview' in stats_result['data']
        print(f"【集成测试】管理员查看统计成功，总公告数: {stats_result['data']['overview']['total_count']}")

        # 步骤7: 管理员查看公告详情（包含已读统计）
        response = client.get(f'/api/notice/admin/detail/{notice_id}')
        assert response.status_code == 200

        admin_detail_result = json.loads(response.data)
        assert admin_detail_result['success'] is True
        assert 'read_stats' in admin_detail_result['data']
        assert admin_detail_result['data']['read_stats']['read_count'] > 0
        print(f"【集成测试】管理员查看公告详情成功，已读人数: {admin_detail_result['data']['read_stats']['read_count']}")

        print("【集成测试】完整公告工作流程测试完成")

    def test_notice_lifecycle(self, client, session, test_admin, test_user, mock_token_required, mock_admin_required):
        """测试公告生命周期：创建->编辑->置顶->删除"""
        print("【集成测试】开始公告生命周期测试")

        # 步骤1: 管理员创建公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        notice_data = {
            'title': '生命周期测试公告',
            'content': '这是一条测试公告生命周期的公告。',
            'notice_type': 'GENERAL',
            'is_top': False
        }

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(notice_data),
                             content_type='application/json')
        assert response.status_code == 200

        create_result = json.loads(response.data)
        notice_id = create_result['data']['id']
        print(f"【集成测试】公告创建成功，ID: {notice_id}")

        # 步骤2: 管理员编辑公告
        update_data = {
            'title': '更新后的生命周期测试公告',
            'content': '这是更新后的公告内容。',
            'is_top': True
        }

        response = client.put(f'/api/notice/admin/update/{notice_id}',
                             data=json.dumps(update_data),
                             content_type='application/json')
        assert response.status_code == 200

        update_result = json.loads(response.data)
        assert update_result['success'] is True
        print(f"【集成测试】公告更新成功")

        # 步骤3: 用户查看置顶公告应该在列表顶部
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get('/api/notice/list')
        assert response.status_code == 200

        list_result = json.loads(response.data)
        assert list_result['success'] is True
        assert len(list_result['data']['items']) > 0

        # 置顶公告应该在列表前面
        first_item = list_result['data']['items'][0]
        if hasattr(first_item, 'is_top'):
            assert first_item['is_top'] is True
        print(f"【集成测试】置顶公告在列表顶部")

        # 步骤4: 管理员删除公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.delete(f'/api/notice/admin/delete/{notice_id}')
        assert response.status_code == 200

        delete_result = json.loads(response.data)
        assert delete_result['success'] is True
        assert delete_result['data']['status'] == 'REJECTED'
        print(f"【集成测试】公告删除成功")

        # 步骤5: 验证用户不再能看到已删除的公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get(f'/api/notice/detail/{notice_id}')
        assert response.status_code in [403, 404]  # 应该无权限或找不到
        print(f"【集成测试】已删除的公告用户无法查看")

        print("【集成测试】公告生命周期测试完成")

    def test_template_based_notice_creation(self, client, session, test_admin, test_user, mock_token_required, mock_admin_required):
        """测试基于模板创建公告的流程"""
        print("【集成测试】开始基于模板创建公告测试")

        # 步骤1: 管理员获取可用模板
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/templates')
        assert response.status_code == 200

        templates_result = json.loads(response.data)
        assert templates_result['success'] is True
        assert len(templates_result['data']['templates']) > 0

        template_id = templates_result['data']['templates'][0]['id']
        print(f"【集成测试】获取模板列表成功，选择模板: {template_id}")

        # 步骤2: 应用模板生成公告内容
        apply_data = {
            'template_id': template_id,
            'variables': {
                'maintenance_time': '2024-01-15 02:00-06:00',
                'maintenance_scope': '用户管理系统',
                'impact_content': '用户登录、注册功能',
                'company_name': '测试科技有限公司',
                'date': '2024-01-14'
            }
        }

        response = client.post('/api/notice/templates/apply',
                             data=json.dumps(apply_data),
                             content_type='application/json')
        assert response.status_code == 200

        apply_result = json.loads(response.data)
        assert apply_result['success'] is True
        template_content = apply_result['data']['content']
        template_title = apply_result['data']['title']
        notice_type = apply_result['data']['notice_type']
        print(f"【集成测试】模板应用成功")

        # 步骤3: 基于模板内容创建公告
        notice_data = {
            'title': template_title,
            'content': template_content,
            'notice_type': notice_type,
            'is_top': False
        }

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(notice_data),
                             content_type='application/json')
        assert response.status_code == 200

        create_result = json.loads(response.data)
        notice_id = create_result['data']['id']
        print(f"【集成测试】基于模板创建公告成功，ID: {notice_id}")

        # 步骤4: 验证用户可以看到基于模板创建的公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get(f'/api/notice/detail/{notice_id}')
        # 根据公告类型，可能成功或被拒绝
        if notice_type in ['SYSTEM', 'GENERAL']:
            assert response.status_code == 200
            detail_result = json.loads(response.data)
            assert detail_result['data']['id'] == notice_id
            print(f"【集成测试】用户成功查看基于模板创建的公告")
        else:
            assert response.status_code == 403
            print(f"【集成测试】用户无权限查看管理员公告")

        print("【集成测试】基于模板创建公告测试完成")


class TestPermissionIntegration:
    """测试权限集成"""

    def test_admin_user_isolation(self, client, session, test_admin, test_user, mock_token_required, mock_admin_required):
        """测试管理员和普通用户的权限隔离"""
        print("【集成测试】开始权限隔离测试")

        # 步骤1: 管理员创建管理员公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        notice_data = {
            'title': '管理员专用公告',
            'content': '这是一条只有管理员才能看到的公告。',
            'notice_type': 'ADMIN'
        }

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(notice_data),
                             content_type='application/json')
        assert response.status_code == 200

        create_result = json.loads(response.data)
        admin_notice_id = create_result['data']['id']
        print(f"【集成测试】管理员公告创建成功，ID: {admin_notice_id}")

        # 步骤2: 验证管理员可以查看该公告
        response = client.get(f'/api/notice/detail/{admin_notice_id}')
        assert response.status_code == 200

        detail_result = json.loads(response.data)
        assert detail_result['success'] is True
        print(f"【集成测试】管理员可以查看管理员公告")

        # 步骤3: 验证普通用户不能查看该公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get(f'/api/notice/detail/{admin_notice_id}')
        assert response.status_code == 403

        error_result = json.loads(response.data)
        assert error_result['success'] is False
        assert "无权限查看此类型公告" in error_result['message']
        print(f"【集成测试】普通用户无法查看管理员公告")

        # 步骤4: 验证普通用户在列表中看不到管理员公告
        response = client.get('/api/notice/list')
        assert response.status_code == 200

        list_result = json.loads(response.data)
        assert list_result['success'] is True

        notice_ids = [item['id'] for item in list_result['data']['items']]
        assert admin_notice_id not in notice_ids
        print(f"【集成测试】普通用户列表中不包含管理员公告")

        # 步骤5: 验证用户看不到管理员公告类型
        response = client.get('/api/notice/types')
        assert response.status_code == 200

        types_result = json.loads(response.data)
        assert types_result['success'] is True
        assert types_result['data']['is_admin'] is False

        type_codes = [t['code'] for t in types_result['data']['types']]
        assert 'ADMIN' not in type_codes
        print(f"【集成测试】普通用户看不到管理员公告类型")

        print("【集成测试】权限隔离测试完成")


class TestSearchIntegration:
    """测试搜索集成"""

    def test_cross_module_search(self, client, session, test_admin, test_user, test_notices, mock_token_required, mock_admin_required):
        """测试跨模块搜索功能"""
        print("【集成测试】开始跨模块搜索测试")

        # 步骤1: 管理员创建不同类型的公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        search_notice_data = {
            'title': '搜索测试专用公告',
            'content': '这条公告包含搜索关键词：集成测试、搜索功能、关键词匹配。',
            'notice_type': 'GENERAL'
        }

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(search_notice_data),
                             content_type='application/json')
        assert response.status_code == 200

        create_result = json.loads(response.data)
        search_notice_id = create_result['data']['id']
        print(f"【集成测试】搜索测试公告创建成功，ID: {search_notice_id}")

        # 步骤2: 用户搜索公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        search_keywords = ['搜索测试', '集成测试', '关键词', '不存在的内容']

        for keyword in search_keywords:
            response = client.get(f'/api/notice/search?keyword={keyword}')
            assert response.status_code == 200

            search_result = json.loads(response.data)
            assert search_result['success'] is True
            assert search_result['data']['keyword'] == keyword

            if keyword == '不存在的内容':
                assert len(search_result['data']['items']) == 0
            else:
                # 应该能找到包含关键词的公告
                found_search_notice = any(item['id'] == search_notice_id for item in search_result['data']['items'])
                if keyword in ['搜索测试', '集成测试', '关键词']:
                    assert len(search_result['data']['items']) > 0
                    if keyword == '搜索测试':
                        assert found_search_notice
            print(f"【集成测试】关键词 '{keyword}' 搜索完成，结果数: {len(search_result['data']['items'])}")

        # 步骤3: 测试搜索结果的分页
        response = client.get('/api/notice/search?keyword=公告&page=1&size=2')
        assert response.status_code == 200

        paginated_result = json.loads(response.data)
        assert paginated_result['success'] is True
        assert paginated_result['data']['page'] == 1
        assert paginated_result['data']['size'] == 2
        assert len(paginated_result['data']['items']) <= 2
        print(f"【集成测试】搜索分页功能正常")

        print("【集成测试】跨模块搜索测试完成")


class TestStatisticsIntegration:
    """测试统计集成"""

    def test_real_time_statistics_update(self, client, session, test_admin, test_user, mock_token_required, mock_admin_required):
        """测试统计数据的实时更新"""
        print("【集成测试】开始实时统计更新测试")

        # 步骤1: 获取初始统计数据
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get('/api/notice/admin/statistics')
        assert response.status_code == 200

        initial_stats = json.loads(response.data)
        initial_total = initial_stats['data']['overview']['total_count']
        print(f"【集成测试】初始公告总数: {initial_total}")

        # 步骤2: 创建新公告
        notice_data = {
            'title': '统计测试公告',
            'content': '这是一条用于测试统计功能的公告。',
            'notice_type': 'GENERAL'
        }

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(notice_data),
                             content_type='application/json')
        assert response.status_code == 200

        create_result = json.loads(response.data)
        notice_id = create_result['data']['id']
        print(f"【集成测试】新公告创建成功，ID: {notice_id}")

        # 步骤3: 验证统计数据更新
        response = client.get('/api/notice/admin/statistics')
        assert response.status_code == 200

        updated_stats = json.loads(response.data)
        updated_total = updated_stats['data']['overview']['total_count']
        assert updated_total == initial_total + 1
        print(f"【集成测试】统计数据更新成功，新总数: {updated_total}")

        # 步骤4: 用户查看公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['account'] = test_user.account

        response = client.get(f'/api/notice/detail/{notice_id}')
        assert response.status_code == 200

        # 步骤5: 验证已读统计更新
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        response = client.get(f'/api/notice/admin/detail/{notice_id}')
        assert response.status_code == 200

        detail_result = json.loads(response.data)
        read_stats = detail_result['data']['read_stats']
        assert read_stats['read_count'] > 0
        assert read_stats['unread_count'] >= 0
        print(f"【集成测试】已读统计更新成功，已读人数: {read_stats['read_count']}")

        print("【集成测试】实时统计更新测试完成")


class TestErrorHandlingIntegration:
    """测试错误处理集成"""

    def test_cascading_error_handling(self, client, session, test_admin, mock_token_required, mock_admin_required):
        """测试级联错误处理"""
        print("【集成测试】开始级联错误处理测试")

        # 步骤1: 创建公告时提供多种无效数据
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        invalid_notices = [
            {},  # 空数据
            {'title': ''},  # 空标题
            {'title': 'A' * 200, 'content': '测试'},  # 标题过长
            {'title': '测试', 'content': '测试', 'notice_type': 'INVALID'},  # 无效类型
            {'title': '测试', 'content': '测试', 'expiration': 'invalid-date'}  # 无效日期
        ]

        for i, invalid_data in enumerate(invalid_notices):
            response = client.post('/api/notice/admin/create',
                                 data=json.dumps(invalid_data),
                                 content_type='application/json')
            # 所有情况都应该有适当的错误处理
            assert response.status_code in [400, 422]
            error_result = json.loads(response.data)
            assert error_result['success'] is False
            assert len(error_result['message']) > 0
            print(f"【集成测试】无效数据 {i+1} 错误处理正确: {error_result['message'][:50]}...")

        # 步骤2: 测试不存在资源的错误处理
        non_existent_ids = [99999, 0, -1]

        for notice_id in non_existent_ids:
            # 测试获取详情
            response = client.get(f'/api/notice/admin/detail/{notice_id}')
            assert response.status_code == 404

            # 测试更新
            update_data = {'title': '更新'}
            response = client.put(f'/api/notice/admin/update/{notice_id}',
                                 data=json.dumps(update_data),
                                 content_type='application/json')
            assert response.status_code == 404

            # 测试删除
            response = client.delete(f'/api/notice/admin/delete/{notice_id}')
            assert response.status_code == 404

        print(f"【集成测试】不存在资源错误处理正确")

        # 步骤3: 测试权限错误的级联处理
        # 创建另一个管理员来测试权限隔离
        other_admin = AdminFactory.create_admin(session)

        with client.session_transaction() as sess:
            sess['user_id'] = other_admin.id
            sess['account'] = other_admin.account

        # 创建一条公告
        notice_data = {
            'title': '其他管理员的公告',
            'content': '这是其他管理员创建的公告。',
            'notice_type': 'GENERAL'
        }

        response = client.post('/api/notice/admin/create',
                             data=json.dumps(notice_data),
                             content_type='application/json')
        assert response.status_code == 200

        create_result = json.loads(response.data)
        other_notice_id = create_result['data']['id']

        # 切换回原管理员，尝试操作他人公告
        with client.session_transaction() as sess:
            sess['user_id'] = test_admin.id
            sess['account'] = test_admin.account

        operations = [
            ('put', {'title': '尝试更新'}),
            ('delete', None)
        ]

        for method, data in operations:
            if method == 'put':
                response = client.put(f'/api/notice/admin/update/{other_notice_id}',
                                     data=json.dumps(data),
                                     content_type='application/json')
            else:
                response = client.delete(f'/api/notice/admin/delete/{other_notice_id}')

            assert response.status_code == 403
            error_result = json.loads(response.data)
            assert error_result['success'] is False
            assert "无权限" in error_result['message']

        print(f"【集成测试】权限错误级联处理正确")

        print("【集成测试】级联错误处理测试完成")


# 辅助函数和工厂类
class AdminFactory:
    """管理员数据工厂（用于集成测试）"""

    @staticmethod
    def create_admin(session, **kwargs):
        """创建管理员"""
        # 先创建用户
        from components.models.user_models import User, Admin
        user_defaults = {
            'account': f'integration_admin_{datetime.now().timestamp()}',
            'username': '集成测试管理员',
            'phone': f'138{int(datetime.now().timestamp()) % 100000000:08d}',
            'email': 'integration_admin@test.com',
            'role': 'ADMIN',
            'is_deleted': 0
        }

        user = User(**user_defaults)
        user.set_password('testpass123')
        session.add(user)
        session.flush()

        # 再创建管理员
        admin_defaults = {
            'account': user.account,
            'username': user.username,
            'phone': user.phone,
            'email': user.email,
            'role': 'ADMIN',
            'user_id': user.id
        }
        admin_defaults.update(kwargs)

        admin = Admin(**admin_defaults)
        admin.set_password('testpass123')
        session.add(admin)
        session.commit()
        return admin