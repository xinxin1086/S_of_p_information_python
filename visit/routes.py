from flask import Blueprint, request, jsonify
from components.models import Notice
from datetime import datetime

visit_bp = Blueprint('visit', __name__, url_prefix='/api/visit')

@visit_bp.route('/notice', methods=['GET'])
def get_notices():
    try:
        # 提取查询参数（兼容前端传 title，映射到 release_title）
        notice_type = request.args.get('notice_type', '').strip()
        release_time_start = request.args.get('release_time_start', '').strip()
        release_time_end = request.args.get('release_time_end', '').strip()
        # 关键：同时支持 title 和 release_title 两种参数名，适配前端
        release_title = request.args.get('release_title', '').strip() or request.args.get('title', '').strip()
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))

        # 构建查询条件
        query = Notice.query

        # 公告类型筛选（非空才筛选）
        if notice_type:
            query = query.filter(Notice.notice_type == notice_type)

        # 处理时间参数（兼容 Z 后缀和多余字符）
        def parse_time(time_str):
            if not time_str:
                return None
            # 移除多余的 HTTP/1.1 后缀（如果有）
            time_str = time_str.split(' ')[0]
            # 替换 Z 为 +00:00，兼容 ISO 格式
            time_str = time_str.replace('Z', '+00:00')
            try:
                return datetime.fromisoformat(time_str)
            except ValueError:
                return None

        # 发布时间起始筛选
        start_time = parse_time(release_time_start)
        if start_time:
            query = query.filter(Notice.release_time >= start_time)

        # 发布时间结束筛选
        end_time = parse_time(release_time_end)
        if end_time:
            query = query.filter(Notice.release_time <= end_time)

        # 公告标题模糊查询（非空才筛选）
        if release_title:
            query = query.filter(Notice.release_title.like(f'%{release_title}%'))

        # 分页查询（按发布时间倒序）
        pagination = query.order_by(Notice.release_time.desc()).paginate(page=page, per_page=size)
        notices = pagination.items
        total = pagination.total

        # 格式化返回数据
        result = []
        for notice in notices:
            result.append({
                'release_time': notice.release_time.isoformat(),
                'release_title': notice.release_title,
                'release_notice': notice.release_notice,
                'expiration': notice.expiration.isoformat() if notice.expiration else None,
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
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500