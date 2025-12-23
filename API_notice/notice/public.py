# 公告公开访问接口

from flask import Blueprint, request
from components import db
from components.models import Notice
from components.response_service import ResponseService
from datetime import datetime

# 创建公告公开访问模块蓝图
bp_notice_public = Blueprint('notice_public', __name__, url_prefix='/api/public/notice')

# 公开的公告列表查询（无需登录）
@bp_notice_public.route('/list', methods=['GET'])
def get_public_notices():
    """
    获取公开发布的公告列表（无需登录）
    """
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        notice_type = request.args.get('notice_type', '').strip()
        release_time_start = request.args.get('release_time_start', '').strip()
        release_time_end = request.args.get('release_time_end', '').strip()
        release_title = request.args.get('title', '').strip()

        # 构建查询
        query = Notice.query.filter_by(status='APPROVED')

        # 类型筛选
        if notice_type:
            query = query.filter(Notice.notice_type == notice_type)

        # 标题搜索
        if release_title:
            query = query.filter(Notice.release_title.like(f'%{release_title}%'))

        # 发布时间范围筛选
        def parse_time(time_str):
            if not time_str:
                return None
            try:
                if time_str.endswith('Z'):
                    time_str = time_str.replace('Z', '+00:00')
                return datetime.fromisoformat(time_str)
            except ValueError:
                return None

        start_time = parse_time(release_time_start)
        if start_time:
            query = query.filter(Notice.release_time >= start_time)

        end_time = parse_time(release_time_end)
        if end_time:
            query = query.filter(Notice.release_time <= end_time)

        # 检查过期状态（不显示已过期的公告）
        current_time = datetime.utcnow()
        query = query.filter(
            (Notice.expiration.is_(None)) | (Notice.expiration > current_time)
        )

        # 分页查询
        pagination = query.order_by(Notice.release_time.desc()).paginate(page=page, per_page=size)
        notices = pagination.items
        total = pagination.total

        result = []
        for notice in notices:
            # 处理附件字段
            attachments = None
            if notice.attachments:
                try:
                    import json
                    attachments = json.loads(notice.attachments)
                except json.JSONDecodeError:
                    attachments = None

            result.append({
                'id': notice.id,
                'release_time': notice.release_time.isoformat().replace('+00:00', 'Z'),
                'update_time': notice.update_time.isoformat().replace('+00:00', 'Z') if notice.update_time else None,
                'release_title': notice.release_title,
                'summary': notice.release_notice[:200] + '...' if len(notice.release_notice) > 200 else notice.release_notice,
                'notice_type': notice.notice_type,
                'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
                'is_expired': notice.is_expired,
                'attachment_count': len(attachments) if attachments else 0
            })

        return ResponseService.paginated_success(
            items=result,
            total=total,
            page=page,
            size=size,
            message="公告列表查询成功"
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

# 公开的公告详情查询（无需登录）
@bp_notice_public.route('/detail/<int:notice_id>', methods=['GET'])
def get_public_notice_detail(notice_id):
    """
    获取公开发布的公告详情（无需登录）
    """
    try:
        notice = Notice.query.filter_by(id=notice_id, status='APPROVED').first()
        if not notice:
            return ResponseService.error('公告不存在或未发布', status_code=404)

        # 检查是否过期
        if notice.is_expired:
            return ResponseService.error('公告已过期', status_code=410)

        # 处理附件字段
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
            'notice_type': notice.notice_type,
            'expiration': notice.expiration.isoformat().replace('+00:00', 'Z') if notice.expiration else None,
            'is_expired': notice.is_expired,
            'author_display': notice.author_display,
            'attachments': attachments
        }

        return ResponseService.success(data=result, message="公告详情查询成功")

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

# 公开的公告分类统计（无需登录）
@bp_notice_public.route('/statistics', methods=['GET'])
def get_public_notice_statistics():
    """
    获取公告统计信息（无需登录）
    """
    try:
        from sqlalchemy import func

        current_time = datetime.utcnow()

        # 基本统计
        total_active = Notice.query.filter_by(status='APPROVED').filter(
            (Notice.expiration.is_(None)) | (Notice.expiration > current_time)
        ).count()

        # 按类型统计
        type_stats = db.session.query(
            Notice.notice_type,
            func.count(Notice.id).label('count')
        ).filter_by(status='APPROVED').filter(
            (Notice.expiration.is_(None)) | (Notice.expiration > current_time)
        ).group_by(Notice.notice_type).all()

        type_distribution = {notice_type: count for notice_type, count in type_stats}

        # 最近发布的公告（最近30天）
        thirty_days_ago = current_time - datetime.timedelta(days=30)
        recent_count = Notice.query.filter(
            Notice.status == 'APPROVED',
            Notice.release_time >= thirty_days_ago
        ).filter(
            (Notice.expiration.is_(None)) | (Notice.expiration > current_time)
        ).count()

        # 过期公告数量
        expired_count = Notice.query.filter(
            Notice.status == 'APPROVED',
            Notice.expiration.isnot(None),
            Notice.expiration <= current_time
        ).count()

        statistics = {
            'total_active': total_active,
            'expired_count': expired_count,
            'recent_30days': recent_count,
            'type_distribution': type_distribution
        }

        return ResponseService.success(data=statistics, message="公告统计查询成功")

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)

# 公开的公告类型列表（无需登录）
@bp_notice_public.route('/types', methods=['GET'])
def get_public_notice_types():
    """
    获取公告类型列表（无需登录）
    """
    try:
        # 定义公告类型
        notice_types = [
            {'value': 'SYSTEM', 'label': '系统公告', 'description': '系统级别的通知公告'},
            {'value': 'ADMIN', 'label': '管理公告', 'description': '管理员发布的通知'},
            {'value': 'GENERAL', 'label': '一般公告', 'description': '常规公告信息'}
        ]

        return ResponseService.success(data=notice_types, message="公告类型查询成功")

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

print("【API_notice 公开访问接口模块加载完成】")