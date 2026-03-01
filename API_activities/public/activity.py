
from flask import Blueprint, request
from components import db
from components.models import Activity
from components.response_service import ResponseService
from datetime import datetime

bp_activities_public = Blueprint('activities_public', __name__, url_prefix='/api/public/activities')

@bp_activities_public.route('/activities', methods=['GET'])
def get_public_activities():
    
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        keyword = request.args.get('keyword', '').strip()
        organizer_display = request.args.get('organizer_display', '').strip()
        status = request.args.get('status', 'published')
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        query = Activity.query

        if status:
            query = query.filter(Activity.status == status)

        if keyword:
            query = query.filter(
                (Activity.title.like(f'%{keyword}%')) |
                (Activity.description.like(f'%{keyword}%'))
            )

        if organizer_display:
            query = query.filter(Activity.organizer_display.like(f'%{organizer_display}%'))

        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Activity.start_time >= start_datetime)
            except ValueError:
                pass

        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Activity.end_time <= end_datetime)
            except ValueError:
                pass

        pagination = query.order_by(Activity.start_time.asc()).paginate(page=page, per_page=size)
        activities = pagination.items
        total = pagination.total

        result_list = []
        for activity in activities:
            now = datetime.utcnow()
            if activity.start_time > now:
                activity_status = "即将开始"
            elif activity.end_time >= now:
                activity_status = "进行中"
            else:
                activity_status = "已结束"

            try:
                from components.models import ActivityBooking
                booking_count = ActivityBooking.query.filter_by(
                    activity_id=activity.id,
                    status='booked'
                ).count()
            except Exception:
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

@bp_activities_public.route('/activities/<int:activity_id>', methods=['GET'])
def get_public_activity_detail(activity_id):
    
    try:
        activity = Activity.query.filter_by(id=activity_id, status='published').first()
        if not activity:
            return ResponseService.error('活动不存在或未发布', status_code=404)

        try:
            from components.models import ActivityBooking
            booking_count = ActivityBooking.query.filter_by(
                activity_id=activity.id,
                status='booked'
            ).count()
        except Exception:
            booking_count = 0

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

        can_book = (
            activity_status == "即将开始" and
            activity.max_participants and
            booking_count < activity.max_participants
        )

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

@bp_activities_public.route('/activities/statistics', methods=['GET'])
def get_public_activities_statistics():
    
    try:
        from sqlalchemy import func

        total_published = Activity.query.filter_by(status='published').count()

        now = datetime.utcnow()

        upcoming_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.start_time > now
        ).count()

        ongoing_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.start_time <= now,
            Activity.end_time >= now
        ).count()

        completed_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.end_time < now
        ).count()

        thirty_days_ago = datetime.utcnow() - datetime.timedelta(days=30)
        recent_count = Activity.query.filter(
            Activity.status == 'published',
            Activity.created_at >= thirty_days_ago
        ).count()

        try:
            from components.models import ActivityBooking
            booking_stats = db.session.query(
                func.count(ActivityBooking.id).label('total_bookings'),
                func.count(func.distinct(ActivityBooking.user_account)).label('unique_participants')
            ).filter(ActivityBooking.status == 'booked').first()

            total_bookings = booking_stats.total_bookings or 0
            unique_participants = booking_stats.unique_participants or 0
        except Exception:
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