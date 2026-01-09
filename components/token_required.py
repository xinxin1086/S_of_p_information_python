# ./components/token_required.py

import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import Config
from components.models import Admin ,User  # 引用公共模型
import logging

logger = logging.getLogger(__name__)

# JWT验证装饰器（管理员和用户模块共享）
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            logger.debug("------------")
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                # 使用repr以避免控制台编码引起的UnicodeEncodeError
                try:
                    logger.debug("【原始Authorization头】%s", repr(auth_header))
                except Exception:
                    logger.debug("【原始Authorization头】(内容无法显示)")
                token = auth_header.split(' ')[1]
                try:
                    logger.debug("【接收令牌】(redacted)")
                except Exception:
                    logger.debug("【接收令牌】(内容无法显示)")

        if not token:
            logger.debug(repr(request.headers))
            logger.warning("【令牌验证失败】缺少令牌")
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
            logger.debug("【令牌解码成功】payload: %s", repr(payload))
            # 根据角色查询对应的用户表
            current_user = None
            if payload.get('role') == 'admin':
                current_user = Admin.query.get(payload['user_id'])
            elif payload.get('role') == 'user':
                current_user = User.query.get(payload['user_id'])
            else:
                # 兼容旧逻辑，按顺序查找
                current_user = Admin.query.get(payload['user_id'])
                if not current_user:
                    current_user = User.query.get(payload['user_id'])

            if not current_user:
                raise Exception('用户不存在')
            logger.info("【验证通过】当前登录用户: %s (角色: %s)", current_user.account, payload.get('role', 'unknown'))
        except jwt.ExpiredSignatureError:
            logger.warning("【令牌验证失败】令牌已过期")
            return jsonify({
                'success': False,
                'message': '令牌已过期，请重新登录',
                'data': None
            }), 401
        except jwt.InvalidTokenError as e:
            logger.warning("【令牌验证失败】令牌格式错误: %s", str(e))
            return jsonify({
                'success': False,
                'message': '令牌格式无效，请重新登录',
                'data': None
            }), 401
        except Exception as e:
            logger.exception("【令牌验证失败】错误")
            return jsonify({
                'success': False,
                'message': f'令牌无效：{str(e)}',
                'data': None
            }), 401

        return f(current_user, *args, **kwargs)
    return decorated