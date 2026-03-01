
from functools import wraps
from flask import request, jsonify, Response
from components import token_required, db
from components.models import Admin, User, ScienceArticle, Activity, ActivityDiscuss
from components.permissions import admin_required
from datetime import datetime, timedelta
import csv
import io
import json
import hashlib
import os
from sqlalchemy import text

def super_admin_required(f):
    
    @wraps(f)
    @token_required
    def decorated_function(current_user, *args, **kwargs):
        if not hasattr(current_user, 'role') or current_user.role != 'SUPER_ADMIN':
            return jsonify({
                'success': False,
                'message': '权限不足，需要超级管理员权限',
                'data': None
            }), 403
        return f(current_user, *args, **kwargs)
    return decorated_function

def log_admin_operation(current_user, operation_type, target_table, target_id=None, details=None):
    
    try:
        log_data = {
            'admin_id': current_user.id,
            'admin_username': current_user.username,
            'operation_type': operation_type,
            'target_table': target_table,
            'target_id': target_id,
            'details': details,
            'ip_address': request.environ.get('REMOTE_ADDR', 'unknown'),
            'user_agent': request.headers.get('User-Agent', 'unknown'),
            'timestamp': datetime.utcnow().isoformat()
        }

        print(f"【管理员操作日志】{json.dumps(log_data, ensure_ascii=False)}")


    except Exception as e:
        print(f"【日志记录异常】错误: {str(e)}")

def export_to_csv(data, filename, headers=None):
    
    output = io.StringIO()
    writer = csv.writer(output)

    if headers:
        writer.writerow(headers)

    for row in data:
        if isinstance(row, dict):
            writer.writerow(row.values())
        else:
            writer.writerow(row)

    output.seek(0)

    response = Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

    return response

def validate_date_range(start_date, end_date):
    
    try:
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            if start_dt > datetime.utcnow():
                return False, '开始日期不能晚于当前日期'

        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            if start_date and start_dt > end_dt:
                return False, '开始日期不能晚于结束日期'

        if start_date and end_date:
            days_diff = (end_dt - start_dt).days
            if days_diff > 365:
                return False, '查询时间范围不能超过1年'

        return True, None

    except ValueError:
        return False, '日期格式不正确，请使用YYYY-MM-DD格式'

def encrypt_sensitive_data(data):
    
    try:
        return hashlib.sha256(data.encode()).hexdigest()
    except Exception as e:
        print(f"【数据加密异常】错误: {str(e)}")
        return None

def get_cross_module_pending_content():
    
    try:
        stats = {}

        science_pending = ScienceArticle.query.filter_by(status='pending').count()
        stats['science_articles'] = {
            'pending_count': science_pending,
            'table_name': 'science_articles'
        }

        activity_pending = Activity.query.filter_by(status='pending').count()
        stats['activities'] = {
            'pending_count': activity_pending,
            'table_name': 'activities'
        }

        try:
            forum_pending = ActivityDiscuss.query.filter_by(status='pending').count()
            stats['forum_discussions'] = {
                'pending_count': forum_pending,
                'table_name': 'activity_discuss'
            }
        except:
            stats['forum_discussions'] = {
                'pending_count': 0,
                'table_name': 'activity_discuss',
                'note': '论坛模块未找到或无待审核数据'
            }

        stats['total_pending'] = sum(item['pending_count'] for item in stats.values() if 'pending_count' in item)

        return stats

    except Exception as e:
        print(f"【跨模块内容查询异常】错误: {str(e)}")
        return {
            'science_articles': {'pending_count': 0},
            'activities': {'pending_count': 0},
            'forum_discussions': {'pending_count': 0},
            'total_pending': 0,
            'error': str(e)
        }

def batch_update_user_display():
    
    try:
        from components.models import ScienceArticle, Activity, ActivityDiscuss, ActivityDiscussComment, ActivityRating

        updates = {}
        total_updated = 0

        science_result = db.session.execute(text())
        updates['science_articles'] = science_result.rowcount
        total_updated += science_result.rowcount

        activity_result = db.session.execute(text())
        updates['activities'] = activity_result.rowcount
        total_updated += activity_result.rowcount

        discuss_result = db.session.execute(text())
        updates['discussions'] = discuss_result.rowcount
        total_updated += discuss_result.rowcount

        db.session.commit()

        return {
            'success': True,
            'total_updated': total_updated,
            'updates_by_type': updates
        }

    except Exception as e:
        db.session.rollback()
        print(f"【批量更新用户显示异常】错误: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def check_system_security():
    
    security_status = {
        'overall_status': 'secure',
        'checks': {}
    }

    try:
        admin_with_default_pwd = Admin.query.filter_by(password_hash='5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8').count()
        if admin_with_default_pwd > 0:
            security_status['checks']['default_password'] = {
                'status': 'critical',
                'message': f'发现{admin_with_default_pwd}个管理员使用默认密码'
            }
            security_status['overall_status'] = 'critical'
        else:
            security_status['checks']['default_password'] = {
                'status': 'secure',
                'message': '未发现使用默认密码的管理员'
            }

        sensitive_files = ['config.py', '.env']
        file_permission_issues = []

        for file_name in sensitive_files:
            if os.path.exists(file_name):
                file_stat = os.stat(file_name)
                if file_stat.st_mode & 0o077:
                    file_permission_issues.append(file_name)

        if file_permission_issues:
            security_status['checks']['file_permissions'] = {
                'status': 'warning',
                'message': f'敏感文件权限过于宽松: {", ".join(file_permission_issues)}'
            }
            if security_status['overall_status'] == 'secure':
                security_status['overall_status'] = 'warning'
        else:
            security_status['checks']['file_permissions'] = {
                'status': 'secure',
                'message': '敏感文件权限检查通过'
            }

        security_status['checks']['recent_logins'] = {
            'status': 'info',
            'message': '需要实现异常登录检测功能'
        }

    except Exception as e:
        security_status['checks']['error'] = {
            'status': 'error',
            'message': f'安全检查异常: {str(e)}'
        }
        security_status['overall_status'] = 'error'

    return security_status