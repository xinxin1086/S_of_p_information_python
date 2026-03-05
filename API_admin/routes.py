# API_admin 统一路由文件
# 包含所有管理员相关的路由和工具函数

from functools import wraps
from flask import Blueprint, request, jsonify, Response
from components import db, token_required
from components.models import Admin, User, ScienceArticle, Activity, ActivityDiscuss
from components.permissions import admin_required
from components.response_service import ResponseService
from datetime import datetime, timedelta
import csv
import io
import json
import hashlib
import os
from sqlalchemy import text

# ==================== 蓝图定义 ====================

# 创建主管理员蓝图
bp_admin = Blueprint('admin', __name__, url_prefix='/api/admin')

# 创建内容审核蓝图
bp_admin_content = Blueprint('admin_content', __name__, url_prefix='/api/admin/content')

# 创建统计分析蓝图
bp_admin_stats = Blueprint('admin_stats', __name__, url_prefix='/api/admin/statistics')

# ==================== 工具函数 ====================

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
        from components.models import ActivityDiscussComment, ActivityRating

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

# ==================== 管理员管理路由 ====================

@bp_admin.route('/list', methods=['GET'])
@admin_required
def list_admins(current_user=None, **kwargs):
    """
    获取管理员列表
    需要管理员权限
    """
    try:
        keyword = request.args.get('keyword', '').strip()
        role = request.args.get('role', '').strip()

        query = Admin.query
        if keyword:
            # 支持账号/姓名/邮箱/手机号模糊查询
            like_kw = f"%{keyword}%"
            query = query.filter(
                (Admin.account.like(like_kw)) |
                (Admin.username.like(like_kw)) |
                (Admin.email.like(like_kw)) |
                (Admin.phone.like(like_kw))
            )
        if role:
            query = query.filter(Admin.role == role)

        admins = query.order_by(Admin.created_at.desc()).all()

        items = []
        for admin in admins:
            items.append({
                'id': admin.id,
                'account': admin.account,
                'username': admin.username,
                'phone': admin.phone or '',
                'email': admin.email or '',
                'avatar': admin.avatar or '',
                'role': admin.role
            })

        log_admin_operation(
            current_user,
            'VIEW',
            'admin_info',
            details={
                'keyword': keyword,
                'role': role,
                'result_count': len(items)
            }
        )

        return ResponseService.success(
            data={
                'fields': Admin.get_fields_info(),
                'items': items,
                'total': len(items)
            },
            message='查询成功' if items else '暂无数据'
        )
    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

# ==================== 内容审核路由 ====================

@bp_admin_content.route('/pending/all', methods=['GET'])
@admin_required
def get_all_pending_content(current_user):
    """
    获取所有模块的待审核内容
    支持分页和模块筛选
    """
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        module = request.args.get('module', '').strip()  # science/activity/forum
        status = request.args.get('status', 'pending').strip()

        # 记录操作日志
        log_admin_operation(
            current_user,
            'VIEW',
            'pending_content',
            details={'module': module, 'status': status}
        )

        results = {}

        # 科普文章待审核内容
        if module in ['', 'science']:
            science_query = ScienceArticle.query.filter_by(status=status)

            if status == 'pending':
                science_query = science_query.order_by(ScienceArticle.created_at.desc())

            science_pagination = science_query.paginate(page=page, per_page=size, error_out=False)

            results['science_articles'] = {
                'total': science_pagination.total,
                'items': [
                    {
                        'id': article.id,
                        'title': article.title,
                        'author': article.author_display,
                        'status': article.status,
                        'created_at': article.created_at.isoformat() + 'Z',
                        'updated_at': article.updated_at.isoformat() + 'Z' if article.updated_at else None
                    }
                    for article in science_pagination.items
                ]
            }

        # 活动待审核内容
        if module in ['', 'activity']:
            activity_query = Activity.query.filter_by(status=status)

            if status == 'pending':
                activity_query = activity_query.order_by(Activity.created_at.desc())

            activity_pagination = activity_query.paginate(page=page, per_page=size, error_out=False)

            results['activities'] = {
                'total': activity_pagination.total,
                'items': [
                    {
                        'id': activity.id,
                        'title': activity.title,
                        'organizer': activity.organizer_display,
                        'status': activity.status,
                        'activity_type': activity.activity_type,
                        'created_at': activity.created_at.isoformat() + 'Z',
                        'updated_at': activity.updated_at.isoformat() + 'Z' if activity.updated_at else None
                    }
                    for activity in activity_pagination.items
                ]
            }

        # 论坛讨论待审核内容
        if module in ['', 'forum']:
            discuss_query = ActivityDiscuss.query.filter_by(status=status)

            if status == 'pending':
                discuss_query = discuss_query.order_by(ActivityDiscuss.created_at.desc())

            discuss_pagination = discuss_query.paginate(page=page, per_page=size, error_out=False)

            results['forum_discussions'] = {
                'total': discuss_pagination.total,
                'items': [
                    {
                        'id': discussion.id,
                        'title': discussion.title,
                        'author': discussion.author_display,
                        'status': discussion.status,
                        'content': discussion.content[:100] + '...' if len(discussion.content) > 100 else discussion.content,
                        'created_at': discussion.created_at.isoformat() + 'Z',
                        'updated_at': discussion.updated_at.isoformat() + 'Z' if discussion.updated_at else None
                    }
                    for discussion in discuss_pagination.items
                ]
            }

        # 统计信息
        stats = get_cross_module_pending_content()
        results['summary'] = stats

        total_count = sum(
            module_data['total']
            for module_data in results.values()
            if isinstance(module_data, dict) and 'total' in module_data
        )

        return jsonify({
            'success': True,
            'message': '待审核内容查询成功',
            'data': {
                'total_pending': total_count,
                'modules': results,
                'filters': {
                    'module': module,
                    'status': status,
                    'page': page,
                    'size': size
                }
            }
        }), 200

    except Exception as e:
        print(f"【待审核内容查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'待审核内容查询失败：{str(e)}',
            'data': None
        }), 500

