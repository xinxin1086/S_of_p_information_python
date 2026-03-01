
from flask import Blueprint, request, jsonify, Response
from components import db
from API_admin.common.utils import super_admin_required, log_admin_operation, validate_date_range, export_to_csv
from datetime import datetime, timedelta
from sqlalchemy import text
import json

bp_admin_stats = Blueprint('admin_stats', __name__, url_prefix='/api/admin/statistics')

@bp_admin_stats.route('/user-growth', methods=['GET'])
@super_admin_required
def get_user_growth_stats(current_user):
    
    try:
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        period = request.args.get('period', 'day')
        chart_type = request.args.get('chart_type', 'line')

        is_valid, error_msg = validate_date_range(start_date, end_date)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 400

        if not start_date:
            end_date_dt = datetime.utcnow()
            start_date_dt = end_date_dt - timedelta(days=30)
            start_date = start_date_dt.strftime('%Y-%m-%d')
            end_date = end_date_dt.strftime('%Y-%m-%d')

        log_admin_operation(
            current_user,
            'VIEW',
            'user_growth_statistics',
            details={
                'start_date': start_date,
                'end_date': end_date,
                'period': period,
                'chart_type': chart_type
            }
        )

        if period == 'day':
            date_format = '%Y-%m-%d'
            group_by = 'DATE(created_at)'
        elif period == 'week':
            date_format = '%Y-%u'
            group_by = 'YEARWEEK(created_at)'
        elif period == 'month':
            date_format = '%Y-%m'
            group_by = 'DATE_FORMAT(created_at, "%Y-%m")'
        else:
            return jsonify({
                'success': False,
                'message': '不支持的统计周期，请使用 day/week/month',
                'data': None
            }), 400

        user_query = text(f)

        user_stats = db.session.execute(user_query, {
            'start_date': start_date,
            'end_date': end_date + ' 23:59:59'
        }).fetchall()

        admin_query = text(f)

        admin_stats = db.session.execute(admin_query, {
            'start_date': start_date,
            'end_date': end_date + ' 23:59:59'
        }).fetchall()

        chart_data = {
            'labels': [],
            'datasets': [
                {
                    'label': '新增用户',
                    'data': [],
                    'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'borderWidth': 2
                },
                {
                    'label': '活跃用户',
                    'data': [],
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'borderWidth': 2
                },
                {
                    'label': '新增管理员',
                    'data': [],
                    'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                    'borderColor': 'rgba(255, 99, 132, 1)',
                    'borderWidth': 2
                }
            ]
        }

        user_dict = {str(row.period): {'new_users': row.new_users, 'active_users': row.active_users} for row in user_stats}
        admin_dict = {str(row.period): row.new_admins for row in admin_stats}

        all_periods = sorted(set(user_dict.keys()) | set(admin_dict.keys()))

        for period in all_periods:
            chart_data['labels'].append(period)
            user_data = user_dict.get(period, {'new_users': 0, 'active_users': 0})
            chart_data['datasets'][0]['data'].append(user_data['new_users'])
            chart_data['datasets'][1]['data'].append(user_data['active_users'])
            chart_data['datasets'][2]['data'].append(admin_dict.get(period, 0))

        total_new_users = sum(row.new_users for row in user_stats)
        total_active_users = sum(row.active_users for row in user_stats)
        total_new_admins = sum(row.new_admins for row in admin_stats)

        summary = {
            'total_new_users': total_new_users,
            'total_active_users': total_active_users,
            'total_new_admins': total_new_admins,
            'avg_new_users_per_period': round(total_new_users / len(all_periods), 2) if all_periods else 0,
            'growth_rate': round((total_new_users / total_active_users * 100), 2) if total_active_users > 0 else 0
        }

        return jsonify({
            'success': True,
            'message': '用户增长统计查询成功',
            'data': {
                'chart_data': chart_data,
                'chart_type': chart_type,
                'period': period,
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'summary': summary
            }
        }), 200

    except Exception as e:
        print(f"【用户增长统计异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'用户增长统计查询失败：{str(e)}',
            'data': None
        }), 500

