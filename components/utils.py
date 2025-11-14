import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import Config
from components.models import Admin  # 引用公共模型

# JWT验证装饰器（管理员和用户模块共享）
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            # print(f"{request.headers}")
            print("------------")
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                print(f"【原始Authorization头】{auth_header}")
                token = auth_header.split(' ')[1]
                print(f"【接收令牌】token: {token}")

        if not token:
            print(f"{request.headers}")
            print("【令牌验证失败】缺少令牌")
            return jsonify({
                'success': False,
                'message': '缺少令牌，请先登录',
                'data': None
            }), 401

        try:
            payload = jwt.decode(
                token,
                Config.JWT_SECRET_KEY,
                algorithms=['HS256']
            )
            print(f"【令牌解码成功】payload: {payload}")
            # 验证用户存在（管理员/用户通用）
            current_user = Admin.query.get(payload['user_id'])  # 若用户模块需单独验证，可扩展
            if not current_user:
                raise Exception('用户不存在')
            print(f"【验证通过】当前登录用户: {current_user.account}")
        except jwt.ExpiredSignatureError:
            print("【令牌验证失败】令牌已过期")
            return jsonify({
                'success': False,
                'message': '令牌已过期，请重新登录',
                'data': None
            }), 401
        except jwt.InvalidTokenError as e:
            print(f"【令牌验证失败】令牌格式错误: {str(e)}")
            return jsonify({
                'success': False,
                'message': '令牌格式无效，请重新登录',
                'data': None
            }), 401
        except Exception as e:
            print(f"【令牌验证失败】错误: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'令牌无效：{str(e)}',
                'data': None
            }), 401

        return f(current_user, *args, **kwargs)
    return decorated