@bp_admin_content.route('/batch-review', methods=['POST'])
@admin_required
def batch_review_content(current_user):
    """
    批量审核内容
    支持批量通过、拒绝、退回修改
    """
    try:
        data = request.get_json()
        action = data.get('action')  # approve/reject/request_changes
        content_list = data.get('content_list', [])  # [{'module': 'science', 'id': 1, 'reason': '...'}]
        review_comment = data.get('review_comment', '')

        if not content_list:
            return jsonify({
                'success': False,
                'message': '请提供要审核的内容列表',
                'data': None
            }), 400

        # 记录批量审核操作日志
        log_admin_operation(
            current_user,
            'UPDATE',
            'batch_content_review',
            details={
                'action': action,
                'content_count': len(content_list),
                'review_comment': review_comment
            }
        )

        success_count = 0
        error_count = 0
        errors = []

        # 根据不同模块执行审核操作
        for content_item in content_list:
            try:
                module = content_item.get('module')
                content_id = content_item.get('id')
                reason = content_item.get('reason', review_comment)

                if module == 'science':
                    content = ScienceArticle.query.get(content_id)
                    if content:
                        if action == 'approve':
                            content.status = 'published'
                        elif action == 'reject':
                            content.status = 'rejected'
                        elif action == 'request_changes':
                            content.status = 'draft'

                        content.review_comment = reason
                        content.reviewed_by = current_user.username
                        content.reviewed_at = datetime.utcnow()
                        success_count += 1
                    else:
                        errors.append(f'科普文章ID {content_id} 不存在')
                        error_count += 1

                elif module == 'activity':
                    content = Activity.query.get(content_id)
                    if content:
                        if action == 'approve':
                            content.status = 'published'
                        elif action == 'reject':
                            content.status = 'rejected'
                        elif action == 'request_changes':
                            content.status = 'draft'

                        content.review_comment = reason
                        content.reviewed_by = current_user.username
                        content.reviewed_at = datetime.utcnow()
                        success_count += 1
                    else:
                        errors.append(f'活动ID {content_id} 不存在')
                        error_count += 1

                elif module == 'forum':
                    content = ActivityDiscuss.query.get(content_id)
                    if content:
                        if action == 'approve':
                            content.status = 'approved'
                        elif action == 'reject':
                            content.status = 'rejected'
                        elif action == 'request_changes':
                            content.status = 'draft'

                        content.review_comment = reason
                        content.reviewed_by = current_user.username
                        content.reviewed_at = datetime.utcnow()
                        success_count += 1
                    else:
                        errors.append(f'论坛讨论ID {content_id} 不存在')
                        error_count += 1

                else:
                    errors.append(f'未知模块: {module}')
                    error_count += 1

            except Exception as e:
                errors.append(f'处理内容ID {content_item.get("id")} 时出错: {str(e)}')
                error_count += 1

        # 提交事务
        if success_count > 0:
            try:
                db.session.commit()
                print(f"【批量审核成功】处理了 {success_count} 条内容")
            except Exception as e:
                db.session.rollback()
                errors.append(f'数据库提交失败: {str(e)}')
                error_count += success_count
                success_count = 0

        return jsonify({
            'success': error_count == 0,
            'message': f'批量审核完成，成功: {success_count} 条，失败: {error_count} 条',
            'data': {
                'action': action,
                'total_processed': len(content_list),
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors
            }
        }), 200 if error_count == 0 else 500

    except Exception as e:
        db.session.rollback()
        print(f"【批量审核异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量审核失败：{str(e)}',
            'data': None
        }), 500

