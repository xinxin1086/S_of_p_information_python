from flask import request, jsonify
from components import token_required, LocalImageStorage, db  # 新增db导入
from components.models import Admin, User  # 导入模型
from common import common_bp
from sqlalchemy.exc import SQLAlchemyError  # 导入SQLAlchemy的错误处理

# 原有公共图片上传接口（保持不变）
@common_bp.route('/upload/image', methods=['POST'])
@token_required
def upload_image(current_user):
    try:
        print(f"【图片上传请求】用户: {current_user.account}")
        file = request.files.get('image')
        if not file:
            return jsonify({'success': False, 'message': '未获取到上传文件', 'data': None}), 400

        image_storage = LocalImageStorage()
        save_result = image_storage.save_image(file)

        if save_result['status'] != 'success':
            print(f"【图片上传失败】原因: {save_result['message']}")
            return jsonify({
                'success': False,
                'message': f'上传失败：{save_result["message"]}',
                'data': None
            }), 400

        print(f"【图片上传成功】URL: {save_result['url']}, 文件名: {save_result['filename']}")
        return jsonify({
            'success': True,
            'message': '图片上传成功',
            'data': {
                'image_url': save_result['url'],
                'filename': save_result['filename'],
                'file_path': save_result['file_path']
            }
        }), 200

    except Exception as e:
        print(f"【图片上传异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'上传异常：{str(e)}',
            'data': None
        }), 500


# 原有公共图片删除接口（保持不变）
@common_bp.route('/delete/image', methods=['POST'])
@token_required
def delete_image(current_user):
    try:
        data = request.get_json()
        filename = data.get('filename')
        image_url = data.get('image_url')

        # 提取文件名
        if not filename and image_url:
            filename = image_url.rsplit('/', 1)[-1]  # 使用rsplit以避免URL末尾斜杠的问题

        if not filename:
            return jsonify({'success': False, 'message': '缺少文件名（filename）或图片URL（image_url）', 'data': None}), 400

        image_storage = LocalImageStorage()
        delete_result = image_storage.delete_image(filename)

        if delete_result['status'] != 'success':
            print(f"【图片删除失败】原因: {delete_result['message']}")
            return jsonify({'success': False, 'message': delete_result['message'], 'data': None}), 400

        return jsonify({'success': True, 'message': '图片删除成功', 'data': None}), 200

    except Exception as e:
        print(f"【图片删除异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除异常：{str(e)}',
            'data': None
        }), 500


# 头像上传接口（仅用户创建成功后调用）
@common_bp.route('/upload/avatar', methods=['POST'])
@token_required
def upload_user_avatar(current_user):
    try:
        print(f"【头像上传请求】用户: {current_user.account}")
        # 接收前端参数：表名、记录ID、图片文件
        table_name = request.form.get('table_name')  # 必选：admin_info / user_info
        record_id = request.form.get('record_id')    # 必选：创建成功返回的ID
        avatar_file = request.files.get('avatar')    # 必选：头像文件

        # 参数校验
        if not table_name or not record_id or not avatar_file:
            return jsonify({
                'success': False,
                'message': '缺少参数：table_name、record_id或avatar文件',
                'data': None
            }), 400

        # 映射表名到模型
        supported_tables = {'admin_info': Admin, 'user_info': User}
        if table_name not in supported_tables:
            return jsonify({
                'success': False,
                'message': f'不支持的表：{table_name}，仅允许admin_info或user_info',
                'data': None
            }), 400
        model = supported_tables[table_name]

        # 校验记录是否存在（确保用户已创建）
        record = model.query.get(int(record_id))
        if not record:
            return jsonify({
                'success': False,
                'message': f'ID为{record_id}的{table_name}记录不存在，无法上传头像',
                'data': None
            }), 404

        # 保存图片并生成URL
        image_storage = LocalImageStorage()
        save_result = image_storage.save_image(avatar_file)
        if save_result['status'] != 'success':
            return jsonify({
                'success': False,
                'message': f'图片上传失败：{save_result["message"]}',
                'data': None
            }), 400

        # 更新数据库的avatar字段
        record.avatar = save_result['url']
        db.session.commit()
        print(f"【头像上传成功】{table_name} ID: {record_id}, 头像URL: {save_result['url']}")

        return jsonify({
            'success': True,
            'message': '头像上传并关联成功',
            'data': {
                'avatar_url': save_result['url'],
                'filename': save_result['filename']
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"【头像上传异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'头像上传失败：{str(e)}',
            'data': None
        }), 500