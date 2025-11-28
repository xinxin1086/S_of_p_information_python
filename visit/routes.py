from flask import Blueprint, request, jsonify
from components.models import Notice
from datetime import datetime  # 移除 timezone 导入

visit_bp = Blueprint('visit', __name__, url_prefix='/api/visit')

@visit_bp.route('/notice', methods=['GET'])
def get_notices():
    try:
        notice_type = request.args.get('notice_type', '').strip()
        release_time_start = request.args.get('release_time_start', '').strip()
        release_time_end = request.args.get('release_time_end', '').strip()
        release_title = request.args.get('release_title', '').strip() or request.args.get('title', '').strip()
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))

        query = Notice.query

        if notice_type:
            query = query.filter(Notice.notice_type == notice_type)

        # 修复：直接解析 UTC 时间（与数据库存储格式一致）
        def parse_time(time_str):
            if not time_str:
                return None
            try:
                # 兼容 Z 后缀，直接解析为 UTC 时间（数据库存储格式）
                if time_str.endswith('Z'):
                    time_str = time_str.replace('Z', '+00:00')
                return datetime.fromisoformat(time_str)
            except ValueError as e:
                print(f"【时间解析失败】{time_str} -> {str(e)}")
                return None

        # 处理起始时间（直接匹配数据库的 UTC 时间）
        start_time = parse_time(release_time_start)
        if start_time:
            query = query.filter(Notice.release_time >= start_time)

        # 处理结束时间（直接匹配数据库的 UTC 时间）
        end_time = parse_time(release_time_end)
        if end_time:
            query = query.filter(Notice.release_time <= end_time)

        if release_title:
            query = query.filter(Notice.release_title.like(f'%{release_title}%'))

        pagination = query.order_by(Notice.release_time.desc()).paginate(page=page, per_page=size)
        notices = pagination.items
        total = pagination.total

        result = []
        for notice in notices:
            result.append({
                'id': notice.id,
                'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),  # 还原 Z 后缀
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z') if notice.update_time else None,
                'release_title': notice.release_title,
                'release_notice': notice.release_notice,
                'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
                'notice_type': notice.notice_type
            })

        return jsonify({
            'success': True,
            'message': '查询成功' if total > 0 else '无匹配数据',
            'data': {
                'total': total,
                'page': page,
                'size': size,
                'items': result
            }
        }), 200

    except Exception as e:
        print(f"【公告查询异常】{str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@visit_bp.route('/notice/<int:notice_id>', methods=['GET'])
def get_notice_detail(notice_id):
    try:
        notice = Notice.query.get(notice_id)

        if not notice:
            return jsonify({
                'success': False,
                'message': '公告不存在',
                'data': None
            }), 404

        # 处理attachments字段（如果有）
        attachments = None
        if notice.attachments:
            try:
                import json
                attachments = json.loads(notice.attachments)
            except json.JSONDecodeError:
                attachments = None

        result = {
            'id': notice.id,
            'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
            'update_time': notice.update_time.isoformat().replace('+00:00', 'Z') if notice.update_time else None,
            'release_title': notice.release_title,
            'release_notice': notice.release_notice,
            'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
            'notice_type': notice.notice_type,
            'attachments': attachments
        }

        return jsonify({
            'success': True,
            'message': '获取成功',
            'data': result
        }), 200

    except Exception as e:
        print(f"【公告详情查询异常】{str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500