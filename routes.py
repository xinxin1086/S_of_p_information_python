from flask import Blueprint, request, jsonify
import jwt
from datetime import datetime, timedelta
from functools import wraps
from models import db, Admin
from config import Config

api = Blueprint('api', __name__)


# JWT验证装饰器（不变，新增令牌验证日志）
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        print(f"【接收所有请求头】{request.headers}")
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                print(f"【原始Authorization头】{auth_header}")
                token = auth_header.split(' ')[1]
                print(f"【接收令牌】token:  {repr(token)}")  # 打印令牌

        if not token:
            print("【令牌验证失败】缺少令牌")
            print(f"{request.headers}")
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
            current_user = Admin.query.get(payload['user_id'])
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
        except Exception as e:
            print(f"【令牌验证失败】错误: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'令牌无效：{str(e)}',
                'data': None
            }), 401

        return f(current_user, *args, **kwargs)

    return decorated


# 登录接口（新增接收/传出数据日志）
@api.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        account = data.get('account')
        password = data.get('password')

        # 打印接收的登录数据（密码脱敏）
        print(f"【接收登录数据】account: {account}, password: {password[:3]}***")

        if not account or not password:
            print("【登录失败】用户名或密码为空")
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空',
                'data': None
            }), 400

        user = Admin.query.filter_by(account=account).first()
        if not user or not user.check_password(password):
            print(f"【登录失败】用户名或密码错误，account: {account}")
            return jsonify({
                'success': False,
                'message': '用户名或密码错误',
                'data': None
            }), 401

        token = jwt.encode({
            'user_id': user.id,
            'account': user.account,
            'exp': datetime.utcnow() + timedelta(seconds=Config.JWT_EXPIRATION_DELTA)
        }, Config.JWT_SECRET_KEY, algorithm='HS256')

        # 打印传出的登录响应数据
        response_data = {
            'success': True,
            'message': '登录成功',
            'data': {
                'token': token,  # 令牌
                'user': {'id': user.id, 'account': user.account},
                'status': 'success'
            }
        }
        print(f"【传出登录响应】{response_data}")

        return jsonify(response_data), 200
    except Exception as e:
        print(f"【登录异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'登录失败：{str(e)}',
            'data': None
        }), 500


# 管理员信息查询接口（新增接收/传出数据日志）
@api.route('/admin/list', methods=['GET'])
@token_required
def get_admin_list(current_user):
    try:
        print(f"【接收查询请求】当前用户: {current_user.account}，查询所有管理员信息")

        admins = Admin.query.all()
        print(f"【查询结果】共找到 {len(admins)} 条管理员数据")

        data_list = []
        for admin in admins:
            admin_data = {
                'id': admin.id,
                'account': admin.account,
                'username': admin.username,
                'phone': admin.phone,
                'email': admin.email,
                'avatar': admin.avatar or '无',
                'role': admin.role
            }
            data_list.append(admin_data)
            print(f"【管理员数据】{admin_data}")  # 打印单条管理员数据

        # 打印传出的查询响应数据
        response_data = {
            'success': True,
            'message': '查询成功' if data_list else '无匹配数据',
            'data': {
                'fields': Admin.get_fields_info(),
                'items': data_list
            }
        }
        print(f"【传出查询响应】字段结构: {Admin.get_fields_info().keys()}, 数据条数: {len(data_list)}")

        return jsonify(response_data), 200
    except Exception as e:
        print(f"【查询异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500