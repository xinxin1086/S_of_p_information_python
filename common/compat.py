from flask import Blueprint, request, jsonify
from components import token_required, db, LocalImageStorage
from components.models import Activity, ActivityBooking, Attachment
from components.response_service import ResponseService
from datetime import datetime

compat_bp = Blueprint('compat', __name__, url_prefix='/api')


@compat_bp.route('/activities/my-activities', methods=['GET'])
@token_required
def alias_get_my_activities(current_user):
    """
    兼容旧前端路径：/api/activities/my-activities
    直接返回用户创建或参与的活动（与 /api/activities/user/my-activities 功能一致）
    """
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        role = request.args.get('role', 'all')
        status = request.args.get('status', '').strip()

        result_list = []

        if role in ['organizer', 'all']:
            organizer_query = Activity.query.filter_by(organizer_user_id=current_user.id)
            if status:
                organizer_query = organizer_query.filter(Activity.status == status)
            organizer_activities = organizer_query.order_by(Activity.updated_at.desc()).all()

            for activity in organizer_activities:
                try:
                    current_bookings = ActivityBooking.query.filter_by(activity_id=activity.id, status='booked').count()
                except Exception:
                    current_bookings = 0
                item = {
                    'id': activity.id,
                    'title': activity.title,
                    'description': activity.description,
                    'location': activity.location,
                    'start_time': activity.start_time.isoformat().replace('+00:00', 'Z') if activity.start_time else None,
                    'end_time': activity.end_time.isoformat().replace('+00:00', 'Z') if activity.end_time else None,
                    'max_participants': activity.max_participants,
                    'current_participants': current_bookings,
                    'tags': getattr(activity, 'tags', None),
                    'status': activity.status,
                    'role': 'organizer',
                    'created_at': activity.created_at.isoformat().replace('+00:00', 'Z') if activity.created_at else None,
                    'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z') if activity.updated_at else None
                }
                result_list.append(item)

        if role in ['participant', 'all']:
            participant_query = ActivityBooking.query.filter_by(user_account=current_user.account)
            if status:
                participant_query = participant_query.join(Activity).filter(Activity.status == status)
            participant_bookings = participant_query.order_by(ActivityBooking.booking_time.desc()).all()

            for booking in participant_bookings:
                activity = Activity.query.get(booking.activity_id)
                if not activity:
                    continue
                if any(item['id'] == activity.id for item in result_list):
                    continue
                try:
                    current_bookings = ActivityBooking.query.filter_by(activity_id=activity.id, status='booked').count()
                except Exception:
                    current_bookings = 0
                item = {
                    'id': activity.id,
                    'title': activity.title,
                    'description': activity.description,
                    'location': activity.location,
                    'start_time': activity.start_time.isoformat().replace('+00:00', 'Z') if activity.start_time else None,
                    'end_time': activity.end_time.isoformat().replace('+00:00', 'Z') if activity.end_time else None,
                    'max_participants': activity.max_participants,
                    'current_participants': current_bookings,
                    'tags': getattr(activity, 'tags', None),
                    'status': activity.status,
                    'role': 'participant',
                    'booking_status': booking.status,
                    'booking_time': booking.booking_time.isoformat().replace('+00:00', 'Z') if booking.booking_time else None,
                    'created_at': activity.created_at.isoformat().replace('+00:00', 'Z') if activity.created_at else None,
                    'updated_at': activity.updated_at.isoformat().replace('+00:00', 'Z') if activity.updated_at else None
                }
                result_list.append(item)

        result_list.sort(key=lambda x: x.get('updated_at', ''), reverse=True)

        # 手动分页
        total = len(result_list)
        start = (page - 1) * size
        end = start + size
        paginated_data = result_list[start:end]

        return ResponseService.success({
            'total': total,
            'page': page,
            'size': size,
            'items': paginated_data
        }, message='我的活动列表查询成功')

    except Exception as e:
        return ResponseService.error(f'查询失败: {str(e)}', status_code=500)


@compat_bp.route('/upload/images', methods=['POST'])
@token_required
def alias_upload_images(current_user):
    """
    兼容旧前端路径：/api/upload/images
    支持多图上传，表单字段名可为 images (多个) 或 image (单个)
    """
    try:
        files = request.files.getlist('images') or []
        # 如果没有 images，尝试单文件字段 image
        if not files:
            single = request.files.get('image')
            if single:
                files = [single]

        if not files:
            return ResponseService.error('未获取到上传文件', status_code=400)

        storage = LocalImageStorage()
        results = []
        for f in files:
            save_result = storage.save_image(f)
            if save_result.get('status') != 'success':
                # 回滚已保存的文件（尝试删除）
                filename = save_result.get('filename')
                if filename:
                    storage.delete_image(filename)
                return ResponseService.error(f'上传失败：{save_result.get("message")}', status_code=400)

            # 创建附件记录
            attachment = Attachment(
                uploader_account=current_user.account,
                file_name=save_result.get('filename'),
                file_path=save_result.get('file_path'),
                file_size=save_result.get('file_size', 0),
                file_type=f.content_type or 'application/octet-stream',
                usage_type='attachment'
            )
            db.session.add(attachment)
            db.session.commit()

            results.append({
                'id': attachment.id,
                'file_name': attachment.file_name,
                'file_url': save_result.get('url'),
                'file_path': attachment.file_path
            })

        return ResponseService.success(data={'files': results}, message='上传成功')

    except Exception as e:
        db.session.rollback()
        return ResponseService.error(f'上传异常：{str(e)}', status_code=500)
