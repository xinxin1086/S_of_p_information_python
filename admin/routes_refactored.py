# admin/routes_refactored.py
# 重构后的管理员路由接口

from flask import request, jsonify
from components import token_required
from admin import admin_bp
from .services.operation_service import OperationService


# 初始化操作服务
operation_service = OperationService()


# 管理员数据增删改查接口（重构版本 - 使用服务类）
@admin_bp.route('/operate_refactored', methods=['POST'])
@token_required
def db_operate_refactored(current_user):
    """重构后的管理员数据操作接口，使用服务类进行模块化处理"""
    try:
        data = request.get_json()
        print(f"【接收操作请求】用户: {current_user.account}, 参数: {data}")

        # 验证必填参数
        required = ['table_name', 'operate_type']
        for param in required:
            if param not in data:
                return jsonify({
                    'success': False,
                    'message': f'缺少参数：{param}',
                    'data': None
                }), 400

        # 执行操作
        result = operation_service.execute_operation(current_user, data)

        return jsonify({
            'success': True,
            'message': result.get('message', '操作成功'),
            'data': result
        }), 200

    except Exception as e:
        print(f"【操作异常】{str(e)}")
        return jsonify({
            'success': False,
            'message': f'操作失败：{str(e)}',
            'data': None
        }), 500


# 管理员数据操作接口（重构版本，保留原路径用于逐步迁移）
@admin_bp.route('/operate', methods=['POST'])
@token_required
def db_operate_new(current_user):
    """新的管理员数据操作接口，使用模块化服务类处理"""
    return db_operate_refactored(current_user)