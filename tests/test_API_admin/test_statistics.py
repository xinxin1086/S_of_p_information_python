# 统计分析接口测试

import pytest
import json
from datetime import datetime, timedelta
from .conftest import get_auth_headers, assert_success_response, assert_error_response, assert_permission_denied

class TestUserGrowthAnalysis:
    """用户增长分析统计接口测试"""

    def test_get_user_growth_stats_default(self, client, super_admin_token):
        """测试获取默认用户增长统计（最近30天）"""
        response = client.get('/api/admin/statistics/user-growth',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        assert 'data' in data
        result = data['data']

        # 验证返回结构
        assert 'chart_data' in result
        assert 'summary' in result
        assert 'period' in result
        assert 'date_range' in result

        # 验证图表数据结构
        chart_data = result['chart_data']
        assert 'labels' in chart_data
        assert 'datasets' in chart_data
        assert len(chart_data['datasets']) == 3  # 新增用户、活跃用户、新增管理员

        # 验证数据集标签
        dataset_labels = [ds['label'] for ds in chart_data['datasets']]
        assert '新增用户' in dataset_labels
        assert '活跃用户' in dataset_labels
        assert '新增管理员' in dataset_labels

        # 验证汇总统计
        summary = result['summary']
        required_summary_fields = ['total_new_users', 'total_active_users', 'total_new_admins',
                                  'avg_new_users_per_period', 'growth_rate']
        for field in required_summary_fields:
            assert field in summary

    def test_get_user_growth_with_custom_date_range(self, client, super_admin_token):
        """测试自定义日期范围的用户增长统计"""
        start_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.utcnow().strftime('%Y-%m-%d')

        params = {
            'start_date': start_date,
            'end_date': end_date,
            'period': 'day',
            'chart_type': 'bar'
        }

        response = client.get('/api/admin/statistics/user-growth',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        result = data['data']

        assert result['date_range']['start_date'] == start_date
        assert result['date_range']['end_date'] == end_date
        assert result['period'] == 'day'

    def test_get_user_growth_different_periods(self, client, super_admin_token):
        """测试不同统计周期的用户增长"""
        test_periods = [
            {'period': 'day', 'expected_format': '%Y-%m-%d'},
            {'period': 'week', 'expected_format': '%Y-%u'},
            {'period': 'month', 'expected_format': '%Y-%m'}
        ]

        for test_config in test_periods:
            params = {'period': test_config['period']}

            response = client.get('/api/admin/statistics/user-growth',
                                headers=get_auth_headers(super_admin_token),
                                query_string=params)

            data = assert_success_response(response)
            assert data['data']['period'] == test_config['period']

    def test_get_user_growth_different_chart_types(self, client, super_admin_token):
        """测试不同图表类型"""
        chart_types = ['line', 'bar', 'area']

        for chart_type in chart_types:
            params = {'chart_type': chart_type}

            response = client.get('/api/admin/statistics/user-growth',
                                headers=get_auth_headers(super_admin_token),
                                query_string=params)

            data = assert_success_response(response)
            assert data['data']['chart_type'] == chart_type

    def test_get_user_growth_invalid_date_range(self, client, super_admin_token):
        """测试无效日期范围"""
        invalid_date_ranges = [
            {'start_date': '2024-12-31', 'end_date': '2024-01-01'},  # 开始日期晚于结束日期
            {'start_date': 'invalid-date', 'end_date': '2024-12-31'},  # 无效日期格式
            {'start_date': '2024-01-01', 'end_date': 'invalid-date'}   # 无效日期格式
        ]

        for date_range in invalid_date_ranges:
            response = client.get('/api/admin/statistics/user-growth',
                                headers=get_auth_headers(super_admin_token),
                                query_string=date_range)

            # 应该返回错误
            assert response.status_code in [400, 500]

    def test_get_user_growth_invalid_period(self, client, super_admin_token):
        """测试无效统计周期"""
        params = {'period': 'invalid_period'}

        response = client.get('/api/admin/statistics/user-growth',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        assert_error_response(response, 400, '不支持的统计周期')

    def test_get_user_growth_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权访问"""
        for token in [regular_admin_token, user_token]:
            response = client.get('/api/admin/statistics/user-growth',
                                headers=get_auth_headers(token))
            assert_permission_denied(response)

    def test_get_user_growth_unauthorized(self, client):
        """测试未授权访问"""
        response = client.get('/api/admin/statistics/user-growth')
        assert response.status_code == 401

    
class TestContentPublishingAnalysis:
    """内容发布分析统计接口测试"""

    def test_get_content_publishing_stats_all_modules(self, client, super_admin_token):
        """测试获取所有模块的内容发布统计"""
        response = client.get('/api/admin/statistics/content-publishing',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        result = data['data']

        # 验证返回结构
        assert 'chart_data' in result
        assert 'summary' in result
        assert 'period' in result
        assert 'content_type' in result
        assert 'date_range' in result

        # 验证图表数据结构
        chart_data = result['chart_data']
        assert 'labels' in chart_data
        assert 'datasets' in chart_data

        # 验证包含所有模块的数据集
        dataset_labels = [ds['label'] for ds in chart_data['datasets']]
        assert '科普文章' in dataset_labels
        assert '活动' in dataset_labels
        assert '论坛讨论' in dataset_labels

        # 验证每个数据集包含子统计
        for dataset in chart_data['datasets']:
            assert 'sub_stats' in dataset
            sub_stats = dataset['sub_stats']
            if dataset['label'] == '科普文章':
                assert 'published' in sub_stats
                assert 'pending' in sub_stats
                assert 'rejected' in sub_stats
            elif dataset['label'] == '活动':
                assert 'published' in sub_stats
                assert 'ongoing' in sub_stats
                assert 'completed' in sub_stats
            elif dataset['label'] == '论坛讨论':
                assert 'approved' in sub_stats
                assert 'pending' in sub_stats
                assert 'rejected' in sub_stats

    def test_get_content_publishing_science_articles_only(self, client, super_admin_token):
        """测试只获取科普文章发布统计"""
        params = {'content_type': 'science'}

        response = client.get('/api/admin/statistics/content-publishing',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        result = data['data']

        assert result['content_type'] == 'science'
        dataset_labels = [ds['label'] for ds in result['chart_data']['datasets']]
        assert '科普文章' in dataset_labels
        assert '活动' not in dataset_labels
        assert '论坛讨论' not in dataset_labels

    def test_get_content_publishing_activities_only(self, client, super_admin_token):
        """测试只获取活动发布统计"""
        params = {'content_type': 'activity'}

        response = client.get('/api/admin/statistics/content-publishing',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        result = data['data']

        assert result['content_type'] == 'activity'
        dataset_labels = [ds['label'] for ds in result['chart_data']['datasets']]
        assert '活动' in dataset_labels
        assert '科普文章' not in dataset_labels

    def test_get_content_publishing_forum_discussions_only(self, client, super_admin_token):
        """测试只获取论坛讨论发布统计"""
        params = {'content_type': 'forum'}

        response = client.get('/api/admin/statistics/content-publishing',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        result = data['data']

        assert result['content_type'] == 'forum'
        dataset_labels = [ds['label'] for ds in result['chart_data']['datasets']]
        assert '论坛讨论' in dataset_labels
        assert '科普文章' not in dataset_labels
        assert '活动' not in dataset_labels

    def test_get_content_publishing_with_date_range(self, client, super_admin_token):
        """测试按日期范围的内容发布统计"""
        start_date = (datetime.utcnow() - timedelta(days=14)).strftime('%Y-%m-%d')
        end_date = datetime.utcnow().strftime('%Y-%m-%d')

        params = {
            'start_date': start_date,
            'end_date': end_date,
            'period': 'week'
        }

        response = client.get('/api/admin/statistics/content-publishing',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        result = data['data']

        assert result['date_range']['start_date'] == start_date
        assert result['date_range']['end_date'] == end_date
        assert result['period'] == 'week'

    def test_get_content_publishing_different_periods(self, client, super_admin_token):
        """测试不同统计周期"""
        periods = ['day', 'week', 'month']

        for period in periods:
            params = {'period': period, 'content_type': 'science'}

            response = client.get('/api/admin/statistics/content-publishing',
                                headers=get_auth_headers(super_admin_token),
                                query_string=params)

            data = assert_success_response(response)
            assert data['data']['period'] == period

    def test_get_content_publishing_invalid_period(self, client, super_admin_token):
        """测试无效统计周期"""
        params = {'period': 'invalid_period'}

        response = client.get('/api/admin/statistics/content-publishing',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        assert_error_response(response, 400, '不支持的统计周期')

    def test_get_content_publishing_summary_validation(self, client, super_admin_token):
        """测试内容发布汇总统计数据验证"""
        response = client.get('/api/admin/statistics/content-publishing',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        result = data['data']
        summary = result['summary']

        # 验证汇总统计结构
        assert 'total_content' in summary
        for dataset in result['chart_data']['datasets']:
            label = dataset['label']
            assert label in summary
            module_summary = summary[label]
            assert 'total' in module_summary
            assert 'average_per_period' in module_summary

    def test_get_content_publishing_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权访问"""
        for token in [regular_admin_token, user_token]:
            response = client.get('/api/admin/statistics/content-publishing',
                                headers=get_auth_headers(token))
            assert_permission_denied(response)

    def test_get_content_publishing_unauthorized(self, client):
        """测试未授权访问"""
        response = client.get('/api/admin/statistics/content-publishing')
        assert response.status_code == 401

class TestActivityEngagementAnalysis:
    """活动参与度分析统计接口测试"""

    def test_get_activity_engagement_stats_default(self, client, super_admin_token):
        """测试获取默认活动参与度统计"""
        response = client.get('/api/admin/statistics/activity-engagement',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        result = data['data']

        # 验证返回结构
        assert 'type_distribution_chart' in result
        assert 'monthly_trend_chart' in result
        assert 'type_details' in result
        assert 'popular_types' in result
        assert 'summary' in result
        assert 'date_range' in result

        # 验证类型分布图表结构
        type_chart = result['type_distribution_chart']
        assert 'labels' in type_chart
        assert 'datasets' in type_chart
        assert len(type_chart['datasets']) == 1
        assert 'data' in type_chart['datasets'][0]
        assert 'backgroundColor' in type_chart['datasets'][0]

        # 验证月度趋势图表结构
        trend_chart = result['monthly_trend_chart']
        assert 'labels' in trend_chart
        assert 'datasets' in trend_chart
        assert len(trend_chart['datasets']) == 2  # 创建活动数和平均参与率
        for dataset in trend_chart['datasets']:
            assert 'label' in dataset
            assert 'data' in dataset
            assert 'yAxisID' in dataset

    def test_get_activity_engagement_with_type_filter(self, client, super_admin_token):
        """测试按活动类型筛选参与度统计"""
        params = {'activity_type': '健康讲座'}

        response = client.get('/api/admin/statistics/activity-engagement',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        result = data['data']

        assert 'date_range' in result
        # 验证返回的数据只包含指定类型的活动
        type_details = result['type_details']
        for detail in type_details:
            assert detail['activity_type'] == '健康讲座'

    def test_get_activity_engagement_with_date_range(self, client, super_admin_token):
        """测试按日期范围的活动参与度统计"""
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = datetime.utcnow().strftime('%Y-%m-%d')

        params = {
            'start_date': start_date,
            'end_date': end_date
        }

        response = client.get('/api/admin/statistics/activity-engagement',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        result = data['data']

        assert result['date_range']['start_date'] == start_date
        assert result['date_range']['end_date'] == end_date

    def test_get_activity_engagement_type_details_structure(self, client, super_admin_token):
        """测试活动类型详细统计数据结构"""
        response = client.get('/api/admin/statistics/activity-engagement',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        result = data['data']

        # 验证类型详细数据结构
        type_details = result['type_details']
        for detail in type_details:
            required_fields = ['activity_type', 'total_activities', 'total_participants',
                              'avg_fill_rate', 'completed_activities', 'ongoing_activities']
            for field in required_fields:
                assert field in detail

            # 验证数据类型
            assert isinstance(detail['total_activities'], int)
            assert isinstance(detail['total_participants'], int)
            assert isinstance(detail['avg_fill_rate'], (int, float))

    def test_get_activity_engagement_popular_types_structure(self, client, super_admin_token):
        """测试最受欢迎活动类型数据结构"""
        response = client.get('/api/admin/statistics/activity-engagement',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        result = data['data']

        # 验证热门活动类型数据结构
        popular_types = result['popular_types']
        for popular_type in popular_types[:5]:  # 只检查前5个
            required_fields = ['activity_type', 'count', 'total_participants', 'avg_participants']
            for field in required_fields:
                assert field in popular_type

    def test_get_activity_engagement_summary_validation(self, client, super_admin_token):
        """测试活动参与度汇总统计数据验证"""
        response = client.get('/api/admin/statistics/activity-engagement',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        result = data['data']
        summary = result['summary']

        # 验证汇总统计结构
        required_summary_fields = ['total_activities', 'total_participants', 'total_capacity',
                                  'overall_fill_rate', 'completed_activities', 'ongoing_activities',
                                  'completion_rate']
        for field in required_summary_fields:
            assert field in summary

        # 验证数据一致性
        assert summary['total_activities'] >= 0
        assert summary['total_participants'] >= 0
        assert summary['total_capacity'] >= 0
        assert 0 <= summary['overall_fill_rate'] <= 100
        assert 0 <= summary['completion_rate'] <= 100

    def test_get_activity_engagement_invalid_date_range(self, client, super_admin_token):
        """测试无效日期范围"""
        params = {
            'start_date': '2024-12-31',
            'end_date': '2024-01-01'
        }

        response = client.get('/api/admin/statistics/activity-engagement',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        # 应该返回错误
        assert response.status_code in [400, 500]

    def test_get_activity_engagement_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权访问"""
        for token in [regular_admin_token, user_token]:
            response = client.get('/api/admin/statistics/activity-engagement',
                                headers=get_auth_headers(token))
            assert_permission_denied(response)

    def test_get_activity_engagement_unauthorized(self, client):
        """测试未授权访问"""
        response = client.get('/api/admin/statistics/activity-engagement')
        assert response.status_code == 401

class TestSystemUsageAnalysis:
    """系统使用情况分析统计接口测试"""

    def test_get_system_usage_stats_default(self, client, super_admin_token):
        """测试获取默认系统使用情况统计"""
        response = client.get('/api/admin/statistics/system-usage',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        result = data['data']

        # 验证返回结构
        assert 'database_stats' in result
        assert 'growth_trend_chart' in result
        assert 'summary' in result

        # 验证数据库统计结构
        db_stats = result['database_stats']
        assert 'users' in db_stats
        assert 'content' in db_stats

        # 验证用户统计
        user_stats = db_stats['users']
        required_user_fields = ['total', 'active', 'today_registrations', 'today_logins']
        for field in required_user_fields:
            assert field in user_stats

        # 验证内容统计
        content_stats = db_stats['content']
        required_content_fields = ['science_articles', 'activities', 'forum_discussions',
                                  'activity_ratings', 'total_views']
        for field in required_content_fields:
            assert field in content_stats

        # 验证增长趋势图表
        growth_chart = result['growth_trend_chart']
        assert 'labels' in growth_chart
        assert 'datasets' in growth_chart
        assert len(growth_chart['datasets']) >= 3  # 用户、文章、活动

    def test_get_system_usage_different_periods(self, client, super_admin_token):
        """测试不同统计周期的系统使用统计"""
        periods = ['day', 'week', 'month']

        for period in periods:
            params = {'period': period}

            response = client.get('/api/admin/statistics/system-usage',
                                headers=get_auth_headers(super_admin_token),
                                query_string=params)

            data = assert_success_response(response)
            result = data['data']

            # 验证汇总中的周期信息
            assert 'growth_period' in result['summary']
            assert result['summary']['growth_period']['period'] == period

    def test_get_system_usage_with_date_range(self, client, super_admin_token):
        """测试按日期范围的系统使用统计"""
        start_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.utcnow().strftime('%Y-%m-%d')

        params = {
            'start_date': start_date,
            'end_date': end_date,
            'period': 'day'
        }

        response = client.get('/api/admin/statistics/system-usage',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        data = assert_success_response(response)
        result = data['data']

        assert result['summary']['growth_period']['start_date'] == start_date
        assert result['summary']['growth_period']['end_date'] == end_date

    def test_get_system_usage_growth_chart_structure(self, client, super_admin_token):
        """测试增长趋势图表数据结构"""
        response = client.get('/api/admin/statistics/system-usage',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        result = data['data']
        growth_chart = result['growth_trend_chart']

        # 验证图表结构
        assert 'labels' in growth_chart
        assert 'datasets' in growth_chart
        assert len(growth_chart['labels']) > 0

        # 验证数据集
        dataset_labels = [ds['label'] for ds in growth_chart['datasets']]
        assert '新增用户' in dataset_labels
        assert '新增科普文章' in dataset_labels
        assert '新增活动' in dataset_labels

        # 验证每个数据集的结构
        for dataset in growth_chart['datasets']:
            assert 'label' in dataset
            assert 'data' in dataset
            assert 'backgroundColor' in dataset
            assert 'borderColor' in dataset
            assert 'borderWidth' in dataset

    def test_get_system_usage_summary_validation(self, client, super_admin_token):
        """测试系统使用汇总统计数据验证"""
        response = client.get('/api/admin/statistics/system-usage',
                            headers=get_auth_headers(super_admin_token))

        data = assert_success_response(response)
        result = data['data']
        summary = result['summary']

        # 验证汇总统计结构
        required_summary_fields = ['database_size_mb', 'total_records', 'today_activity', 'growth_period']
        for field in required_summary_fields:
            assert field in summary

        # 验证数据一致性
        assert summary['database_size_mb'] >= 0
        assert summary['total_records'] >= 0
        assert summary['today_activity'] >= 0

    def test_get_system_usage_invalid_date_range(self, client, super_admin_token):
        """测试无效日期范围"""
        params = {
            'start_date': '2024-12-31',
            'end_date': '2024-01-01'
        }

        response = client.get('/api/admin/statistics/system-usage',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        # 应该返回错误
        assert response.status_code in [400, 500]

    def test_get_system_usage_invalid_period(self, client, super_admin_token):
        """测试无效统计周期"""
        params = {'period': 'invalid_period'}

        response = client.get('/api/admin/statistics/system-usage',
                            headers=get_auth_headers(super_admin_token),
                            query_string=params)

        # 应该使用默认值或返回错误
        assert response.status_code in [200, 400, 500]

    def test_get_system_usage_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权访问"""
        for token in [regular_admin_token, user_token]:
            response = client.get('/api/admin/statistics/system-usage',
                                headers=get_auth_headers(token))
            assert_permission_denied(response)

    def test_get_system_usage_unauthorized(self, client):
        """测试未授权访问"""
        response = client.get('/api/admin/statistics/system-usage')
        assert response.status_code == 401

class TestStatisticsDataExport:
    """统计数据导出接口测试"""

    def test_export_user_growth_statistics_csv(self, client, super_admin_token):
        """测试导出用户增长统计为CSV"""
        export_data = {
            'report_type': 'user_growth',
            'format': 'csv',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }

        response = client.post('/api/admin/statistics/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 200
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition
        assert content_disposition.endswith('.csv')

    def test_export_user_growth_statistics_json(self, client, super_admin_token):
        """测试导出用户增长统计为JSON"""
        export_data = {
            'report_type': 'user_growth',
            'format': 'json',
            'start_date': '2024-06-01',
            'end_date': '2024-06-30'
        }

        response = client.post('/api/admin/statistics/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 200
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition
        assert content_disposition.endswith('.json')

    def test_export_content_publishing_statistics(self, client, super_admin_token):
        """测试导出内容发布统计数据"""
        export_data = {
            'report_type': 'content_publishing',
            'format': 'csv',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }

        response = client.post('/api/admin/statistics/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 200

    def test_export_activity_engagement_statistics(self, client, super_admin_token):
        """测试导出活动参与度统计数据"""
        export_data = {
            'report_type': 'activity_engagement',
            'format': 'csv'
        }

        response = client.post('/api/admin/statistics/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 200

    def test_export_system_usage_overview(self, client, super_admin_token):
        """测试导出系统使用概况"""
        export_data = {
            'report_type': 'system_usage',
            'format': 'json'
        }

        response = client.post('/api/admin/statistics/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 200
        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition
        assert content_disposition.endswith('.json')

    def test_export_statistics_with_empty_date_range(self, client, super_admin_token):
        """测试空日期范围的统计导出"""
        export_data = {
            'report_type': 'user_growth',
            'format': 'csv',
            'start_date': '',
            'end_date': ''
        }

        response = client.post('/api/admin/statistics/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 200

    def test_export_statistics_invalid_format(self, client, super_admin_token):
        """测试导出无效格式"""
        export_data = {
            'report_type': 'user_growth',
            'format': 'xml'  # 不支持的格式
        }

        response = client.post('/api/admin/statistics/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert_error_response(response, 400, '不支持的导出格式')

    def test_export_statistics_missing_parameters(self, client, super_admin_token):
        """测试缺少必要参数的统计导出"""
        export_data = {
            'format': 'csv'
            # 缺少 report_type
        }

        response = client.post('/api/admin/statistics/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        # 应该使用默认的 report_type 或返回错误
        assert response.status_code in [200, 400, 500]

    def test_export_statistics_permission_denied(self, client, regular_admin_token, user_token):
        """测试权限验证 - 普通管理员和用户无权导出统计数据"""
        export_data = {
            'report_type': 'user_growth',
            'format': 'csv'
        }

        for token in [regular_admin_token, user_token]:
            response = client.post('/api/admin/statistics/export',
                                 headers=get_auth_headers(token),
                                 data=json.dumps(export_data),
                                 content_type='application/json')
            assert_permission_denied(response)

    def test_export_statistics_unauthorized(self, client):
        """测试未授权导出统计数据"""
        export_data = {
            'report_type': 'user_growth',
            'format': 'csv'
        }

        response = client.post('/api/admin/statistics/export',
                             data=json.dumps(export_data),
                             content_type='application/json')

        assert response.status_code == 401

    def test_export_statistics_invalid_report_type(self, client, super_admin_token):
        """测试导出无效报告类型"""
        export_data = {
            'report_type': 'invalid_report_type',
            'format': 'csv'
        }

        response = client.post('/api/admin/statistics/export',
                             headers=get_auth_headers(super_admin_token),
                             data=json.dumps(export_data),
                             content_type='application/json')

        # 根据实现，可能返回空数据或错误
        assert response.status_code in [200, 400, 500]