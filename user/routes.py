# ./user/routes.py

from flask import request, jsonify
from user import user_bp  # 导入用户蓝图
from components import token_required, LocalImageStorage, db  # 引用公共工具
from components.models import User  # 导入用户模型
import jwt
from datetime import datetime, timedelta
from config import Config

# 用户登录接口
@user_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录功能
    接收参数: account, password, role(可选)
    返回: JWT token 和用户信息
    """
    try:
        data = request.get_json()

        # 验证必要参数
        if not data or 'account' not in data or 'password' not in data:
            return jsonify({
                'success': False,
                'message': '账号和密码不能为空',
                'data': None
            }), 400

        account = data['account'].strip()
        password = data['password'].strip()
        requested_role = data.get('role', '').strip()  # 可选的角色参数

        if not account or not password:
            return jsonify({
                'success': False,
                'message': '账号和密码不能为空',
                'data': None
            }), 400

        # 验证角色参数（如果提供）
        valid_roles = ['普通用户', '组织用户']
        if requested_role and requested_role not in valid_roles:
            return jsonify({
                'success': False,
                'message': '用户角色参数无效，应为"普通用户"或"组织用户"',
                'data': None
            }), 400

        # 查询用户
        user = User.query.filter_by(account=account).first()

        if not user:
            print(f"【登录失败】账号不存在: {account}")
            return jsonify({
                'success': False,
                'message': '账号不存在',
                'data': None
            }), 401

        # 验证密码
        if not user.check_password(password):
            print(f"【登录失败】密码错误: {account}")
            return jsonify({
                'success': False,
                'message': '密码错误',
                'data': None
            }), 401

        # 验证用户角色（如果请求中指定了角色）
        if requested_role:
            # 将数据库中的英文角色转换为中文显示进行验证
            role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户'}
            user_role_cn = role_mapping.get(user.role, user.role)

            if user_role_cn != requested_role:
                print(f"【登录失败】角色不匹配: 用户角色={user_role_cn}, 请求角色={requested_role}")
                return jsonify({
                    'success': False,
                    'message': f'用户角色不匹配，该账号为"{user_role_cn}"，无法以"{requested_role}"身份登录',
                    'data': None
                }), 401

        # 生成JWT token
        token_payload = {
            'user_id': user.id,
            'account': user.account,
            'role': user.role,  # 使用数据库中的原始角色（英文）
            'exp': datetime.utcnow() + timedelta(hours=24)  # 24小时过期
        }

        token = jwt.encode(
            token_payload,
            Config.JWT_SECRET_KEY,
            algorithm='HS256'
        )

        # 将角色转换为中文显示
        role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户'}
        role_cn = role_mapping.get(user.role, user.role)

        print(f"【登录成功】用户: {account}, 角色: {role_cn}")

        return jsonify({
            'success': True,
            'message': '登录成功',
            'data': {
                'token': token,
                'user': {
                    'id': user.id,
                    'account': user.account,
                    'username': user.username,
                    'phone': user.phone,
                    'email': user.email,
                    'avatar': user.avatar,
                    'role': user.role,  # 原始英文角色
                    'role_cn': role_cn  # 中文角色显示
                }
            }
        }), 200

    except Exception as e:
        print(f"【登录异常】{str(e)}")
        return jsonify({
            'success': False,
            'message': f'登录失败：{str(e)}',
            'data': None
        }), 500

# 用户注册接口
@user_bp.route('/register', methods=['POST'])
def register():
    """
    用户注册功能
    接收参数: account, username, password, phone, email(可选)
    返回: 注册结果
    """
    try:
        data = request.get_json()

        # 验证必要参数
        required_fields = ['account', 'username', 'password', 'phone']
        for field in required_fields:
            if field not in data or not data[field] or not str(data[field]).strip():
                return jsonify({
                    'success': False,
                    'message': f'{field}不能为空',
                    'data': None
                }), 400

        account = data['account'].strip()
        username = data['username'].strip()
        password = data['password'].strip()
        phone = data['phone'].strip()
        email = data.get('email', '').strip() if data.get('email') else None

        # 验证账号长度
        if len(account) < 3 or len(account) > 20:
            return jsonify({
                'success': False,
                'message': '账号长度应在3-20个字符之间',
                'data': None
            }), 400

        # 验证密码长度
        if len(password) < 6 or len(password) > 20:
            return jsonify({
                'success': False,
                'message': '密码长度应在6-20个字符之间',
                'data': None
            }), 400

        # 验证手机号格式
        if not phone.isdigit() or len(phone) != 11:
            return jsonify({
                'success': False,
                'message': '请输入正确的11位手机号',
                'data': None
            }), 400

        # 验证邮箱格式（如果提供）
        if email and '@' not in email:
            return jsonify({
                'success': False,
                'message': '请输入正确的邮箱格式',
                'data': None
            }), 400

        # 检查账号是否已存在
        if User.query.filter_by(account=account).first():
            return jsonify({
                'success': False,
                'message': '账号已存在',
                'data': None
            }), 400

        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            return jsonify({
                'success': False,
                'message': '用户名已存在',
                'data': None
            }), 400

        # 检查手机号是否已存在
        if User.query.filter_by(phone=phone).first():
            return jsonify({
                'success': False,
                'message': '手机号已存在',
                'data': None
            }), 400

        # 创建新用户
        new_user = User(
            account=account,
            username=username,
            phone=phone,
            email=email,
            role='USER'  # 注册时默认为普通用户
        )

        # 设置密码
        new_user.set_password(password)

        # 保存到数据库
        db.session.add(new_user)
        db.session.commit()

        # 将角色转换为中文显示
        role_mapping = {'USER': '普通用户', 'ORG_USER': '组织用户'}
        role_cn = role_mapping.get(new_user.role, new_user.role)

        print(f"【注册成功】新用户: {account}, 角色: {role_cn}")

        return jsonify({
            'success': True,
            'message': '注册成功',
            'data': {
                'user': {
                    'id': new_user.id,
                    'account': new_user.account,
                    'username': new_user.username,
                    'phone': new_user.phone,
                    'email': new_user.email,
                    'role': new_user.role,  # 原始英文角色
                    'role_cn': role_cn  # 中文角色显示
                }
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"【注册异常】{str(e)}")
        return jsonify({
            'success': False,
            'message': f'注册失败：{str(e)}',
            'data': None
        }), 500

# 用户信息接口（需登录）
@user_bp.route('/info', methods=['GET'])
@token_required
def get_user_info(current_user):
    try:
        # 此处可扩展用户业务逻辑
        return jsonify({
            'success': True,
            'message': '用户信息查询成功',
            'data': {
                'id': current_user.id,
                'account': current_user.account,
                'username': current_user.username,
                'phone': current_user.phone,
                'email': current_user.email,
                'avatar': current_user.avatar,
                'role': current_user.role
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500

# 用户更新个人信息接口（需登录）
@user_bp.route('/update', methods=['POST'])
@token_required
def update_user_info(current_user):
    try:
        data = request.get_json()
        update_kwargs = data.get('kwargs', {})

        if not update_kwargs:
            return jsonify({
                'success': False,
                'message': '缺少更新内容：kwargs',
                'data': None
            }), 400

        # 禁止修改账号
        update_kwargs.pop('account', None)

        # 处理头像更新
        if 'avatar' in update_kwargs:
            new_avatar = update_kwargs['avatar']
            if not new_avatar or new_avatar.strip() == '':
                if current_user.avatar:
                    filename = current_user.avatar.split('/')[-1]
                    LocalImageStorage().delete_image(filename)
                    print(f"【更新为空】删除旧头像：{filename}")
            else:
                if current_user.avatar:
                    filename = current_user.avatar.split('/')[-1]
                    LocalImageStorage().delete_image(filename)
                    print(f"【更新新头像】删除旧头像：{filename}")

        # 处理密码更新
        if 'password' in update_kwargs:
            new_password = update_kwargs.pop('password')
            if new_password and new_password.strip():
                current_user.set_password(new_password)
                print(f"【更新密码】用户ID: {current_user.id} 的密码已更新")

        # 更新其他字段
        updated_count = User.query.filter_by(id=current_user.id).update(update_kwargs)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'更新{updated_count}条用户记录',
            'data': {'updated_count': updated_count}
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【用户更新异常】{str(e)}")
        return jsonify({
            'success': False,
            'message': f'更新失败：{str(e)}',
            'data': None
        }), 500