# 内容审核管理接口测试

import pytest
import json
from datetime import datetime
from .conftest import get_auth_headers, assert_success_response, assert_error_response, assert_permission_denied

class TestPendingContentManagement:
    """待审核内容管理接口测试"""

    def test_get_all_pending_content_success(self, client, super_admin_token):
        """测试成功获取所有模块的待审核内容"""
        response = client.get('/api/admin/content/pending/all',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        assert 'data' in data
        assert 'modules' in data['data']
        assert 'science_articles' in data['data']['modules']
        assert 'activities' in data['data']['modules']
        assert 'forum_discussions' in data['data']['modules']
        assert 'summary' in data['data']
        assert 'total_pending' in data['data']
        assert 'filters' in data['data']

    def test_get_pending_science_articles_only(self, client, super_admin_token):
        """测试只获取科普文章待审核内容"""
        params = {'module': 'science', 'status': 'pending', 'page': 1, 'size': 10}

        response = client.get('/api/admin/content/pending/all',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        assert 'science_articles' in data['data']['modules']
        # 验证返回的结构包含必要字段
        science_articles = data['data']['modules']['science_articles']
        assert 'total' in science_articles
        assert 'items' in science_articles
        if science_articles['items']:
            item = science_articles['items'][0]
            assert 'id' in item
            assert 'title' in item
            assert 'author' in item
            assert 'status' in item
            assert 'created_at' in item

    def test_get_pending_activities_only(self, client, super_admin_token):
        """测试只获取活动待审核内容"""
        params = {'module': 'activity', 'status': 'pending', 'page': 1, 'size': 10}

        response = client.get('/api/admin/content/pending/all',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        assert 'activities' in data['data']['modules']
        activities = data['data']['modules']['activities']
        assert 'total' in activities
        assert 'items' in activities
        if activities['items']:
            item = activities['items'][0]
            assert 'id' in item
            assert 'title' in item
            assert 'organizer' in item
            assert 'activity_type' in item

    def test_get_pending_forum_discussions_only(self, client, super_admin_token):
        """测试只获取论坛讨论待审核内容"""
        params = {'module': 'forum', 'status': 'pending', 'page': 1, 'size': 10}

        response = client.get('/api/admin/content/pending/all',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        assert 'forum_discussions' in data['data']['modules']
        discussions = data['data']['modules']['forum_discussions']
        assert 'total' in discussions
        assert 'items' in discussions
        if discussions['items']:
            item = discussions['items'][0]
            assert 'id' in item
            assert 'title' in item
            assert 'content' in item  # 论坛讨论包含内容预览

    def test_get_pending_content_with_different_status(self, client, super_admin_token):
        """测试获取不同状态的待审核内容"""
        statuses = ['pending', 'draft', 'published', 'rejected']

        for status in statuses:
            params = {'status': status, 'page': 1, 'size': 5}

            response = client.get('/api/admin/content/pending/all',
                                headers=get_auth_headers(super_admin_token),
                                query_string=params)

            data = assert_success_response(response)
            assert data['data']['filters']['status'] == status

    def test_get_pending_content_pagination_parameters(self, client, super_admin_token):
        """测试分页参数的有效性"""
        test_cases = [
            {'page': 1, 'size': 5},
            {'page': 2, 'size': 20},
            {'page': 1, 'size': 50}
        ]

        for params in test_cases:
            response = client.get('/api/admin/content/pending/all',
                                headers=get_auth_headers(super_admin_token),
                                query_string=params)

            data = assert_success_response(response)
            filters = data['data']['filters']
            assert filters['page'] == params['page']
            assert filters['size'] == params['size']

    def test_get_pending_content_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权访问"""
        for token in [regular_admin_token, user_token]:
            response = client.get('/api/admin/content/pending/all',
                                headers=get_auth_headers(token))
            assert_permission_denied(response)

    def test_get_pending_content_unauthorized(self, client):
        """测试未授权访问"""
        response = client.get('/api/admin/content/pending/all')
        assert response.status_code == 401

class TestBatchContentReview:
    """批量内容审核接口测试"""

    def test_batch_approve_science_articles(self, client, super_admin_token):
        """测试批量审核通过科普文章"""
        review_data = {
            'action': 'approve',
            'content_list': [
                {'module': 'science', 'id': 1, 'reason': '内容科学严谨，审核通过'},
                {'module': 'science', 'id': 2, 'reason': '文章质量优秀，符合发布标准'}
            ],
            'review_comment': '科普文章批量审核通过'
        }

        response = client.post('/api/admin/content/batch-review',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(review_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'success_count' in data['data']
        assert 'error_count' in data['data']
        assert 'total_processed' in data['data']
        assert 'action' in data['data']
        assert data['data']['action'] == 'approve'

    def test_batch_reject_activities(self, client, super_admin_token):
        """测试批量审核拒绝活动"""
        review_data = {
            'action': 'reject',
            'content_list': [
                {'module': 'activity', 'id': 1, 'reason': '活动存在安全隐患，不予通过'},
                {'module': 'activity', 'id': 2, 'reason': '活动方案不完善，需要重新策划'}
            ],
            'review_comment': '活动批量审核拒绝'
        }

        response = client.post('/api/admin/content/batch-review',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(review_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['action'] == 'reject'

    def test_batch_request_changes_forum_discussions(self, client, super_admin_token):
        """测试批量要求修改论坛讨论"""
        review_data = {
            'action': 'request_changes',
            'content_list': [
                {'module': 'forum', 'id': 1, 'reason': '讨论内容不够充实，需要补充更多细节'},
                {'module': 'forum', 'id': 2, 'reason': '标题与内容不符，需要调整'}
            ],
            'review_comment': '论坛讨论批量退回修改'
        }

        response = client.post('/api/admin/content/batch-review',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(review_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert data['data']['action'] == 'request_changes'

    def test_batch_review_mixed_modules(self, client, super_admin_token):
        """测试跨模块批量审核"""
        review_data = {
            'action': 'approve',
            'content_list': [
                {'module': 'science', 'id': 1, 'reason': '科普文章质量优秀'},
                {'module': 'activity', 'id': 1, 'reason': '活动方案合理可行'},
                {'module': 'forum', 'id': 1, 'reason': '讨论内容健康向上'}
            ],
            'review_comment': '跨模块批量审核通过'
        }

        response = client.post('/api/admin/content/batch-review',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(review_data),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'success_count' in data['data']
        assert 'error_count' in data['data']

    def test_batch_review_empty_content_list(self, client, super_admin_token):
        """测试批量审核空内容列表"""
        review_data = {
            'action': 'approve',
            'content_list': [],
            'review_comment': '空列表测试'
        }

        response = client.post('/api/admin/content/batch-review',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(review_data),
                             content_type='application/json')

        assert_error_response(response, 400, '请提供要审核的内容列表')

    def test_batch_review_invalid_action(self, client, super_admin_token):
        """测试无效的审核动作"""
        review_data = {
            'action': 'invalid_action',
            'content_list': [
                {'module': 'science', 'id': 1, 'reason': '测试无效动作'}
            ]
        }

        response = client.post('/api/admin/content/batch-review',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(review_data),
                             content_type='application/json')

        # 应该处理无效动作，但不应该完全失败
        data = response.get_json()
        assert 'success' in data
        if not data['success']:
            assert 'message' in data

    def test_batch_review_with_invalid_modules(self, client, super_admin_token):
        """测试包含无效模块的批量审核"""
        review_data = {
            'action': 'approve',
            'content_list': [
                {'module': 'science', 'id': 1, 'reason': '有效的科普文章'},
                {'module': 'invalid_module', 'id': 999, 'reason': '无效的模块'}
            ]
        }

        response = client.post('/api/admin/content/batch-review',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(review_data),
                             content_type='application/json')

        data = assert_success_response(response)
        # 应该部分成功，部分失败
        assert 'errors' in data['data']
        assert 'success_count' in data['data']
        assert 'error_count' in data['data']

    def test_batch_review_with_nonexistent_content(self, client, super_admin_token):
        """测试包含不存在内容的批量审核"""
        review_data = {
            'action': 'approve',
            'content_list': [
                {'module': 'science', 'id': 99999, 'reason': '不存在的科普文章'}
            ]
        }

        response = client.post('/api/admin/content/batch-review',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(review_data),
                             content_type='application/json')

        data = assert_success_response(response)
        # 应该有错误信息
        assert 'errors' in data['data']
        assert data['data']['error_count'] > 0

    def test_batch_review_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权批量审核"""
        review_data = {
            'action': 'approve',
            'content_list': [{'module': 'science', 'id': 1, 'reason': '权限测试'}]
        }

        for token in [regular_admin_token, user_token]:
            response = client.post('/api/admin/content/batch-review',
                                 headers=get_auth_headers(token),
                                 data=json.dumps(review_data),
                                 content_type='application/json')
            assert_permission_denied(response)

    def test_batch_review_missing_auth_token(self, client):
        """测试缺少认证令牌"""
        review_data = {
            'action': 'approve',
            'content_list': [{'module': 'science', 'id': 1}]
        }

        response = client.post('/api/admin/content/batch-review',
                             data=json.dumps(review_data),
                             content_type='application/json')

        assert response.status_code == 401

class TestContentDetailView:
    """内容详情查看接口测试"""

    def test_get_science_article_detail_success(self, client, super_admin_token):
        """测试成功获取科普文章详情"""
        response = client.get('/api/admin/content/detail/science/1',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        assert 'data' in data
        article_detail = data['data']

        # 验证科普文章特有字段
        required_fields = ['id', 'title', 'content', 'summary', 'author_display',
                          'author_user_id', 'status', 'tags', 'category', 'cover_image',
                          'view_count', 'like_count', 'created_at', 'updated_at']

        for field in required_fields:
            assert field in article_detail, f"Missing field: {field}"

        # 验证审核相关字段
        review_fields = ['review_comment', 'reviewed_by', 'reviewed_at']
        for field in review_fields:
            assert field in article_detail, f"Missing review field: {field}"

    def test_get_activity_detail_success(self, client, super_admin_token):
        """测试成功获取活动详情"""
        response = client.get('/api/admin/content/detail/activity/1',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        assert 'data' in data
        activity_detail = data['data']

        # 验证活动特有字段
        required_fields = ['id', 'title', 'description', 'organizer_display',
                          'organizer_user_id', 'status', 'activity_type',
                          'start_time', 'end_time', 'location', 'max_participants',
                          'current_participants', 'cover_image', 'created_at']

        for field in required_fields:
            assert field in activity_detail, f"Missing field: {field}"

    def test_get_forum_discussion_detail_success(self, client, super_admin_token):
        """测试成功获取论坛讨论详情"""
        response = client.get('/api/admin/content/detail/forum/1',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        assert 'data' in data
        discussion_detail = data['data']

        # 验证论坛讨论特有字段
        required_fields = ['id', 'title', 'content', 'author_display',
                          'author_user_id', 'status', 'tags', 'view_count',
                          'like_count', 'comment_count', 'created_at']

        for field in required_fields:
            assert field in discussion_detail, f"Missing field: {field}"

    def test_get_content_detail_not_found(self, client, super_admin_token):
        """测试获取不存在的内容详情"""
        test_cases = [
            ('science', 99999, '科普文章不存在'),
            ('activity', 99999, '活动不存在'),
            ('forum', 99999, '论坛讨论不存在')
        ]

        for module, content_id, expected_message in test_cases:
            response = client.get(f'/api/admin/content/detail/{module}/{content_id}',
                                headers=get_auth_headers(super_admin_token))
            assert_error_response(response, 404, expected_message)

    def test_get_content_detail_invalid_module(self, client, super_admin_token):
        """测试获取无效模块的内容详情"""
        response = client.get('/api/admin/content/detail/invalid_module/1',
                            headers=get_auth_headers(super_admin_token))

        assert_error_response(response, 400, '未知的内容模块')

    def test_get_content_detail_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权查看详情"""
        test_modules = ['science', 'activity', 'forum']

        for token in [regular_admin_token, user_token]:
            for module in test_modules:
                response = client.get(f'/api/admin/content/detail/{module}/1',
                                    headers=get_auth_headers(token))
                assert_permission_denied(response)

    def test_get_content_detail_missing_auth(self, client):
        """测试未认证访问内容详情"""
        response = client.get('/api/admin/content/detail/science/1')
        assert response.status_code == 401

    def test_get_content_detail_invalid_content_id(self, client, super_admin_token):
        """测试无效的内容ID"""
        invalid_ids = ['abc', -1, 0]

        for content_id in invalid_ids:
            response = client.get(f'/api/admin/content/detail/science/{content_id}',
                                headers=get_auth_headers(super_admin_token))
            # 应该返回404或400错误
            assert response.status_code in [404, 400]

class TestContentDataExport:
    """内容数据导出接口测试"""

    def test_export_content_csv_format(self, client, super_admin_token):
        """测试CSV格式导出内容数据"""
        export_data = {
            'modules': ['science', 'activity', 'forum'],
            'status': 'published',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'format': 'csv'
        }

        response = client.post('/api/admin/content/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 200
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition
        assert content_disposition.endswith('.csv')

    def test_export_content_json_format(self, client, super_admin_token):
        """测试JSON格式导出内容数据"""
        export_data = {
            'modules': ['science'],
            'status': 'pending',
            'format': 'json'
        }

        response = client.post('/api/admin/content/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 200
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition
        assert content_disposition.endswith('.json')

    def test_export_specific_modules(self, client, super_admin_token):
        """测试导出特定模块的数据"""
        test_cases = [
            {'modules': ['science'], 'name': '科普文章'},
            {'modules': ['activity'], 'name': '活动'},
            {'modules': ['forum'], 'name': '论坛讨论'},
            {'modules': ['science', 'activity'], 'name': '科普文章和活动'}
        ]

        for export_config in test_cases:
            export_data = {
                'modules': export_config['modules'],
                'format': 'csv'
            }

            response = client.post('/api/admin/content/export',
                                 headers=get_auth_headers(super_admin_token),
                                 data=json.dumps(export_data),
                                 content_type='application/json')

            assert response.status_code == 200

    def test_export_content_with_status_filter(self, client, super_admin_token):
        """测试按状态筛选导出内容"""
        statuses = ['published', 'pending', 'draft', 'rejected']

        for status in statuses:
            export_data = {
                'modules': ['science'],
                'status': status,
                'format': 'csv'
            }

            response = client.post('/api/admin/content/export',
                                 headers=get_auth_headers(super_admin_token),
                                 data=json.dumps(export_data),
                                 content_type='application/json')

            assert response.status_code == 200

    def test_export_content_with_date_range(self, client, super_admin_token):
        """测试按日期范围导出内容"""
        export_data = {
            'modules': ['all'],
            'start_date': '2024-01-01',
            'end_date': '2024-06-30',
            'format': 'csv'
        }

        response = client.post('/api/admin/content/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 200

    def test_export_content_invalid_format(self, client, super_admin_token):
        """测试导出无效格式"""
        export_data = {
            'modules': ['science'],
            'format': 'xml'  # 不支持的格式
        }

        response = client.post('/api/admin/content/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert_error_response(response, 400, '不支持的导出格式')

    def test_export_content_missing_modules(self, client, super_admin_token):
        """测试缺少模块参数的导出"""
        export_data = {
            'format': 'csv'
            # 缺少 modules 参数
        }

        response = client.post('/api/admin/content/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        # 应该使用默认值 ['science', 'activity', 'forum']
        assert response.status_code == 200

    def test_export_content_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权导出"""
        export_data = {
            'modules': ['science'],
            'format': 'csv'
        }

        for token in [regular_admin_token, user_token]:
            response = client.post('/api/admin/content/export',
                                 headers=get_auth_headers(token),
                                 data=json.dumps(export_data),
                                 content_type='application/json')
            assert_permission_denied(response)

    def test_export_content_unauthorized(self, client):
        """测试未授权导出"""
        export_data = {
            'modules': ['science'],
            'format': 'csv'
        }

        response = client.post('/api/admin/content/export',
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 401

class TestUserDisplayManagement:
    """用户显示信息管理接口测试"""

    def test_update_user_displays_success(self, client, super_admin_token):
        """测试成功更新用户显示信息"""
        response = client.post('/api/admin/content/update-user-displays',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps({}),
                             content_type='application/json')

        data = assert_success_response(response)
        assert 'data' in data
        result = data['data']

        # 验证返回字段
        assert 'total_updated' in result
        assert 'updates_by_type' in result
        assert 'update_time' in result

        # 验证数据类型
        assert isinstance(result['total_updated'], int)
        assert isinstance(result['updates_by_type'], dict)

    def test_update_user_displays_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权更新用户显示信息"""
        for token in [regular_admin_token, user_token]:
            response = client.post('/api/admin/content/update-user-displays',
                                 headers=get_auth_headers(token),
                                 data=json.dumps({}),
                                 content_type='application/json')
            assert_permission_denied(response)

    def test_update_user_displays_unauthorized(self, client):
        """测试未授权访问"""
        response = client.post('/api/admin/content/update-user-displays',
                             data=json.dumps({}),
                             content_type='application/json')

        assert response.status_code == 401

class TestContentManagementStatistics:
    """内容管理统计接口测试"""

    def test_get_content_statistics_success(self, client, super_admin_token):
        """测试成功获取内容管理统计数据"""
        response = client.get('/api/admin/content/statistics',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        assert 'data' in data
        stats = data['data']

        # 验证科普文章统计
        assert 'science_articles' in stats
        science_stats = stats['science_articles']
        required_science_fields = ['total', 'published', 'draft', 'pending', 'rejected', 'total_views', 'total_likes']
        for field in required_science_fields:
            assert field in science_stats

        # 验证活动统计
        assert 'activities' in stats
        activity_stats = stats['activities']
        required_activity_fields = ['total', 'published', 'draft', 'ongoing', 'completed', 'cancelled', 'total_participants']
        for field in required_activity_fields:
            assert field in activity_stats

        # 验证论坛讨论统计
        assert 'forum_discussions' in stats
        forum_stats = stats['forum_discussions']
        required_forum_fields = ['total', 'approved', 'pending', 'rejected', 'total_views', 'total_likes']
        for field in required_forum_fields:
            assert field in forum_stats

        # 验证总体统计
        assert 'summary' in stats
        summary = stats['summary']
        required_summary_fields = ['total_content', 'pending_review', 'total_views', 'total_engagement']
        for field in required_summary_fields:
            assert field in summary

    def test_content_statistics_data_integrity(self, client, super_admin_token):
        """测试内容统计数据完整性"""
        response = client.get('/api/admin/content/statistics',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        stats = data['data']

        # 验证数据逻辑一致性
        science_total = stats['science_articles']['total']
        science_sum = (stats['science_articles']['published'] +
                      stats['science_articles']['draft'] +
                      stats['science_articles']['pending'] +
                      stats['science_articles']['rejected'])
        assert science_total == science_sum, "科普文章统计数据不一致"

        # 验证总体统计计算正确性
        summary_total = stats['summary']['total_content']
        calculated_total = (stats['science_articles']['total'] +
                           stats['activities']['total'] +
                           stats['forum_discussions']['total'])
        assert summary_total == calculated_total, "总体内容统计计算错误"

    def test_content_statistics_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权查看统计数据"""
        for token in [regular_admin_token, user_token]:
            response = client.get('/api/admin/content/statistics',
                                headers=get_auth_headers(token))
            assert_permission_denied(response)

    def test_content_statistics_unauthorized(self, client):
        """测试未授权访问统计数据"""
        response = client.get('/api/admin/content/statistics')
        assert response.status_code == 401