@bp_admin_content.route('/detail/<module>/<int:content_id>', methods=['GET'])
@admin_required
def get_content_detail(current_user, module, content_id):
    """
    获取内容详情
    支持科普、活动、论坛内容查看
    """
    try:
        # 记录查看操作日志
        log_admin_operation(
            current_user,
            'VIEW',
            f'{module}_content_detail',
            details={'content_id': content_id}
        )

        if module == 'science':
            content = ScienceArticle.query.get(content_id)
            if content:
                detail = {
                    'id': content.id,
                    'title': content.title,
                    'content': content.content,
                    'summary': content.summary,
                    'author_display': content.author_display,
                    'author_user_id': content.author_user_id,
                    'status': content.status,
                    'tags': content.tags,
                    'category': content.category,
                    'cover_image': content.cover_image,
                    'view_count': content.view_count,
                    'like_count': content.like_count,
                    'created_at': content.created_at.isoformat() + 'Z',
                    'updated_at': content.updated_at.isoformat() + 'Z' if content.updated_at else None,
                    'review_comment': getattr(content, 'review_comment', ''),
                    'reviewed_by': getattr(content, 'reviewed_by', ''),
                    'reviewed_at': getattr(content, 'reviewed_at', '').isoformat() + 'Z' if getattr(content, 'reviewed_at', None) else None
                }
            else:
                return jsonify({
                    'success': False,
                    'message': '科普文章不存在',
                    'data': None
                }), 404

        elif module == 'activity':
            content = Activity.query.get(content_id)
            if content:
                detail = {
                    'id': content.id,
                    'title': content.title,
                    'description': content.description,
                    'organizer_display': content.organizer_display,
                    'organizer_user_id': content.organizer_user_id,
                    'status': content.status,
                    'activity_type': content.activity_type,
                    'start_time': content.start_time.isoformat() + 'Z' if content.start_time else None,
                    'end_time': content.end_time.isoformat() + 'Z' if content.end_time else None,
                    'location': content.location,
                    'max_participants': content.max_participants,
                    'current_participants': content.current_participants,
                    'cover_image': content.cover_image,
                    'created_at': content.created_at.isoformat() + 'Z',
                    'updated_at': content.updated_at.isoformat() + 'Z' if content.updated_at else None,
                    'review_comment': getattr(content, 'review_comment', ''),
                    'reviewed_by': getattr(content, 'reviewed_by', ''),
                    'reviewed_at': getattr(content, 'reviewed_at', '').isoformat() + 'Z' if getattr(content, 'reviewed_at', None) else None
                }
            else:
                return jsonify({
                    'success': False,
                    'message': '活动不存在',
                    'data': None
                }), 404

        elif module == 'forum':
            content = ActivityDiscuss.query.get(content_id)
            if content:
                detail = {
                    'id': content.id,
                    'title': content.title,
                    'content': content.content,
                    'author_display': content.author_display,
                    'author_user_id': content.author_user_id,
                    'status': content.status,
                    'tags': content.tags,
                    'view_count': content.view_count,
                    'like_count': content.like_count,
                    'comment_count': content.comment_count,
                    'created_at': content.created_at.isoformat() + 'Z',
                    'updated_at': content.updated_at.isoformat() + 'Z' if content.updated_at else None,
                    'review_comment': getattr(content, 'review_comment', ''),
                    'reviewed_by': getattr(content, 'reviewed_by', ''),
                    'reviewed_at': getattr(content, 'reviewed_at', '').isoformat() + 'Z' if getattr(content, 'reviewed_at', None) else None
                }
            else:
                return jsonify({
                    'success': False,
                    'message': '论坛讨论不存在',
                    'data': None
                }), 404

        else:
            return jsonify({
                'success': False,
                'message': '未知的内容模块',
                'data': None
            }), 400

        return jsonify({
            'success': True,
            'message': f'{module}内容详情获取成功',
            'data': detail
        }), 200

    except Exception as e:
        print(f"【内容详情查看异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'内容详情获取失败：{str(e)}',
            'data': None
        }), 500