@bp_admin_stats.route('/content-publishing', methods=['GET'])
@super_admin_required
def get_content_publishing_stats(current_user):
    
    try:
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        period = request.args.get('period', 'day')
        content_type = request.args.get('content_type', 'all')

        is_valid, error_msg = validate_date_range(start_date, end_date)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 400

        if not start_date:
            end_date_dt = datetime.utcnow()
            start_date_dt = end_date_dt - timedelta(days=30)
            start_date = start_date_dt.strftime('%Y-%m-%d')
            end_date = end_date_dt.strftime('%Y-%m-%d')

        log_admin_operation(
            current_user,
            'VIEW',
            'content_publishing_statistics',
            details={
                'start_date': start_date,
                'end_date': end_date,
                'period': period,
                'content_type': content_type
            }
        )

        if period == 'day':
            group_by = 'DATE(created_at)'
        elif period == 'week':
            group_by = 'YEARWEEK(created_at)'
        elif period == 'month':
            group_by = 'DATE_FORMAT(created_at, "%Y-%m")'
        else:
            return jsonify({
                'success': False,
                'message': '不支持的统计周期，请使用 day/week/month',
                'data': None
            }), 400

        datasets = []
        all_periods = set()

        if content_type in ['all', 'science']:
            from components.models import ScienceArticle
            science_query = text(f)

            science_stats = db.session.execute(science_query, {
                'start_date': start_date,
                'end_date': end_date + ' 23:59:59'
            }).fetchall()

            science_dict = {str(row.period): row for row in science_stats}
            all_periods.update(science_dict.keys())

            datasets.append({
                'label': '科普文章',
                'data': [],
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'borderColor': 'rgba(255, 99, 132, 1)',
                'borderWidth': 2,
                'sub_stats': {
                    'published': [],
                    'pending': [],
                    'rejected': []
                }
            })

        if content_type in ['all', 'activity']:
            from components.models import Activity
            activity_query = text(f)

            activity_stats = db.session.execute(activity_query, {
                'start_date': start_date,
                'end_date': end_date + ' 23:59:59'
            }).fetchall()

            activity_dict = {str(row.period): row for row in activity_stats}
            all_periods.update(activity_dict.keys())

            datasets.append({
                'label': '活动',
                'data': [],
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 2,
                'sub_stats': {
                    'published': [],
                    'ongoing': [],
                    'completed': []
                }
            })

        if content_type in ['all', 'forum']:
            from components.models import ActivityDiscuss
            forum_query = text(f)

            forum_stats = db.session.execute(forum_query, {
                'start_date': start_date,
                'end_date': end_date + ' 23:59:59'
            }).fetchall()

            forum_dict = {str(row.period): row for row in forum_stats}
            all_periods.update(forum_dict.keys())

            datasets.append({
                'label': '论坛讨论',
                'data': [],
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 2,
                'sub_stats': {
                    'approved': [],
                    'pending': [],
                    'rejected': []
                }
            })

        sorted_periods = sorted(all_periods)

        for i, period in enumerate(sorted_periods):
            for dataset in datasets:
                if dataset['label'] == '科普文章':
                    stats = science_dict.get(period)
                    dataset['data'].append(stats.total if stats else 0)
                    dataset['sub_stats']['published'].append(stats.published if stats else 0)
                    dataset['sub_stats']['pending'].append(stats.pending if stats else 0)
                    dataset['sub_stats']['rejected'].append(stats.rejected if stats else 0)
                elif dataset['label'] == '活动':
                    stats = activity_dict.get(period)
                    dataset['data'].append(stats.total if stats else 0)
                    dataset['sub_stats']['published'].append(stats.published if stats else 0)
                    dataset['sub_stats']['ongoing'].append(stats.ongoing if stats else 0)
                    dataset['sub_stats']['completed'].append(stats.completed if stats else 0)
                elif dataset['label'] == '论坛讨论':
                    stats = forum_dict.get(period)
                    dataset['data'].append(stats.total if stats else 0)
                    dataset['sub_stats']['approved'].append(stats.approved if stats else 0)
                    dataset['sub_stats']['pending'].append(stats.pending if stats else 0)
                    dataset['sub_stats']['rejected'].append(stats.rejected if stats else 0)

        chart_data = {
            'labels': sorted_periods,
            'datasets': datasets
        }

        summary = {}
        total_content = 0

        for dataset in datasets:
            dataset_total = sum(dataset['data'])
            summary[dataset['label']] = {
                'total': dataset_total,
                'average_per_period': round(dataset_total / len(sorted_periods), 2) if sorted_periods else 0
            }
            total_content += dataset_total

        summary['total_content'] = total_content

        return jsonify({
            'success': True,
            'message': '内容发布统计查询成功',
            'data': {
                'chart_data': chart_data,
                'period': period,
                'content_type': content_type,
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'summary': summary
            }
        }), 200

    except Exception as e:
        print(f"【内容发布统计异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'内容发布统计查询失败：{str(e)}',
            'data': None
        }), 500

