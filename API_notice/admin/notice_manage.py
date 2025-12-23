# 管理员公告管理接口
# 包含：发布公告、编辑公告、置顶管理、推送管理、撤回公告等功能

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from components import db, token_required
from API_notice.common.utils import NoticeUtils, NoticePermissionUtils, NoticeQueryUtils
from components.models.notice_models import Notice, NoticeAttachment
from components.models.user_models import Admin


# 管理员权限装饰器
def admin_required(f):
    """管理员权限验证装饰器"""
    def decorated_function(current_user, *args, **kwargs):
        # 检查当前用户是否为管理员
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '需要管理员权限',
                'data': None
            }), 403
        return f(current_user, *args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


# 创建管理员公告管理蓝图
bp_notice_admin = Blueprint('notice_admin', __name__, url_prefix='/api/notice/admin')


@bp_notice_admin.route('/create', methods=['POST'])
@token_required
@admin_required
def create_notice(current_user):
    """
    创建公告
    需要管理员权限

    请求参数：
    {
        "title": "公告标题",
        "content": "公告内容",
        "notice_type": "SYSTEM|ADMIN|GENERAL",
        "expiration": "2024-12-31T23:59:59Z",  // 可选，到期时间
        "is_top": false,  // 可选，是否置顶
        "attachments": []  // 可选，附件列表
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据不能为空',
                'data': None
            }), 400

        # 验证必填字段
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        notice_type = data.get('notice_type', '').strip()

        if not title:
            return jsonify({
                'success': False,
                'message': '公告标题不能为空',
                'data': None
            }), 400

        if not content:
            return jsonify({
                'success': False,
                'message': '公告内容不能为空',
                'data': None
            }), 400

        if notice_type not in ['SYSTEM', 'ADMIN', 'GENERAL']:
            return jsonify({
                'success': False,
                'message': '无效的公告类型',
                'data': None
            }), 400

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '管理员信息不存在',
                'data': None
            }), 404

        # 解析到期时间
        expiration = None
        if data.get('expiration'):
            try:
                expiration = datetime.fromisoformat(data['expiration'].replace('Z', '+00:00'))
                if expiration <= datetime.now():
                    return jsonify({
                        'success': False,
                        'message': '到期时间不能早于当前时间',
                        'data': None
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '到期时间格式无效',
                    'data': None
                }), 400

        # 创建公告
        notice = Notice(
            release_title=title,
            release_notice=content,
            notice_type=notice_type,
            expiration=expiration,
            author_user_id=current_admin.id,
            author_display=f"{current_admin.username}（管理员）",
            status='APPROVED'  # 管理员创建的公告直接设为已发布状态
        )

        # 如果模型支持置顶功能
        if hasattr(notice, 'is_top'):
            notice.is_top = data.get('is_top', False)

        db.session.add(notice)
        db.session.flush()  # 获取公告ID

        # 处理附件（如果提供）
        attachments_data = data.get('attachments', [])
        if attachments_data:
            for attachment_data in attachments_data:
                if not all(key in attachment_data for key in ['file_name', 'file_path', 'file_size', 'file_type']):
                    continue  # 跳过无效的附件数据

                attachment = NoticeAttachment(
                    notice_id=notice.id,
                    uploader_account=current_admin.account,
                    file_name=attachment_data['file_name'],
                    file_path=attachment_data['file_path'],
                    file_size=attachment_data['file_size'],
                    file_type=attachment_data['file_type']
                )
                db.session.add(attachment)

        db.session.commit()

        print(f"【管理员创建公告成功】管理员: {current_user.account}, 公告ID: {notice.id}, 类型: {notice_type}")

        return jsonify({
            'success': True,
            'message': '公告创建成功',
            'data': {
                'id': notice.id,
                'title': notice.release_title,
                'notice_type': notice.notice_type,
                'status': notice.status,
                'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【管理员创建公告异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'创建失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_admin.route('/update/<int:notice_id>', methods=['PUT'])
@token_required
@admin_required
def update_notice(current_user, notice_id):
    """
    更新公告
    需要管理员权限

    Path参数：
    - notice_id: 公告ID

    请求参数：
    {
        "title": "公告标题",  // 可选
        "content": "公告内容",  // 可选
        "notice_type": "SYSTEM|ADMIN|GENERAL",  // 可选
        "expiration": "2024-12-31T23:59:59Z",  // 可选
        "is_top": false  // 可选
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据不能为空',
                'data': None
            }), 400

        # 获取公告
        notice = Notice.query.get(notice_id)
        if not notice:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '管理员信息不存在',
                'data': None
            }), 404

        # 权限校验
        can_manage, error_msg = NoticePermissionUtils.can_admin_manage_notice(
            admin_user_id=current_admin.id,
            notice=notice
        )

        if not can_manage:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        # 更新字段
        update_fields = []

        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return jsonify({
                    'success': False,
                    'message': '公告标题不能为空',
                    'data': None
                }), 400
            notice.release_title = title
            update_fields.append('title')

        if 'content' in data:
            content = data['content'].strip()
            if not content:
                return jsonify({
                    'success': False,
                    'message': '公告内容不能为空',
                    'data': None
                }), 400
            notice.release_notice = content
            update_fields.append('content')

        if 'notice_type' in data:
            notice_type = data['notice_type'].strip()
            if notice_type not in ['SYSTEM', 'ADMIN', 'GENERAL']:
                return jsonify({
                    'success': False,
                    'message': '无效的公告类型',
                    'data': None
                }), 400
            notice.notice_type = notice_type
            update_fields.append('notice_type')

        if 'expiration' in data:
            if data['expiration']:
                try:
                    expiration = datetime.fromisoformat(data['expiration'].replace('Z', '+00:00'))
                    if expiration <= datetime.now():
                        return jsonify({
                            'success': False,
                            'message': '到期时间不能早于当前时间',
                            'data': None
                        }), 400
                    notice.expiration = expiration
                except ValueError:
                    return jsonify({
                        'success': False,
                        'message': '到期时间格式无效',
                        'data': None
                    }), 400
            else:
                notice.expiration = None
            update_fields.append('expiration')

        if hasattr(notice, 'is_top') and 'is_top' in data:
            notice.is_top = data['is_top']
            update_fields.append('is_top')

        # 更新修改时间
        notice.update_time = datetime.now()

        db.session.commit()

        print(f"【管理员更新公告成功】管理员: {current_user.account}, 公告ID: {notice_id}, 更新字段: {update_fields}")

        return jsonify({
            'success': True,
            'message': '公告更新成功',
            'data': {
                'id': notice.id,
                'updated_fields': update_fields,
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z')
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【管理员更新公告异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'更新失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_admin.route('/delete/<int:notice_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_notice(current_user, notice_id):
    """
    删除公告（软删除，状态改为REJECTED）
    需要管理员权限

    Path参数：
    - notice_id: 公告ID
    """
    try:
        # 获取公告
        notice = Notice.query.get(notice_id)
        if not notice:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '管理员信息不存在',
                'data': None
            }), 404

        # 权限校验
        can_manage, error_msg = NoticePermissionUtils.can_admin_manage_notice(
            admin_user_id=current_admin.id,
            notice=notice
        )

        if not can_manage:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        # 软删除：状态改为REJECTED
        notice.status = 'REJECTED'
        notice.update_time = datetime.now()

        db.session.commit()

        print(f"【管理员删除公告成功】管理员: {current_user.account}, 公告ID: {notice_id}")

        return jsonify({
            'success': True,
            'message': '公告删除成功',
            'data': {
                'id': notice.id,
                'status': notice.status
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【管理员删除公告异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_admin.route('/list', methods=['GET'])
@token_required
@admin_required
def get_admin_notice_list(current_user):
    """
    管理员获取公告列表（支持条件筛选）
    需要管理员权限

    Query参数：
    - page: 页码（默认1）
    - size: 页大小（默认20）
    - status: 状态筛选（DRAFT/PENDING/APPROVED/REJECTED/EXPIRED）
    - type: 类型筛选（SYSTEM/ADMIN/GENERAL）
    - date_from: 开始日期（YYYY-MM-DD）
    - date_to: 结束日期（YYYY-MM-DD）
    - author: 作者筛选
    """
    try:
        print(f"【管理员公告列表查询】管理员: {current_user.account}")

        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status_filter = request.args.get('status', '').strip() or None
        type_filter = request.args.get('type', '').strip() or None
        date_from = request.args.get('date_from', '').strip() or None
        date_to = request.args.get('date_to', '').strip() or None
        author_filter = request.args.get('author', '').strip() or None

        # 构建基础查询
        base_query = Notice.query

        # 应用筛选条件
        filtered_query = NoticeQueryUtils.build_admin_filter_query(
            base_query=base_query,
            status_filter=status_filter,
            type_filter=type_filter,
            date_from=date_from,
            date_to=date_to,
            author_filter=author_filter
        )

        # 排序：置顶优先，然后按发布时间倒序
        if hasattr(Notice, 'is_top'):
            filtered_query = filtered_query.order_by(
                Notice.is_top.desc(),
                Notice.release_time.desc()
            )
        else:
            filtered_query = filtered_query.order_by(Notice.release_time.desc())

        # 分页查询
        pagination = filtered_query.paginate(page=page, per_page=size, error_out=False)
        notices = pagination.items
        total = pagination.total

        # 构建返回数据
        notice_list = []
        for notice in notices:
            # 获取已读统计
            read_stats = NoticeUtils.get_notice_read_statistics(notice.id)

            notice_data = {
                'id': notice.id,
                'title': notice.release_title,
                'content': notice.release_notice[:100] + '...' if len(notice.release_notice) > 100 else notice.release_notice,
                'notice_type': notice.notice_type,
                'status': notice.status,
                'is_top': getattr(notice, 'is_top', False),
                'is_expired': notice.is_expired,
                'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z'),
                'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
                'author_display': notice.author_display,
                'author_user_id': notice.author_user_id,
                'attachment_count': len(notice.attachments) if notice.attachments else 0,
                'read_stats': read_stats
            }
            notice_list.append(notice_data)

        result = {
            'total': total,
            'page': page,
            'size': size,
            'items': notice_list,
            'filters': {
                'status': status_filter,
                'type': type_filter,
                'date_from': date_from,
                'date_to': date_to,
                'author': author_filter
            }
        }

        print(f"【管理员公告列表查询成功】管理员: {current_user.account}, 总数: {total}")
        return jsonify({
            'success': True,
            'message': '公告列表查询成功',
            'data': result
        }), 200

    except Exception as e:
        print(f"【管理员公告列表查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_admin.route('/detail/<int:notice_id>', methods=['GET'])
@token_required
@admin_required
def get_admin_notice_detail(current_user, notice_id):
    """
    管理员获取公告详情（包含完整统计信息）
    需要管理员权限

    Path参数：
    - notice_id: 公告ID
    """
    try:
        print(f"【管理员公告详情查询】管理员: {current_user.account}, 公告ID: {notice_id}")

        # 获取公告详情
        notice_detail = NoticeQueryUtils.get_notice_with_attachments(notice_id)
        if not notice_detail:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 获取已读统计
        read_stats = NoticeUtils.get_notice_read_statistics(notice_id)

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()

        # 检查权限
        can_edit = False
        if current_admin and notice_detail['author_user_id'] == current_admin.id:
            can_edit = True

        result_data = {
            **notice_detail,
            'read_stats': read_stats,
            'can_edit': can_edit
        }

        print(f"【管理员公告详情查询成功】管理员: {current_user.account}, 公告标题: {notice_detail['title']}")
        return jsonify({
            'success': True,
            'message': '公告详情查询成功',
            'data': result_data
        }), 200

    except Exception as e:
        print(f"【管理员公告详情查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_admin.route('/top/<int:notice_id>', methods=['POST'])
@token_required
@admin_required
def toggle_notice_top(current_user, notice_id):
    """
    切换公告置顶状态
    需要管理员权限

    Path参数：
    - notice_id: 公告ID

    请求参数：
    {
        "is_top": true  // 是否置顶
    }
    """
    try:
        data = request.get_json()
        if not data or 'is_top' not in data:
            return jsonify({
                'success': False,
                'message': '缺少置顶状态参数',
                'data': None
            }), 400

        # 获取公告
        notice = Notice.query.get(notice_id)
        if not notice:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 检查模型是否支持置顶功能
        if not hasattr(notice, 'is_top'):
            return jsonify({
                'success': False,
                'message': '当前公告模型不支持置顶功能',
                'data': None
            }), 400

        # 获取当前管理员信息
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '管理员信息不存在',
                'data': None
            }), 404

        # 权限校验
        can_manage, error_msg = NoticePermissionUtils.can_admin_manage_notice(
            admin_user_id=current_admin.id,
            notice=notice
        )

        if not can_manage:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        # 更新置顶状态
        old_top_status = notice.is_top
        notice.is_top = data['is_top']
        notice.update_time = datetime.now()

        db.session.commit()

        action = "置顶" if notice.is_top else "取消置顶"
        print(f"【管理员{action}公告成功】管理员: {current_user.account}, 公告ID: {notice_id}")

        return jsonify({
            'success': True,
            'message': f'公告{action}成功',
            'data': {
                'id': notice.id,
                'is_top': notice.is_top,
                'old_is_top': old_top_status,
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z')
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【管理员置顶公告异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'操作失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_admin.route('/statistics', methods=['GET'])
@token_required
@admin_required
def get_notice_statistics(current_user):
    """
    获取公告统计数据
    需要管理员权限
    """
    try:
        print(f"【管理员公告统计查询】管理员: {current_user.account}")

        from sqlalchemy import func

        # 统计各状态公告数量
        status_stats = db.session.query(
            Notice.status,
            func.count(Notice.id)
        ).group_by(Notice.status).all()

        # 统计各类型公告数量
        type_stats = db.session.query(
            Notice.notice_type,
            func.count(Notice.id)
        ).group_by(Notice.notice_type).all()

        # 统计总公告数和活跃公告数
        total_count = Notice.query.count()
        active_count = Notice.query.filter(
            and_(
                Notice.status == 'APPROVED',
                or_(
                    Notice.expiration.is_(None),
                    Notice.expiration > datetime.now()
                )
            )
        ).count()

        # 统计置顶公告数量（如果支持）
        top_count = 0
        if hasattr(Notice, 'is_top'):
            top_count = Notice.query.filter(
                and_(
                    Notice.is_top == True,
                    Notice.status == 'APPROVED',
                    or_(
                        Notice.expiration.is_(None),
                        Notice.expiration > datetime.now()
                    )
                )
            ).count()

        # 统计过期公告数量
        expired_count = Notice.query.filter(
            and_(
                Notice.expiration.isnot(None),
                Notice.expiration <= datetime.now(),
                Notice.status != 'EXPIRED'
            )
        ).count()

        # 近期发布的公告数量（最近7天）
        recent_date = datetime.now() - timedelta(days=7)
        recent_count = Notice.query.filter(
            Notice.release_time >= recent_date
        ).count()

        result = {
            'overview': {
                'total_count': total_count,
                'active_count': active_count,
                'top_count': top_count,
                'expired_count': expired_count,
                'recent_count': recent_count
            },
            'status_distribution': {status: count for status, count in status_stats},
            'type_distribution': {notice_type: count for notice_type, count in type_stats}
        }

        print(f"【管理员公告统计查询成功】管理员: {current_user.account}")
        return jsonify({
            'success': True,
            'message': '公告统计数据查询成功',
            'data': result
        }), 200

    except Exception as e:
        print(f"【管理员公告统计查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500