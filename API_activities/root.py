from flask import Blueprint, request
from components import db, token_required
from components.models import Activity
from components.response_service import ResponseService
from datetime import datetime, timezone

root_bp = Blueprint('api_activities_root', __name__, url_prefix='/api/activities')


@root_bp.route('', methods=['POST'])
@root_bp.route('/', methods=['POST'])
@token_required
def create_activity_public(current_user):
    """
    前端创建活动兼容接口：POST /api/activities
    允许已登录用户创建活动（组织者为当前用户）
    """
    try:
        # 先打印原始请求体，以诊断JSON问题
        raw_data = request.get_data(as_text=True)
        print(f"【原始请求体】{repr(raw_data)}")
        
        data = request.get_json(force=True, silent=False)
        print(f"【创建活动请求】用户: {current_user.account}, 请求数据: {data}")
        if not data:
            return ResponseService.error('请求数据不能为空', status_code=400)

        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        location = data.get('location', '').strip()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        max_participants = data.get('max_participants')
        tags = data.get('tags', [])
        status = data.get('status', 'draft')
        print(f"【解析参数】title={title}, start_time={start_time}, end_time={end_time}, max_participants={max_participants}")

        # 权限检查：仅允许组织用户或管理员创建
        role = (getattr(current_user, 'role', '') or '').upper()
        print(f"【权限检查】用户角色: {role}")
        if role not in ('ORG_USER', 'ADMIN', 'SUPER_ADMIN'):
            return ResponseService.error('仅组织者或管理员可以创建活动', status_code=403)
        print(f"【权限验证通过】")

        # 验证必填字段
        if not title:
            return ResponseService.error('活动标题不能为空', status_code=400)
        if not start_time or not end_time:
            return ResponseService.error('活动时间不能为空', status_code=400)
        if max_participants is None:
            return ResponseService.error('最大参与人数不能为空', status_code=400)

        print(f"【必填字段验证通过】")
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        print(f"【时间解析成功】start_dt={start_dt}, end_dt={end_dt}")
        if start_dt >= end_dt:
            return ResponseService.error('活动开始时间必须早于结束时间', status_code=400)

        # 使用 UTC 时间进行比较（避免 naive vs aware datetime 冲突）
        now_utc = datetime.now(timezone.utc)
        if start_dt < now_utc:
            print(f"【时间验证失败】start_dt={start_dt} < now_utc={now_utc}")
            return ResponseService.error('活动开始时间不能早于当前时间', status_code=400)

        valid_statuses = ['draft', 'published']
        if status not in valid_statuses:
            return ResponseService.error(f'无效的活动状态，支持的值: {", ".join(valid_statuses)}', status_code=400)

        print(f"【活动数据验证通过】")
        activity = Activity(
            title=title,
            description=description,
            location=location,
            start_time=start_dt,
            end_time=end_dt,
            max_participants=int(max_participants) if max_participants else None,
            organizer_user_id=current_user.id,
            organizer_display=current_user.username,
            tags=tags if tags else [],
            status=status
        )

        db.session.add(activity)
        db.session.commit()
        print(f"【活动创建成功】活动ID: {activity.id}")

        activity_data = {
            'id': activity.id,
            'title': activity.title,
            'description': activity.description,
            'location': activity.location,
            'start_time': activity.start_time.isoformat().replace('+00:00', 'Z'),
            'end_time': activity.end_time.isoformat().replace('+00:00', 'Z'),
            'max_participants': activity.max_participants,
            'current_participants': 0,
            'tags': activity.tags or [],
            'status': activity.status,
            'organizer_display': activity.organizer_display,
            'created_at': activity.created_at.isoformat().replace('+00:00', 'Z')
        }

        return ResponseService.success(data=activity_data, message='活动创建成功')

    except Exception as e:
        print(f"【活动创建异常】错误类型: {type(e).__name__}, 错误信息: {str(e)}")
        import traceback
        print(f"【错误堆栈】{traceback.format_exc()}")
        db.session.rollback()
        return ResponseService.error(f'活动创建失败: {str(e)}', status_code=500)
