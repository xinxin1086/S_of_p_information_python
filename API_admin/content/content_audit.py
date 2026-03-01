# 内容审核管理接口模块

from flask import Blueprint, request, jsonify, Response
from components import db
from API_admin.common.utils import super_admin_required, admin_required, log_admin_operation, export_to_csv, get_cross_module_pending_content, batch_update_user_display
from datetime import datetime
import json

# 创建内容审核蓝图
bp_admin_content = Blueprint('admin_content', __name__, url_prefix='/api/admin/content')

# 跨模块待审核内容查询接口
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
            from components.models import ScienceArticle
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
            from components.models import Activity
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
            from components.models import ActivityDiscuss
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

# 批量审核接口
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
                    from components.models import ScienceArticle
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
                    from components.models import Activity
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
                    from components.models import ActivityDiscuss
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

# 内容详情查看接口
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
            from components.models import ScienceArticle
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
            from components.models import Activity
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
            from components.models import ActivityDiscuss
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

# 内容导出接口
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
            from components.models import ScienceArticle
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
            from components.models import Activity
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
            from components.models import ActivityDiscuss
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

# 批量更新用户显示信息接口
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

# 内容统计接口
@bp_admin_content.route('/statistics', methods=['GET'])
@admin_required
def get_content_statistics(current_user):
    """
    获取内容管理统计数据
    """
    try:
        # 记录查看统计日志
        log_admin_operation(current_user, 'VIEW', 'content_statistics')

        from components.models import ScienceArticle, Activity, ActivityDiscuss
        from sqlalchemy import text

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