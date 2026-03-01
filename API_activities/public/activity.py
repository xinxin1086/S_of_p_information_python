# 活动公开访问接口

from flask import Blueprint, request
from components import db
from components.models import Activity
from components.response_service import ResponseService
from datetime import datetime

# 创建活动公开访问模块蓝图
bp_activities_public = Blueprint('activities_public', __name__, url_prefix='/api/public/activities')

# 公开的活动列表查询（无需登录）
@bp_activities_public.route('/activities', methods=['GET'])
def get_public_activities():
    """
    获取公开的活动列表（无需登录）
    """
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        keyword = request.args.get('keyword', '').strip()
        organizer_display = request.args.get('organizer_display', '').strip()
        status = request.args.get('status', 'published')  # 默认只显示已发布的活动
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # 构建查询
        query = Activity.query

        # 状态筛选
        if status:
            query = query.filter(Activity.status == status)

        # 关键词搜索（标题和描述）
        if keyword:
            query = query.filter(
                (Activity.title.like(f'%{keyword}%')) |
                (Activity.description.like(f'%{keyword}%'))
            )

        # 组织者筛选
        if organizer_display:
            query = query.filter(Activity.organizer_display.like(f'%{organizer_display}%'))

        # 时间范围筛选
        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Activity.start_time >= start_datetime)
            except ValueError:
                pass  # 忽略无效的日期格式

        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Activity.end_time <= end_datetime)
            except ValueError:
                pass  # 忽略无效的日期格式

        # 分页查询（按开始时间倒序，即将开始的活动在前）
        pagination = query.order_by(Activity.start_time.asc()).paginate(page=page, per_page=size)
        activities = pagination.items
        total = pagination.total

        result_list = []
        for activity in activities:
            # 计算活动状态
            now = datetime.utcnow()
            if activity.start_time > now:
                activity_status = "即将开始"
            elif activity.end_time >= now:
                activity_status = "进行中"
            else:
                activity_status = "已结束"

            # 获取报名人数（如果有预约表的话）
            try:
                from components.models import ActivityBooking
                booking_count = ActivityBooking.query.filter_by(
                    activity_id=activity.id,
                    status='confirmed'
                ).count()
            except:
                booking_count = 0

            item = {
                'id': activity.id,
                'title': activity.title,
                'description': activity.description[:200] + '...' if len(activity.description) > 200 else activity.description,
                'organizer_display': activity.organizer_display,
                'location': activity.location,
                'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
                'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
                'max_participants': activity.max_participants,
                'current_participants': booking_count,
                'activity_status': activity_status,
                'status': activity.status,
                'created_at': activity.created_at.isoformat().replace('+00:00', 'Z')
            }
            result_list.append(item)

        return ResponseService.paginated_success(
            items=result_list,
            total=total,
            page=page,
            size=size,
            message="活动列表查询成功"
        )

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

# 公开的活动详情查询（无需登录）
@bp_activities_public.route('/activities/<int:activity_id>', methods=['GET'])
def get_public_activity_detail(activity_id):
    """
    获取公开的活动详情（无需登录）
    """
    try:
        activity = Activity.query.filter_by(id=activity_id, status='published').first()
        if not activity:
            return ResponseService.error('活动不存在或未发布', status_code=404)

        # 获取报名人数
        try:
            from components.models import ActivityBooking
            booking_count = ActivityBooking.query.filter_by(
                activity_id=activity.id,
                status='confirmed'
            ).count()
        except:
            booking_count = 0

        # 计算活动状态
        now = datetime.utcnow()
        if activity.start_time > now:
            activity_status = "即将开始"
            days_until = (activity.start_time - now).days
            status_info = f"距离开始还有 {days_until} 天"
        elif activity.end_time >= now:
            activity_status = "进行中"
            status_info = "活动正在进行中"
        else:
            activity_status = "已结束"
            status_info = "活动已结束"

        # 检查是否还可以报名
        can_book = (
            activity_status == "即将开始" and
            activity.max_participants and
            booking_count < activity.max_participants
        )

        # 返回完整信息
        item = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'organizer_display': activity.organizer_display,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_participants': booking_count,
            'available_slots': max(0, activity.max_participants - booking_count) if activity.max_participants else None,
            'activity_status': activity_status,
            'status_info': status_info,
            'can_book': can_book,
            'status': activity.status,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z'),
            'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z') if activity.updated_at else None
        }

        return ResponseService.success(data=item, message="活动详情查询成功")

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

# 公开的活动统计信息（无需登录）
@bp_activities_public.route('/activities/statistics', methods=['GET'])
def get_public_activities_statistics():
    """
    获取活动公开统计信息（无需登录）
    """
    try:
        from sqlalchemy import func

        # 基本统计（仅已发布活动）
        total_published = Activity.query.filter_by(status='published').count()

        # 活动状态统计
        now = datetime.utcnow()

        # 即将开始的活动
        upcoming_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.start_time > now
        ).count()

        # 进行中的活动
        ongoing_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.start_time <= now,
            Activity.end_time >= now
        ).count()

        # 已结束的活动
        completed_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.end_time < now
        ).count()

        # 最近30天发布的活动
        thirty_days_ago = datetime.utcnow() - datetime.timedelta(days=30)
        recent_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.created_at >= thirty_days_ago
        ).count()

        # 获取报名统计（如果有预约表）
        try:
            from components.models import ActivityBooking
            booking_stats = db.session.query(
                func.count(ActivityBooking.id).label('total_bookings'),
                func.count(func.distinct(ActivityBooking.user_id)).label('unique_participants')
            ).filter(ActivityBooking.status == 'confirmed').first()

            total_bookings = booking_stats.total_bookings or 0
            unique_participants = booking_stats.unique_participants or 0
        except:
            total_bookings = 0
            unique_participants = 0

        statistics = {
            'total_published': total_published,
            'upcoming_count': upcoming_count,
            'ongoing_count': ongoing_count,
            'completed_count': completed_count,
            'recent_published_30days': recent_count,
            'total_bookings': total_bookings,
            'unique_participants': unique_participants
        }

        return ResponseService.success(data=statistics, message="活动统计查询成功")

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)

print("【API_activities 公开访问接口模块加载完成】")