@bp_admin_stats.route('/activity-engagement', methods=['GET'])
@super_admin_required
def get_activity_engagement_stats(current_user):
    
    try:
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        activity_type = request.args.get('activity_type', '').strip()

        is_valid, error_msg = validate_date_range(start_date, end_date)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 400

        if not start_date:
            end_date_dt = datetime.utcnow()
            start_date_dt = end_date_dt - timedelta(days=30)
            start_date = start_date_dt.strftime('%Y-%m-%d')
            end_date = end_date_dt.strftime('%Y-%m-%d')

        log_admin_operation(
            current_user,
            'VIEW',
            'activity_engagement_statistics',
            details={
                'start_date': start_date,
                'end_date': end_date,
                'activity_type': activity_type
            }
        )

        where_conditions = ["created_at BETWEEN :start_date AND :end_date"]
        params = {'start_date': start_date, 'end_date': end_date + ' 23:59:59'}

        if activity_type:
            where_conditions.append("activity_type = :activity_type")
            params['activity_type'] = activity_type

        where_clause = "WHERE " + " AND ".join(where_conditions)

        engagement_query = text(f)

        engagement_stats = db.session.execute(engagement_query, params).fetchall()

        monthly_trend_query = text(f)

        monthly_trend = db.session.execute(monthly_trend_query, params).fetchall()

        popular_types_query = text(f)

        popular_types = db.session.execute(popular_types_query, params).fetchall()

        type_distribution_data = {
            'labels': [],
            'datasets': [{
                'data': [],
                'backgroundColor': [
                    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                    '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                ]
            }]
        }

        for stat in engagement_stats:
            type_distribution_data['labels'].append(stat.activity_type or '未分类')
            type_distribution_data['datasets'][0]['data'].append(stat.total_activities)

        monthly_trend_data = {
            'labels': [],
            'datasets': [
                {
                    'label': '创建活动数',
                    'data': [],
                    'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'borderWidth': 2,
                    'yAxisID': 'y'
                },
                {
                    'label': '平均参与率(%)',
                    'data': [],
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'borderWidth': 2,
                    'yAxisID': 'y1'
                }
            ]
        }

        for trend in monthly_trend:
            monthly_trend_data['labels'].append(trend.month)
            monthly_trend_data['datasets'][0]['data'].append(trend.activities_created)
            monthly_trend_data['datasets'][1]['data'].append(round(trend.avg_fill_rate or 0, 2))

        total_activities = sum(stat.total_activities for stat in engagement_stats)
        total_participants = sum(stat.total_participants for stat in engagement_stats)
        total_capacity = sum(stat.total_capacity for stat in engagement_stats)
        overall_fill_rate = round((total_participants / total_capacity * 100), 2) if total_capacity > 0 else 0

        summary = {
            'total_activities': total_activities,
            'total_participants': total_participants,
            'total_capacity': total_capacity,
            'overall_fill_rate': overall_fill_rate,
            'completed_activities': sum(stat.completed_activities for stat in engagement_stats),
            'ongoing_activities': sum(stat.ongoing_activities for stat in engagement_stats),
            'completion_rate': round(
                (sum(stat.completed_activities for stat in engagement_stats) / total_activities * 100), 2
            ) if total_activities > 0 else 0
        }

        type_details = []
        for stat in engagement_stats:
            type_details.append({
                'activity_type': stat.activity_type,
                'total_activities': stat.total_activities,
                'total_participants': stat.total_participants,
                'avg_fill_rate': round(stat.avg_fill_rate or 0, 2),
                'completed_activities': stat.completed_activities,
                'ongoing_activities': stat.ongoing_activities
            })

        return jsonify({
            'success': True,
            'message': '活动参与度统计查询成功',
            'data': {
                'type_distribution_chart': type_distribution_data,
                'monthly_trend_chart': monthly_trend_data,
                'type_details': type_details,
                'popular_types': [
                    {
                        'activity_type': t.activity_type,
                        'count': t.count,
                        'total_participants': t.total_participants,
                        'avg_participants': round(t.avg_participants or 0, 2)
                    }
                    for t in popular_types
                ],
                'summary': summary,
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
        }), 200

    except Exception as e:
        print(f"【活动参与度统计异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'活动参与度统计查询失败：{str(e)}',
            'data': None
        }), 500

@bp_admin_stats.route('/system-usage', methods=['GET'])
@super_admin_required
def get_system_usage_stats(current_user):
    
    try:
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        period = request.args.get('period', 'day')

        is_valid, error_msg = validate_date_range(start_date, end_date)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 400

        if not start_date:
            end_date_dt = datetime.utcnow()
            start_date_dt = end_date_dt - timedelta(days=30)
            start_date = start_date_dt.strftime('%Y-%m-%d')
            end_date = end_date_dt.strftime('%Y-%m-%d')

        log_admin_operation(
            current_user,
            'VIEW',
            'system_usage_statistics',
            details={
                'start_date': start_date,
                'end_date': end_date,
                'period': period
            }
        )

        db_stats = {}

        user_stats_query = text()

        user_stats = db.session.execute(user_stats_query).fetchone()
        db_stats['users'] = {
            'total': user_stats.total_users,
            'active': user_stats.active_users,
            'today_registrations': user_stats.today_registrations,
            'today_logins': user_stats.today_logins
        }

        content_stats_query = text()

        content_stats = db.session.execute(content_stats_query).fetchone()
        db_stats['content'] = {
            'science_articles': content_stats.science_articles,
            'activities': content_stats.activities,
            'forum_discussions': content_stats.forum_discussions,
            'activity_ratings': content_stats.activity_ratings,
            'total_views': (content_stats.total_science_views or 0) + (content_stats.total_forum_views or 0)
        }

        if period == 'day':
            date_format = '%Y-%m-%d'
            group_by = 'DATE(created_at)'
        elif period == 'week':
            date_format = '%Y-%u'
            group_by = 'YEARWEEK(created_at)'
        elif period == 'month':
            date_format = '%Y-%m'
            group_by = 'DATE_FORMAT(created_at, "%Y-%m")'

        growth_query = text(f)

        growth_stats = db.session.execute(growth_query, {
            'start_date': start_date,
            'end_date': end_date + ' 23:59:59'
        }).fetchall()

        growth_chart_data = {
            'labels': [str(row.period) for row in growth_stats],
            'datasets': [
                {
                    'label': '新增用户',
                    'data': [row.new_users for row in growth_stats],
                    'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'borderWidth': 2
                },
                {
                    'label': '新增科普文章',
                    'data': [row.new_articles for row in growth_stats],
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'borderWidth': 2
                },
                {
                    'label': '新增活动',
                    'data': [row.new_activities for row in growth_stats],
                    'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                    'borderColor': 'rgba(255, 99, 132, 1)',
                    'borderWidth': 2
                }
            ]
        }

        db_size_query = text()

        db_size_stats = db.session.execute(db_size_query).fetchone()
        db_size = db_size_stats.size_mb if db_size_stats else 0

        summary = {
            'database_size_mb': db_size,
            'total_records': (
                db_stats['users']['total'] +
                db_stats['content']['science_articles'] +
                db_stats['content']['activities'] +
                db_stats['content']['forum_discussions']
            ),
            'today_activity': (
                db_stats['users']['today_registrations'] +
                db_stats['users']['today_logins']
            ),
            'growth_period': {
                'start_date': start_date,
                'end_date': end_date,
                'period': period
            }
        }

        return jsonify({
            'success': True,
            'message': '系统使用情况统计查询成功',
            'data': {
                'database_stats': db_stats,
                'growth_trend_chart': growth_chart_data,
                'summary': summary
            }
        }), 200

    except Exception as e:
        print(f"【系统使用情况统计异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'系统使用情况统计查询失败：{str(e)}',
            'data': None
        }), 500