@bp_admin_content.route('/export', methods=['POST'])
@admin_required
def export_content_data(current_user):
    """
    导出内容数据
    支持按模块、状态、时间范围筛选导出
    """
    try:
        data = request.get_json()
        modules = data.get('modules', ['science', 'activity', 'forum'])  # 要导出的模块
        status = data.get('status', '')  # 状态筛选
        start_date = data.get('start_date', '')  # 开始日期
        end_date = data.get('end_date', '')  # 结束日期
        export_format = data.get('format', 'csv')  # 导出格式 csv/json

        # 记录导出操作日志
        log_admin_operation(
            current_user,
            'EXPORT',
            'content_data',
            details={
                'modules': modules,
                'status': status,
                'start_date': start_date,
                'end_date': end_date,
                'format': export_format
            }
        )

        export_data = []

        # 科普文章数据
        if 'science' in modules:
            query = ScienceArticle.query

            if status:
                query = query.filter_by(status=status)
            if start_date:
                query = query.filter(ScienceArticle.created_at >= start_date)
            if end_date:
                query = query.filter(ScienceArticle.created_at <= end_date)

            articles = query.all()
            for article in articles:
                export_data.append({
                    '模块': '科普文章',
                    'ID': article.id,
                    '标题': article.title,
                    '作者': article.author_display,
                    '状态': article.status,
                    '分类': article.category,
                    '浏览量': article.view_count,
                    '点赞数': article.like_count,
                    '创建时间': article.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    '更新时间': article.updated_at.strftime('%Y-%m-%d %H:%M:%S') if article.updated_at else ''
                })

        # 活动数据
        if 'activity' in modules:
            query = Activity.query

            if status:
                query = query.filter_by(status=status)
            if start_date:
                query = query.filter(Activity.created_at >= start_date)
            if end_date:
                query = query.filter(Activity.created_at <= end_date)

            activities = query.all()
            for activity in activities:
                export_data.append({
                    '模块': '活动',
                    'ID': activity.id,
                    '标题': activity.title,
                    '组织者': activity.organizer_display,
                    '状态': activity.status,
                    '活动类型': activity.activity_type,
                    '参与人数': f"{activity.current_participants}/{activity.max_participants}",
                    '开始时间': activity.start_time.strftime('%Y-%m-%d %H:%M:%S') if activity.start_time else '',
                    '结束时间': activity.end_time.strftime('%Y-%m-%d %H:%M:%S') if activity.end_time else '',
                    '创建时间': activity.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    '更新时间': activity.updated_at.strftime('%Y-%m-%d %H:%M:%S') if activity.updated_at else ''
                })

        # 论坛讨论数据
        if 'forum' in modules:
            query = ActivityDiscuss.query

            if status:
                query = query.filter_by(status=status)
            if start_date:
                query = query.filter(ActivityDiscuss.created_at >= start_date)
            if end_date:
                query = query.filter(ActivityDiscuss.created_at <= end_date)

            discussions = query.all()
            for discussion in discussions:
                export_data.append({
                    '模块': '论坛讨论',
                    'ID': discussion.id,
                    '标题': discussion.title,
                    '作者': discussion.author_display,
                    '状态': discussion.status,
                    '浏览量': discussion.view_count,
                    '点赞数': discussion.like_count,
                    '评论数': discussion.comment_count,
                    '创建时间': discussion.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    '更新时间': discussion.updated_at.strftime('%Y-%m-%d %H:%M:%S') if discussion.updated_at else ''
                })

        # 生成文件名
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"content_export_{timestamp}.{export_format}"

        if export_format == 'csv':
            # CSV导出
            headers = ['模块', 'ID', '标题', '作者/组织者', '状态', '分类/类型', '数据', '时间']

            # 转换数据格式
            csv_data = []
            for item in export_data:
                if item['模块'] == '科普文章':
                    csv_data.append([
                        item['模块'], item['ID'], item['标题'], item['作者'], item['状态'],
                        item['分类'], f"浏览:{item['浏览量']} 点赞:{item['点赞数']}", item['创建时间']
                    ])
                elif item['模块'] == '活动':
                    csv_data.append([
                        item['模块'], item['ID'], item['标题'], item['组织者'], item['状态'],
                        item['活动类型'], f"参与:{item['参与人数']} 时间:{item['开始时间']}", item['创建时间']
                    ])
                elif item['模块'] == '论坛讨论':
                    csv_data.append([
                        item['模块'], item['ID'], item['标题'], item['作者'], item['状态'],
                        '', f"浏览:{item['浏览量']} 评论:{item['评论数']}", item['创建时间']
                    ])

            return export_to_csv(csv_data, filename, headers)

        elif export_format == 'json':
            # JSON导出
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
        print(f"【内容导出异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'内容导出失败：{str(e)}',
            'data': None
        }), 500

