from flask import jsonify
from user import user_bp  # 导入用户蓝图
from components import token_required  # 引用公共工具

# 示例：用户信息接口（需登录）
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
                'username': current_user.username
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500