@bp_admin_stats.route('/export', methods=['POST'])
@super_admin_required
def export_statistics_data(current_user):
    
    try:
        data = request.get_json()
        report_type = data.get('report_type', 'user_growth')
        export_format = data.get('format', 'csv')
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')

        log_admin_operation(
            current_user,
            'EXPORT',
            'statistics_data',
            details={
                'report_type': report_type,
                'format': export_format,
                'start_date': start_date,
                'end_date': end_date
            }
        )

        export_data = []
        filename = f"statistics_{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{export_format}"

        if report_type == 'user_growth':
            query = text()

            results = db.session.execute(query, {
                'start_date': start_date,
                'end_date': end_date + ' 23:59:59' if end_date else ''
            }).fetchall()

            for row in results:
                export_data.append({
                    '日期': row.date,
                    '新增用户': row.new_users,
                    '活跃用户': row.active_users,
                    '增长率': f"{((row.new_users / row.active_users * 100) if row.active_users > 0 else 0):.2f}%"
                })

        elif report_type == 'content_publishing':
            query = text()

            results = db.session.execute(query, {
                'start_date': start_date,
                'end_date': end_date + ' 23:59:59' if end_date else ''
            }).fetchall()

            for row in results:
                export_data.append({
                    '模块': row.module,
                    '日期': row.date,
                    '总发布数': row.total,
                    '已发布': row.published,
                    '发布率': f"{((row.published / row.total * 100) if row.total > 0 else 0):.2f}%"
                })

        elif report_type == 'activity_engagement':
            query = text()

            results = db.session.execute(query, {
                'start_date': start_date,
                'end_date': end_date + ' 23:59:59' if end_date else ''
            }).fetchall()

            for row in results:
                export_data.append({
                    '活动类型': row.activity_type,
                    '活动总数': row.total_activities,
                    '总参与人数': row.total_participants,
                    '总容量': row.total_capacity,
                    '平均参与率': f"{(row.avg_fill_rate or 0):.2f}%"
                })

        elif report_type == 'system_usage':
            export_data = [
                {
                    '统计项目': '用户总数',
                    '数值': db.session.execute(text('SELECT COUNT(*) FROM user_info')).fetchone()[0],
                    '说明': '包括所有注册用户'
                },
                {
                    '统计项目': '科普文章总数',
                    '数值': db.session.execute(text('SELECT COUNT(*) FROM science_articles')).fetchone()[0],
                    '说明': '所有科普文章数量'
                },
                {
                    '统计项目': '活动总数',
                    '数值': db.session.execute(text('SELECT COUNT(*) FROM activities')).fetchone()[0],
                    '说明': '所有活动数量'
                },
                {
                    '统计项目': '论坛讨论总数',
                    '数值': db.session.execute(text('SELECT COUNT(*) FROM activity_discuss')).fetchone()[0],
                    '说明': '所有论坛讨论数量'
                }
            ]

        if export_format == 'csv':
            headers = list(export_data[0].keys()) if export_data else []
            csv_data = [[item[key] for key in headers] for item in export_data]
            return export_to_csv(csv_data, filename, headers)

        elif export_format == 'json':
            response = Response(
                json.dumps(export_data, ensure_ascii=False, indent=2),
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename={filename}'}
            )
            return response

        else:
            return jsonify({
                'success': False,
                'message': '不支持的导出格式',
                'data': None
            }), 400

    except Exception as e:
        print(f"【统计数据导出异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'统计数据导出失败：{str(e)}',
            'data': None
        }), 500