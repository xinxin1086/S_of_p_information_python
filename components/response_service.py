# ./components/response_service.py

"""
通用API响应处理服务
提供统一的API响应格式、错误处理和用户信息获取功能
"""

from flask import jsonify, request
from typing import Dict, Any, Optional, Union, List
from functools import wraps
from .models import Admin, User
from datetime import datetime


class ResponseService:
    """统一API响应服务"""

    @staticmethod
    def success(data: Any = None, message: str = "操作成功", status_code: int = 200) -> tuple:
        """成功响应"""
        response = {
            'success': True,
            'message': message,
            'data': data
        }
        return jsonify(response), status_code

    @staticmethod
    def error(message: str, data: Any = None, status_code: int = 400, error_detail: str = None) -> tuple:
        """错误响应"""
        response = {
            'success': False,
            'message': message,
            'data': data
        }

        # 如果有详细错误信息，添加到响应中
        if error_detail:
            response['error'] = {
                'detail': error_detail
            }

        return jsonify(response), status_code

    @staticmethod
    def paginated_success(items: List[Any], total: int, page: int, size: int,
                        message: str = "查询成功", status_code: int = 200) -> tuple:
        """分页响应"""
        data = {
            'total': total,
            'page': page,
            'size': size,
            'items': items
        }
        return ResponseService.success(data=data, message=message, status_code=status_code)


class UserInfoService:
    """用户信息服务"""

    @staticmethod
    def get_user_by_account(account: str, include_sensitive: bool = False) -> Optional[Dict[str, Any]]:
        """
        根据账号获取用户信息

        Args:
            account: 用户账号
            include_sensitive: 是否包含敏感信息（phone, email）

        Returns:
            用户信息字典或None
        """
        # 先查普通用户表
        user = User.query.filter_by(account=account).first()
        if user:
            return UserInfoService._format_user_info(user, 'user', include_sensitive)

        # 再查管理员表
        admin = Admin.query.filter_by(account=account).first()
        if admin:
            return UserInfoService._format_user_info(admin, 'admin', include_sensitive)

        return None

    @staticmethod
    def get_current_user_info(current_user, include_sensitive: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取当前登录用户信息

        Args:
            current_user: 当前用户对象
            include_sensitive: 是否包含敏感信息

        Returns:
            用户信息字典或None
        """
        if not current_user:
            return None

        # 判断用户类型
        user = User.query.filter_by(account=current_user.account).first()
        if user:
            return UserInfoService._format_user_info(user, 'user', include_sensitive)

        admin = Admin.query.filter_by(account=current_user.account).first()
        if admin:
            return UserInfoService._format_user_info(admin, 'admin', include_sensitive)

        return None

    @staticmethod
    def _format_user_info(user_obj, user_type: str, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        格式化用户信息

        Args:
            user_obj: 用户对象（User或Admin）
            user_type: 用户类型 ('user' 或 'admin')
            include_sensitive: 是否包含敏感信息

        Returns:
            格式化的用户信息字典
        """
        base_info = {
            'id': user_obj.id,
            'account': user_obj.account,
            'username': user_obj.username,
            'avatar': user_obj.avatar,
            'role': user_obj.role,
            'user_type': user_type
        }

        # 根据用户类型设置角色中文名称
        if user_type == 'admin':
            role_mapping = {'ADMIN': '管理员', 'USER': '管理员用户'}
            base_info['role_cn'] = role_mapping.get(user_obj.role, user_obj.role)
        else:
            role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户'}
            base_info['role_cn'] = role_mapping.get(user_obj.role, user_obj.role)

        # 添加敏感信息（如果需要）
        if include_sensitive:
            base_info.update({
                'phone': getattr(user_obj, 'phone', None),
                'email': getattr(user_obj, 'email', None)
            })

        return base_info

    @staticmethod
    def get_multiple_user_info(accounts: List[str], include_sensitive: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        批量获取用户信息

        Args:
            accounts: 用户账号列表
            include_sensitive: 是否包含敏感信息

        Returns:
            账号到用户信息的映射字典
        """
        user_map = {}

        for account in accounts:
            user_info = UserInfoService.get_user_by_account(account, include_sensitive)
            if user_info:
                user_map[account] = user_info

        return user_map


def format_datetime(dt: datetime) -> str:
    """格式化时间为ISO字符串"""
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


def handle_api_exception(func):
    """API异常处理装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            return ResponseService.error(str(e), status_code=400)
        except PermissionError as e:
            return ResponseService.error(str(e), status_code=403)
        except FileNotFoundError as e:
            return ResponseService.error(str(e), status_code=404)
        except Exception as e:
            print(f"【API异常】{func.__name__}: {str(e)}")
            return ResponseService.error(f"服务器内部错误: {str(e)}", status_code=500)

    return wrapper


def validate_pagination_params(func):
    """分页参数验证装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 10))

            # 参数验证
            if page < 1:
                return ResponseService.error("页码必须大于0", status_code=400)
            if size < 1 or size > 100:
                return ResponseService.error("每页数量必须在1-100之间", status_code=400)

            return func(*args, **kwargs)
        except ValueError:
            return ResponseService.error("分页参数格式错误", status_code=400)

    return wrapper