@bp_admin_content.route('/update-user-displays', methods=['POST'])
@super_admin_required
def update_user_displays(current_user):
    """
    批量更新已删除用户的显示信息为"用户已注销"
    """
    try:
        # 记录操作日志
        log_admin_operation(
            current_user,
            'UPDATE',
            'user_display_info'
        )

        # 执行批量更新
        result = batch_update_user_display()

        if result['success']:
            return jsonify({
                'success': True,
                'message': f'用户显示信息更新成功，共更新 {result["total_updated"]} 条记录',
                'data': {
                    'total_updated': result['total_updated'],
                    'updates_by_type': result['updates_by_type'],
                    'update_time': datetime.utcnow().isoformat() + 'Z'
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': f'用户显示信息更新失败：{result["error"]}',
                'data': None
            }), 500

    except Exception as e:
        print(f"【批量更新用户显示异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量更新失败：{str(e)}',
            'data': None
        }), 500

@bp_admin_content.route('/statistics', methods=['GET'])
@admin_required
def get_content_statistics(current_user):
    """
    获取内容管理统计数据
    """
    try:
        # 记录查看统计日志
        log_admin_operation(current_user, 'VIEW', 'content_statistics')

        stats = {}

        # 科普文章统计
        article_stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(view_count) as total_views,
                SUM(like_count) as total_likes
            FROM science_articles
        """)).fetchone()

        stats['science_articles'] = {
            'total': article_stats.total or 0,
            'published': article_stats.published or 0,
            'draft': article_stats.draft or 0,
            'pending': article_stats.pending or 0,
            'rejected': article_stats.rejected or 0,
            'total_views': article_stats.total_views or 0,
            'total_likes': article_stats.total_likes or 0
        }

        # 活动统计
        activity_stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft,
                SUM(CASE WHEN status = 'ongoing' THEN 1 ELSE 0 END) as ongoing,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                SUM(current_participants) as total_participants
            FROM activities
        """)).fetchone()

        stats['activities'] = {
            'total': activity_stats.total or 0,
            'published': activity_stats.published or 0,
            'draft': activity_stats.draft or 0,
            'ongoing': activity_stats.ongoing or 0,
            'completed': activity_stats.completed or 0,
            'cancelled': activity_stats.cancelled or 0,
            'total_participants': activity_stats.total_participants or 0
        }

        # 论坛讨论统计
        forum_stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(view_count) as total_views,
                SUM(like_count) as total_likes
            FROM activity_discuss
        """)).fetchone()

        stats['forum_discussions'] = {
            'total': forum_stats.total or 0,
            'approved': forum_stats.approved or 0,
            'pending': forum_stats.pending or 0,
            'rejected': forum_stats.rejected or 0,
            'total_views': forum_stats.total_views or 0,
            'total_likes': forum_stats.total_likes or 0
        }

        # 总体统计
        stats['summary'] = {
            'total_content': (
                stats['science_articles']['total'] +
                stats['activities']['total'] +
                stats['forum_discussions']['total']
            ),
            'pending_review': (
                stats['science_articles']['pending'] +
                stats['activities']['published'] +  # 假设发布的活动需要审核
                stats['forum_discussions']['pending']
            ),
            'total_views': (
                stats['science_articles']['total_views'] +
                stats['forum_discussions']['total_views']
            ),
            'total_engagement': (
                stats['science_articles']['total_likes'] +
                stats['forum_discussions']['total_likes'] +
                stats['activities']['total_participants']
            )
        }

        return jsonify({
            'success': True,
            'message': '内容统计数据获取成功',
            'data': stats
        }), 200

    except Exception as e:
        print(f"【内容统计查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'内容统计查询失败：{str(e)}',
            'data': None
        }), 500

# ==================== 统计分析路由 ====================

@bp_admin_stats.route('/user-growth', methods=['GET'])
@super_admin_required
def get_user_growth_stats(current_user):
    """
    获取用户增长统计数据
    支持按天、周、月统计用户注册增长
    """
    try:
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        period = request.args.get('period', 'day')  # day/week/month
        chart_type = request.args.get('chart_type', 'line')  # line/bar/area

        # 验证日期范围
        is_valid, error_msg = validate_date_range(start_date, end_date)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 400

        # 设置默认日期范围（最近30天）
        if not start_date:
            end_date_dt = datetime.utcnow()
            start_date_dt = end_date_dt - timedelta(days=30)
            start_date = start_date_dt.strftime('%Y-%m-%d')
            end_date = end_date_dt.strftime('%Y-%m-%d')

        # 记录操作日志
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

        # 根据统计周期构建SQL查询
        if period == 'day':
            date_format = '%Y-%m-%d'
            group_by = 'DATE(created_at)'
        elif period == 'week':
            date_format = '%Y-%u'  # 年-周
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

        # 查询用户注册数据
        user_query = text(f"""
            SELECT
                {group_by} as period,
                COUNT(*) as new_users,
                COUNT(CASE WHEN is_deleted = 0 THEN 1 END) as active_users
            FROM user_info
            WHERE created_at BETWEEN :start_date AND :end_date
            GROUP BY {group_by}
            ORDER BY period
        """)

        user_stats = db.session.execute(user_query, {
            'start_date': start_date,
            'end_date': end_date + ' 23:59:59'
        }).fetchall()

        # 查询管理员数据
        admin_query = text(f"""
            SELECT
                {group_by} as period,
                COUNT(*) as new_admins
            FROM admin
            WHERE created_at BETWEEN :start_date AND :end_date
            GROUP BY {group_by}
            ORDER BY period
        """)

        admin_stats = db.session.execute(admin_query, {
            'start_date': start_date,
            'end_date': end_date + ' 23:59:59'
        }).fetchall()

        # 构建图表数据
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

        # 填充图表数据
        user_dict = {str(row.period): {'new_users': row.new_users, 'active_users': row.active_users} for row in user_stats}
        admin_dict = {str(row.period): row.new_admins for row in admin_stats}

        # 合并所有日期
        all_periods = sorted(set(user_dict.keys()) | set(admin_dict.keys()))

        for period in all_periods:
            chart_data['labels'].append(period)
            user_data = user_dict.get(period, {'new_users': 0, 'active_users': 0})
            chart_data['datasets'][0]['data'].append(user_data['new_users'])
            chart_data['datasets'][1]['data'].append(user_data['active_users'])
            chart_data['datasets'][2]['data'].append(admin_dict.get(period, 0))

        # 计算汇总统计
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
    """
    获取内容发布统计数据
    包括科普文章、活动、论坛讨论的发布趋势
    """
    try:
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        period = request.args.get('period', 'day')  # day/week/month
        content_type = request.args.get('content_type', 'all')  # all/science/activity/forum

        # 验证日期范围
        is_valid, error_msg = validate_date_range(start_date, end_date)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 400

        # 设置默认日期范围（最近30天）
        if not start_date:
            end_date_dt = datetime.utcnow()
            start_date_dt = end_date_dt - timedelta(days=30)
            start_date = start_date_dt.strftime('%Y-%m-%d')
            end_date = end_date_dt.strftime('%Y-%m-%d')

        # 记录操作日志
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

        # 根据统计周期构建SQL查询
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

        # 科普文章统计
        if content_type in ['all', 'science']:
            science_query = text(f"""
                SELECT
                    {group_by} as period,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
                FROM science_articles
                WHERE created_at BETWEEN :start_date AND :end_date
                GROUP BY {group_by}
                ORDER BY period
            """)

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

        # 活动统计
        if content_type in ['all', 'activity']:
            activity_query = text(f"""
                SELECT
                    {group_by} as period,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
                    SUM(CASE WHEN status = 'ongoing' THEN 1 ELSE 0 END) as ongoing,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                FROM activities
                WHERE created_at BETWEEN :start_date AND :end_date
                GROUP BY {group_by}
                ORDER BY period
            """)

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

        # 论坛讨论统计
        if content_type in ['all', 'forum']:
            forum_query = text(f"""
                SELECT
                    {group_by} as period,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
                FROM activity_discuss
                WHERE created_at BETWEEN :start_date AND :end_date
                GROUP BY {group_by}
                ORDER BY period
            """)

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

        # 排序周期
        sorted_periods = sorted(all_periods)

        # 填充图表数据
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

        # 计算汇总统计
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
    """
    获取活动参与度统计数据
    包括活动参与人数、完成率、评分统计等
    """
    try:
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        activity_type = request.args.get('activity_type', '').strip()  # 活动类型筛选

        # 验证日期范围
        is_valid, error_msg = validate_date_range(start_date, end_date)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 400

        # 设置默认日期范围（最近30天）
        if not start_date:
            end_date_dt = datetime.utcnow()
            start_date_dt = end_date_dt - timedelta(days=30)
            start_date = start_date_dt.strftime('%Y-%m-%d')
            end_date = end_date_dt.strftime('%Y-%m-%d')

        # 记录操作日志
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

        # 构建查询条件
        where_conditions = ["created_at BETWEEN :start_date AND :end_date"]
        params = {'start_date': start_date, 'end_date': end_date + ' 23:59:59'}

        if activity_type:
            where_conditions.append("activity_type = :activity_type")
            params['activity_type'] = activity_type

        where_clause = "WHERE " + " AND ".join(where_conditions)

        # 活动参与度统计
        engagement_query = text(f"""
            SELECT
                activity_type,
                COUNT(*) as total_activities,
                SUM(current_participants) as total_participants,
                SUM(max_participants) as total_capacity,
                AVG(current_participants / max_participants * 100) as avg_fill_rate,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_activities,
                SUM(CASE WHEN status = 'ongoing' THEN 1 ELSE 0 END) as ongoing_activities
            FROM activities
            {where_clause}
            GROUP BY activity_type
            ORDER BY total_activities DESC
        """)

        engagement_stats = db.session.execute(engagement_query, params).fetchall()

        # 月度参与趋势
        monthly_trend_query = text(f"""
            SELECT
                DATE_FORMAT(created_at, '%Y-%m') as month,
                COUNT(*) as activities_created,
                SUM(current_participants) as total_participants,
                AVG(current_participants / max_participants * 100) as avg_fill_rate
            FROM activities
            {where_clause}
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month
        """)

        monthly_trend = db.session.execute(monthly_trend_query, params).fetchall()

        # 最受欢迎的活动类型
        popular_types_query = text(f"""
            SELECT
                activity_type,
                COUNT(*) as count,
                SUM(current_participants) as total_participants,
                AVG(current_participants) as avg_participants
            FROM activities
            {where_clause}
            GROUP BY activity_type
            ORDER BY total_participants DESC
            LIMIT 10
        """)

        popular_types = db.session.execute(popular_types_query, params).fetchall()

        # 构建图表数据
        # 活动类型分布饼图
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

        # 月度参与趋势折线图
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

        # 计算汇总统计
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

        # 活动类型详细统计
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
    """
    获取系统使用情况统计数据
    包括API访问量、数据增长趋势、系统资源使用等
    """
    try:
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        period = request.args.get('period', 'day')  # day/week/month

        # 验证日期范围
        is_valid, error_msg = validate_date_range(start_date, end_date)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 400

        # 设置默认日期范围（最近30天）
        if not start_date:
            end_date_dt = datetime.utcnow()
            start_date_dt = end_date_dt - timedelta(days=30)
            start_date = start_date_dt.strftime('%Y-%m-%d')
            end_date = end_date_dt.strftime('%Y-%m-%d')

        # 记录操作日志
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

        # 数据库统计查询
        db_stats = {}

        # 用户表统计
        user_stats_query = text("""
            SELECT
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_deleted = 0 THEN 1 END) as active_users,
                COUNT(CASE WHEN DATE(created_at) = CURDATE() THEN 1 END) as today_registrations,
                COUNT(CASE WHEN DATE(last_login) = CURDATE() THEN 1 END) as today_logins
            FROM user_info
        """)

        user_stats = db.session.execute(user_stats_query).fetchone()
        db_stats['users'] = {
            'total': user_stats.total_users,
            'active': user_stats.active_users,
            'today_registrations': user_stats.today_registrations,
            'today_logins': user_stats.today_logins
        }

        # 内容统计
        content_stats_query = text("""
            SELECT
                (SELECT COUNT(*) FROM science_articles) as science_articles,
                (SELECT COUNT(*) FROM activities) as activities,
                (SELECT COUNT(*) FROM activity_discuss) as forum_discussions,
                (SELECT COUNT(*) FROM activity_rating) as activity_ratings,
                (SELECT SUM(view_count) FROM science_articles WHERE view_count IS NOT NULL) as total_science_views,
                (SELECT SUM(view_count) FROM activity_discuss WHERE view_count IS NOT NULL) as total_forum_views
        """)

        content_stats = db.session.execute(content_stats_query).fetchone()
        db_stats['content'] = {
            'science_articles': content_stats.science_articles,
            'activities': content_stats.activities,
            'forum_discussions': content_stats.forum_discussions,
            'activity_ratings': content_stats.activity_ratings,
            'total_views': (content_stats.total_science_views or 0) + (content_stats.total_forum_views or 0)
        }

        # 数据增长趋势
        if period == 'day':
            date_format = '%Y-%m-%d'
            group_by = 'DATE(created_at)'
        elif period == 'week':
            date_format = '%Y-%u'
            group_by = 'YEARWEEK(created_at)'
        elif period == 'month':
            date_format = '%Y-%m'
            group_by = 'DATE_FORMAT(created_at, "%Y-%m")'

        growth_query = text(f"""
            SELECT
                {group_by} as period,
                COUNT(CASE WHEN table_name = 'user_info' THEN 1 END) as new_users,
                COUNT(CASE WHEN table_name = 'science_articles' THEN 1 END) as new_articles,
                COUNT(CASE WHEN table_name = 'activities' THEN 1 END) as new_activities
            FROM (
                SELECT 'user_info' as table_name, created_at FROM user_info
                WHERE created_at BETWEEN :start_date AND :end_date
                UNION ALL
                SELECT 'science_articles' as table_name, created_at FROM science_articles
                WHERE created_at BETWEEN :start_date AND :end_date
                UNION ALL
                SELECT 'activities' as table_name, created_at FROM activities
                WHERE created_at BETWEEN :start_date AND :end_date
            ) as combined_data
            GROUP BY {group_by}
            ORDER BY period
        """)

        growth_stats = db.session.execute(growth_query, {
            'start_date': start_date,
            'end_date': end_date + ' 23:59:59'
        }).fetchall()

        # 构建增长趋势图表数据
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

        # 数据库大小统计
        db_size_query = text("""
            SELECT
                table_schema as 'database',
                ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'size_mb'
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            GROUP BY table_schema
        """)

        db_size_stats = db.session.execute(db_size_query).fetchone()
        db_size = db_size_stats.size_mb if db_size_stats else 0

        # 汇总统计
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
    """
    导出统计数据
    支持导出各种统计报表
    """
    try:
        data = request.get_json()
        report_type = data.get('report_type', 'user_growth')  # user_growth/content_publishing/activity_engagement/system_usage
        export_format = data.get('format', 'csv')  # csv/json
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')

        # 记录导出操作日志
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
            # 导出用户增长数据
            query = text("""
                SELECT
                    DATE(created_at) as date,
                    COUNT(*) as new_users,
                    COUNT(CASE WHEN is_deleted = 0 THEN 1 END) as active_users
                FROM user_info
                WHERE (:start_date = '' OR created_at >= :start_date)
                AND (:end_date = '' OR created_at <= :end_date)
                GROUP BY DATE(created_at)
                ORDER BY date
            """)

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
            # 导出内容发布数据
            query = text("""
                SELECT
                    'science_articles' as module,
                    DATE(created_at) as date,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published
                FROM science_articles
                WHERE (:start_date = '' OR created_at >= :start_date)
                AND (:end_date = '' OR created_at <= :end_date)
                GROUP BY DATE(created_at)
                UNION ALL
                SELECT
                    'activities' as module,
                    DATE(created_at) as date,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published
                FROM activities
                WHERE (:start_date = '' OR created_at >= :start_date)
                AND (:end_date = '' OR created_at <= :end_date)
                GROUP BY DATE(created_at)
                ORDER BY date, module
            """)

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
            # 导出活动参与度数据
            query = text("""
                SELECT
                    activity_type,
                    COUNT(*) as total_activities,
                    SUM(current_participants) as total_participants,
                    SUM(max_participants) as total_capacity,
                    AVG(current_participants / max_participants * 100) as avg_fill_rate
                FROM activities
                WHERE (:start_date = '' OR created_at >= :start_date)
                AND (:end_date = '' OR created_at <= :end_date)
                GROUP BY activity_type
                ORDER BY total_activities DESC
            """)

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
            # 导出系统使用概况
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
            # CSV导出
            headers = list(export_data[0].keys()) if export_data else []
            csv_data = [[item[key] for key in headers] for item in export_data]
            return export_to_csv(csv_data, filename, headers)

        elif export_format == 'json':
            # JSON导出
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
