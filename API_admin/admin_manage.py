# API_admin 管理员管理接口
from flask import request
from components.response_service import ResponseService
from components.models import Admin
from API_admin.common.utils import admin_required, log_admin_operation
from API_admin import bp_admin


@bp_admin.route('/list', methods=['GET'])
@admin_required
def list_admins(current_user=None, **kwargs):
    """
    获取管理员列表
    需要管理员权限
    """
    try:
        keyword = request.args.get('keyword', '').strip()
        role = request.args.get('role', '').strip()

        query = Admin.query
        if keyword:
            # 支持账号/姓名/邮箱/手机号模糊查询
            like_kw = f"%{keyword}%"
            query = query.filter(
                (Admin.account.like(like_kw)) |
                (Admin.username.like(like_kw)) |
                (Admin.email.like(like_kw)) |
                (Admin.phone.like(like_kw))
            )
        if role:
            query = query.filter(Admin.role == role)

        admins = query.order_by(Admin.created_at.desc()).all()

        items = []
        for admin in admins:
            items.append({
                'id': admin.id,
                'account': admin.account,
                'username': admin.username,
                'phone': admin.phone or '',
                'email': admin.email or '',
                'avatar': admin.avatar or '',
                'role': admin.role
            })

        log_admin_operation(
            current_user,
            'VIEW',
            'admin_info',
            details={
                'keyword': keyword,
                'role': role,
                'result_count': len(items)
            }
        )

        return ResponseService.success(
            data={
                'fields': Admin.get_fields_info(),
                'items': items,
                'total': len(items)
            },
            message='查询成功' if items else '暂无数据'
        )
    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

