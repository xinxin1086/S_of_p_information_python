# 用户信息公开访问接口

from flask import Blueprint, request
from components import db
from components.models import User, Admin
from components.response_service import ResponseService

# 创建用户信息公开访问模块蓝图
bp_user_public = Blueprint('user_public', __name__, url_prefix='/api/public/user')

# 公开的用户基础信息查询（无需登录）
@bp_user_public.route('/info', methods=['GET'])
def get_public_user_info():
    """
    获取用户基础信息（公开接口，无需认证）
    专门用于访客查看公开发布内容时的发布者信息显示

    参数：
    - account: 用户账号（必填）

    注意：此接口只返回基础信息，不包含电话、邮箱等隐私信息
    """
    try:
        # 获取用户账号参数
        account = request.args.get('account')
        if not account or not account.strip():
            return ResponseService.error('缺少参数：account', status_code=400)

        account = account.strip()

        # 查询目标用户（支持管理员和普通用户）
        target_user = None
        user_type = None

        # 先查普通用户表
        target_user = User.query.filter_by(account=account, is_deleted=0).first()
        if target_user:
            user_type = 'user'
        else:
            # 再查管理员表
            target_user = Admin.query.filter_by(account=account).first()
            if target_user:
                user_type = 'admin'

        if not target_user:
            return ResponseService.error('用户不存在', status_code=404)

        # 返回公开的基础信息（不包含敏感信息如电话、邮箱等）
        user_info = {
            'id': target_user.id,
            'account': target_user.account,
            'username': target_user.username,
            'avatar': target_user.avatar,
            'role': getattr(target_user, 'role', 'USER'),
            'user_type': user_type  # 标识是管理员还是普通用户
        }

        # 角色中文显示
        if user_type == 'admin':
            role_mapping = {'SUPER_ADMIN': '超级管理员', 'ADMIN': '管理员', 'USER': '管理员用户'}
            user_info['role_cn'] = role_mapping.get(getattr(target_user, 'role', 'USER'), '未知角色')
        else:
            role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户', 'ADMIN': '管理员用户'}
            user_info['role_cn'] = role_mapping.get(getattr(target_user, 'role', 'USER'), '未知角色')

        return ResponseService.success(data=user_info, message="用户信息查询成功")

    except Exception as e:
        return ResponseService.error(f'查询失败：{str(e)}', status_code=500)

# 批量查询用户基础信息（无需登录）
@bp_user_public.route('/info/batch', methods=['POST'])
def get_batch_public_user_info():
    """
    批量获取用户基础信息（公开接口，无需认证）
    专门用于批量查询用户信息

    请求参数：
    {
        "accounts": ["user1", "user2", "admin1"]
    }
    """
    try:
        data = request.get_json()
        if not data or 'accounts' not in data:
            return ResponseService.error('缺少参数：accounts', status_code=400)

        accounts = data.get('accounts', [])
        if not isinstance(accounts, list):
            return ResponseService.error('accounts参数必须是数组', status_code=400)

        if not accounts:
            return ResponseService.success(data=[], message="用户列表为空")

        # 去重
        accounts = list(set(account.strip() for account in accounts if account.strip()))

        result = []
        for account in accounts:
            # 查询目标用户
            target_user = None
            user_type = None

            # 先查普通用户表
            target_user = User.query.filter_by(account=account, is_deleted=0).first()
            if target_user:
                user_type = 'user'
            else:
                # 再查管理员表
                target_user = Admin.query.filter_by(account=account).first()
                if target_user:
                    user_type = 'admin'

            if target_user:
                user_info = {
                    'id': target_user.id,
                    'account': target_user.account,
                    'username': target_user.username,
                    'avatar': target_user.avatar,
                    'role': getattr(target_user, 'role', 'USER'),
                    'user_type': user_type
                }

                # 角色中文显示
                if user_type == 'admin':
                    role_mapping = {'SUPER_ADMIN': '超级管理员', 'ADMIN': '管理员', 'USER': '管理员用户'}
                    user_info['role_cn'] = role_mapping.get(getattr(target_user, 'role', 'USER'), '未知角色')
                else:
                    role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户', 'ADMIN': '管理员用户'}
                    user_info['role_cn'] = role_mapping.get(getattr(target_user, 'role', 'USER'), '未知角色')

                result.append(user_info)

        return ResponseService.success(data=result, message=f"批量查询成功，找到 {len(result)} 个用户")

    except Exception as e:
        return ResponseService.error(f'批量查询失败：{str(e)}', status_code=500)

# 公开的用户统计信息（无需登录）
@bp_user_public.route('/statistics', methods=['GET'])
def get_public_user_statistics():
    """
    获取用户统计信息（公开接口，无需登录）
    """
    try:
        from sqlalchemy import func

        # 普通用户统计
        from sqlalchemy import case

        user_stats = db.session.query(
            func.count(User.id).label('total_users'),
            func.sum(case((User.is_deleted == 0, 1), else_=0)).label('active_users'),
            func.sum(case((User.is_deleted == 1, 1), else_=0)).label('deleted_users')
        ).first()

        # 管理员统计
        admin_stats = db.session.query(
            func.count(Admin.id).label('total_admins'),
            func.sum(case((Admin.role == 'SUPER_ADMIN', 1), else_=0)).label('super_admins'),
            func.sum(case((Admin.role == 'ADMIN', 1), else_=0)).label('regular_admins')
        ).first()

        statistics = {
            'user_statistics': {
                'total_users': int(user_stats.total_users or 0),
                'active_users': int(user_stats.active_users or 0),
                'deleted_users': int(user_stats.deleted_users or 0)
            },
            'admin_statistics': {
                'total_admins': int(admin_stats.total_admins or 0),
                'super_admins': int(admin_stats.super_admins or 0),
                'regular_admins': int(admin_stats.regular_admins or 0)
            }
        }

        return ResponseService.success(data=statistics, message="用户统计查询成功")

    except Exception as e:
        return ResponseService.error(f'统计查询失败：{str(e)}', status_code=500)

print("【API_user 公开访问接口模块加载完成】")