# API_admin 公共工具模块

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
    """
    超级管理员权限装饰器
    仅有SUPER_ADMIN角色的用户可以访问
    """
    @wraps(f)
    @token_required
    def decorated_function(current_user, *args, **kwargs):
        # 检查用户类型和权限
        if not hasattr(current_user, 'role') or current_user.role != 'SUPER_ADMIN':
            return jsonify({
                'success': False,
                'message': '权限不足，需要超级管理员权限',
                'data': None
            }), 403
        return f(current_user, *args, **kwargs)
    return decorated_function

def log_admin_operation(current_user, operation_type, target_table, target_id=None, details=None):
    """
    记录管理员操作日志

    Args:
        current_user: 当前用户对象
        operation_type: 操作类型 (CREATE/UPDATE/DELETE/VIEW/EXPORT)
        target_table: 目标表名
        target_id: 目标ID（可选）
        details: 详细信息（可选）
    """
    try:
        # 这里可以将日志保存到数据库表
        # 如果没有专门的日志表，可以记录到文件
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

        # 记录到控制台（生产环境建议使用日志系统）
        print(f"【管理员操作日志】{json.dumps(log_data, ensure_ascii=False)}")

        # 如果有日志表，可以保存到数据库
        # from components.models import AdminOperationLog
        # log_entry = AdminOperationLog(**log_data)
        # db.session.add(log_entry)
        # db.session.commit()

    except Exception as e:
        print(f"【日志记录异常】错误: {str(e)}")

def export_to_csv(data, filename, headers=None):
    """
    导出数据为CSV文件

    Args:
        data: 要导出的数据列表
        filename: 文件名
        headers: CSV头部（可选）

    Returns:
        Flask Response对象
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # 写入头部
    if headers:
        writer.writerow(headers)

    # 写入数据
    for row in data:
        if isinstance(row, dict):
            writer.writerow(row.values())
        else:
            writer.writerow(row)

    output.seek(0)

    # 创建响应对象
    response = Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

    return response

def validate_date_range(start_date, end_date):
    """
    验证日期范围

    Args:
        start_date: 开始日期字符串
        end_date: 结束日期字符串

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            if start_dt > datetime.utcnow():
                return False, '开始日期不能晚于当前日期'

        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            if start_date and start_dt > end_dt:
                return False, '开始日期不能晚于结束日期'

        # 限制查询范围不超过1年
        if start_date and end_date:
            days_diff = (end_dt - start_dt).days
            if days_diff > 365:
                return False, '查询时间范围不能超过1年'

        return True, None

    except ValueError:
        return False, '日期格式不正确，请使用YYYY-MM-DD格式'

def encrypt_sensitive_data(data):
    """
    加密敏感数据

    Args:
        data: 要加密的数据

    Returns:
        str: 加密后的数据
    """
    try:
        # 使用SHA-256进行简单加密（生产环境建议使用更强的加密算法）
        return hashlib.sha256(data.encode()).hexdigest()
    except Exception as e:
        print(f"【数据加密异常】错误: {str(e)}")
        return None

def get_cross_module_pending_content():
    """
    获取跨模块待审核内容

    Returns:
        dict: 各模块待审核内容统计
    """
    try:
        stats = {}

        # 科普文章待审核数量
        science_pending = ScienceArticle.query.filter_by(status='pending').count()
        stats['science_articles'] = {
            'pending_count': science_pending,
            'table_name': 'science_articles'
        }

        # 活动待审核数量
        activity_pending = Activity.query.filter_by(status='pending').count()
        stats['activities'] = {
            'pending_count': activity_pending,
            'table_name': 'activities'
        }

        # 论坛讨论待审核数量（如果存在）
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

        # 统计总数
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
    """
    批量更新已删除用户的显示信息

    Returns:
        dict: 更新结果统计
    """
    try:
        from components.models import ScienceArticle, Activity, ActivityDiscuss, ActivityDiscussComment, ActivityRating

        updates = {}
        total_updated = 0

        # 更新科普文章作者显示
        science_result = db.session.execute(text("""
            UPDATE science_articles
            SET author_display = '用户已注销'
            WHERE author_user_id IS NOT NULL
            AND author_user_id IN (
                SELECT id FROM user_info WHERE is_deleted = 1
            )
            AND author_display != '用户已注销'
        """))
        updates['science_articles'] = science_result.rowcount
        total_updated += science_result.rowcount

        # 更新活动相关用户显示
        activity_result = db.session.execute(text("""
            UPDATE activities
            SET organizer_display = '用户已注销'
            WHERE organizer_user_id IS NOT NULL
            AND organizer_user_id IN (
                SELECT id FROM user_info WHERE is_deleted = 1
            )
            AND organizer_display != '用户已注销'
        """))
        updates['activities'] = activity_result.rowcount
        total_updated += activity_result.rowcount

        # 更新活动讨论作者显示
        discuss_result = db.session.execute(text("""
            UPDATE activity_discuss
            SET author_display = '用户已注销'
            WHERE author_user_id IS NOT NULL
            AND author_user_id IN (
                SELECT id FROM user_info WHERE is_deleted = 1
            )
            AND author_display != '用户已注销'
        """))
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
    """
    系统安全检查

    Returns:
        dict: 安全检查结果
    """
    security_status = {
        'overall_status': 'secure',
        'checks': {}
    }

    try:
        # 检查默认密码
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

        # 检查敏感文件权限
        sensitive_files = ['config.py', '.env']
        file_permission_issues = []

        for file_name in sensitive_files:
            if os.path.exists(file_name):
                file_stat = os.stat(file_name)
                if file_stat.st_mode & 0o077:  # 检查组和其他用户的权限
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

        # 检查最近异常登录
        # 这里可以实现检查异常登录的逻辑
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