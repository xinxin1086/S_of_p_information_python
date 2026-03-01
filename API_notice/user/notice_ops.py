
from flask import Blueprint, request, jsonify
from datetime import datetime
from components import db, token_required
from API_notice.common.utils import NoticeUtils, NoticePermissionUtils, NoticeQueryUtils
from components.models.user_models import User, Admin
import logging

logger = logging.getLogger(__name__)


bp_notice_user = Blueprint('notice_user', __name__, url_prefix='/api/notice')


@bp_notice_user.route('/list', methods=['GET'])
@token_required
def get_notice_list(current_user):
    
    try:
        logger.info(f"【用户公告列表查询】用户: {current_user.account}")

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        notice_type = request.args.get('type', '').strip() or None

        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        result = NoticeUtils.get_user_notice_list(
            user_id=current_user.id,
            page=page,
            size=size,
            notice_type=notice_type,
            is_admin=is_admin
        )

        logger.info(f"【用户公告列表查询成功】用户: {current_user.account}, 总数: {result['total']}, 未读数: {result['unread_count']}")
        return jsonify({
            'success': True,
            'message': '公告列表查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【用户公告列表查询异常】")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_user.route('/detail/<int:notice_id>', methods=['GET'])
@token_required
def get_notice_detail(current_user, notice_id):
    
    try:
        logger.info(f"【用户公告详情查询】用户: {current_user.account}, 公告ID: {notice_id}")

        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        can_view, error_msg = NoticePermissionUtils.can_user_view_notice(
            user_id=current_user.id,
            notice_id=notice_id,
            is_admin=is_admin
        )

        if not can_view:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        notice_detail = NoticeQueryUtils.get_notice_with_attachments(notice_id)
        if not notice_detail:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        NoticeUtils.mark_notice_as_read(current_user.id, notice_id)

        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        result_data = {
            **notice_detail,
            'unread_count': unread_count
        }

        logger.info(f"【用户公告详情查询成功】用户: {current_user.account}, 公告标题: {notice_detail['title']}")
        return jsonify({
            'success': True,
            'message': '公告详情查询成功',
            'data': result_data
        }), 200

    except Exception:
        logger.exception("【用户公告详情查询异常】")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_user.route('/read/<int:notice_id>', methods=['POST'])
@token_required
def mark_notice_as_read(current_user, notice_id):
    
    try:
        logger.info(f"【标记公告已读】用户: {current_user.account}, 公告ID: {notice_id}")

        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        can_view, error_msg = NoticePermissionUtils.can_user_view_notice(
            user_id=current_user.id,
            notice_id=notice_id,
            is_admin=is_admin
        )

        if not can_view:
            return jsonify({
                'success': False,
                'message': error_msg,
                'data': None
            }), 403

        success = NoticeUtils.mark_notice_as_read(current_user.id, notice_id)
        if not success:
            return jsonify({
                'success': False,
                'message': '标记失败，公告可能不存在或已失效',
                'data': None
            }), 400

        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        logger.info(f"【标记公告已读成功】用户: {current_user.account}, 公告ID: {notice_id}")
        return jsonify({
            'success': True,
            'message': '已成功标记为已读',
            'data': {
                'notice_id': notice_id,
                'unread_count': unread_count
            }
        }), 200

    except Exception:
        logger.exception("【标记公告已读异常】")
        return jsonify({
            'success': False,
            'message': f'操作失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_user.route('/read/all', methods=['POST'])
@token_required
def mark_all_notices_as_read(current_user):
    
    try:
        logger.info(f"【标记全部公告已读】用户: {current_user.account}")

        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        read_count = NoticeUtils.mark_all_notices_as_read(
            user_id=current_user.id,
            is_admin=is_admin
        )

        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        logger.info(f"【标记全部公告已读成功】用户: {current_user.account}, 标记数量: {read_count}")
        return jsonify({
            'success': True,
            'message': f'已成功标记 {read_count} 条公告为已读',
            'data': {
                'marked_count': read_count,
                'unread_count': unread_count
            }
        }), 200

    except Exception:
        logger.exception("【标记全部公告已读异常】")
        return jsonify({
            'success': False,
            'message': f'操作失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_user.route('/unread/count', methods=['GET'])
@token_required
def get_unread_count(current_user):
    
    try:
        logger.info(f"【未读公告数量查询】用户: {current_user.account}")

        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        logger.info(f"【未读公告数量查询成功】用户: {current_user.account}, 未读数: {unread_count}")
        return jsonify({
            'success': True,
            'message': '未读公告数量查询成功',
            'data': {
                'unread_count': unread_count
            }
        }), 200

    except Exception:
        logger.exception("【未读公告数量查询异常】")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_user.route('/types', methods=['GET'])
@token_required
def get_notice_types(current_user):
    
    try:
        logger.info(f"【公告类型查询】用户: {current_user.account}")

        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        if is_admin:
            types = [
                {'value': 'SYSTEM', 'label': '系统通知'},
                {'value': 'ACTIVITY', 'label': '活动公告'},
                {'value': 'GENERAL', 'label': '其他公告'}
            ]
        else:
            types = [
                {'value': 'SYSTEM', 'label': '系统通知'},
                {'value': 'ACTIVITY', 'label': '活动公告'},
                {'value': 'GENERAL', 'label': '其他公告'}
            ]

        logger.info(f"【公告类型查询成功】用户: {current_user.account}, 管理员: {is_admin}")
        return jsonify({
            'success': True,
            'message': '公告类型查询成功',
            'data': {
                'types': types,
                'is_admin': is_admin
            }
        }), 200

    except Exception:
        logger.exception("【公告类型查询异常】")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_user.route('/search', methods=['GET'])
@token_required
def search_notices(current_user):
    
    try:
        logger.info(f"【公告搜索】用户: {current_user.account}")

        keyword = request.args.get('keyword', '').strip()
        if not keyword:
            return jsonify({
                'success': False,
                'message': '搜索关键词不能为空',
                'data': None
            }), 400

        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        notice_type = request.args.get('type', '').strip() or None

        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        from components.models.notice_models import Notice
        from sqlalchemy import and_, or_

        search_query = Notice.query.filter(
            and_(
                Notice.status == 'APPROVED',
                or_(
                    Notice.expiration.is_(None),
                    Notice.expiration > datetime.utcnow()
                ),
                or_(
                    Notice.release_title.like(f"%{keyword}%"),
                    Notice.release_notice.like(f"%{keyword}%")
                )
            )
        )

        if not is_admin:
            search_query = search_query.filter(
                Notice.notice_type.in_(['SYSTEM', 'ACTIVITY', 'GENERAL'])
            )

        if notice_type:
            search_query = search_query.filter(Notice.notice_type == notice_type)

        search_query = search_query.order_by(
            Notice.is_top.desc(),
            Notice.release_time.desc()
        )

        pagination = search_query.paginate(page=page, per_page=size, error_out=False)
        notices = pagination.items
        total = pagination.total

        notice_list = []
        for notice in notices:
            is_read = db.session.query(NoticeRead).filter(
                and_(
                    NoticeRead.user_id == current_user.id,
                    NoticeRead.notice_id == notice.id
                )
            ).first() is not None

            notice_data = {
                'id': notice.id,
                'title': notice.release_title,
                'content': notice.release_notice[:200] + '...' if len(notice.release_notice) > 200 else notice.release_notice,
                'notice_type': notice.notice_type,
                'is_top': getattr(notice, 'is_top', False),
                'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
                'author_display': notice.author_display,
                'is_read': is_read,
                'attachment_count': len(notice.attachments) if notice.attachments else 0
            }
            notice_list.append(notice_data)

        unread_count = NoticeUtils.get_user_unread_count(current_user.id, is_admin)

        result = {
            'total': total,
            'page': page,
            'size': size,
            'items': notice_list,
            'unread_count': unread_count,
            'keyword': keyword
        }

        logger.info(f"【公告搜索成功】用户: {current_user.account}, 关键词: {keyword}, 结果数: {total}")
        return jsonify({
            'success': True,
            'message': '公告搜索成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【公告搜索异常】")
        return jsonify({
            'success': False,
            'message': f'搜索失败：{str(e)}',
            'data': None
        }), 500