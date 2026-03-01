

from flask import jsonify, request
from typing import Dict, Any, Optional, Union, List
from functools import wraps
from .models import Admin, User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ResponseService:
    

    @staticmethod
    def success(data: Any = None, message: str = "操作成功", status_code: int = 200) -> tuple:
        
        response = {
            'success': True,
            'message': message,
            'data': data
        }
        return jsonify(response), status_code

    @staticmethod
    def error(message: str, data: Any = None, status_code: int = 400, error_detail: str = None) -> tuple:
        
        response = {
            'success': False,
            'message': message,
            'data': data
        }

        if error_detail:
            response['error'] = {
                'detail': error_detail
            }

        return jsonify(response), status_code

    @staticmethod
    def paginated_success(items: List[Any], total: int, page: int, size: int,
                        message: str = "查询成功", status_code: int = 200) -> tuple:
        
        data = {
            'total': total,
            'page': page,
            'size': size,
            'items': items
        }
        return ResponseService.success(data=data, message=message, status_code=status_code)


class UserInfoService:
    

    @staticmethod
    def get_user_by_account(account: str, include_sensitive: bool = False) -> Optional[Dict[str, Any]]:
        
        user = User.query.filter_by(account=account).first()
        if user:
            return UserInfoService._format_user_info(user, 'user', include_sensitive)

        admin = Admin.query.filter_by(account=account).first()
        if admin:
            return UserInfoService._format_user_info(admin, 'admin', include_sensitive)

        return None

    @staticmethod
    def get_current_user_info(current_user, include_sensitive: bool = True) -> Optional[Dict[str, Any]]:
        
        if not current_user:
            return None

        user = User.query.filter_by(account=current_user.account).first()
        if user:
            return UserInfoService._format_user_info(user, 'user', include_sensitive)

        admin = Admin.query.filter_by(account=current_user.account).first()
        if admin:
            return UserInfoService._format_user_info(admin, 'admin', include_sensitive)

        return None

    @staticmethod
    def _format_user_info(user_obj, user_type: str, include_sensitive: bool = False) -> Dict[str, Any]:
        
        base_info = {
            'id': user_obj.id,
            'account': user_obj.account,
            'username': user_obj.username,
            'avatar': user_obj.avatar,
            'role': user_obj.role,
            'user_type': user_type
        }

        if user_type == 'admin':
            role_mapping = {'ADMIN': '管理员', 'USER': '管理员用户'}
            base_info['role_cn'] = role_mapping.get(user_obj.role, user_obj.role)
        else:
            role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户'}
            base_info['role_cn'] = role_mapping.get(user_obj.role, user_obj.role)

        if include_sensitive:
            base_info.update({
                'phone': getattr(user_obj, 'phone', None),
                'email': getattr(user_obj, 'email', None)
            })

        return base_info

    @staticmethod
    def get_multiple_user_info(accounts: List[str], include_sensitive: bool = False) -> Dict[str, Dict[str, Any]]:
        
        user_map = {}

        for account in accounts:
            user_info = UserInfoService.get_user_by_account(account, include_sensitive)
            if user_info:
                user_map[account] = user_info

        return user_map


def format_datetime(dt: datetime) -> str:
    
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


def handle_api_exception(func):
    
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
            logger.exception("【API异常】%s: %s", func.__name__, str(e))
            return ResponseService.error(f"服务器内部错误: {str(e)}", status_code=500)

    return wrapper


def validate_pagination_params(func):
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 10))

            if page < 1:
                return ResponseService.error("页码必须大于0", status_code=400)
            if size < 1 or size > 100:
                return ResponseService.error("每页数量必须在1-100之间", status_code=400)

            return func(*args, **kwargs)
        except ValueError:
            return ResponseService.error("分页参数格式错误", status_code=400)

    return wrapper