from flask import request, jsonify
from components import token_required, LocalImageStorage  # 通用验证+图片工具类
from common import common_bp

# 公共图片上传接口（所有登录用户均可调用：管理员+普通用户）
@common_bp.route('/upload/image', methods=['POST'])
@token_required  # 仅登录用户可访问（验证JWT令牌）
def upload_image(current_user):
    try:
        print(f"【图片上传请求】用户: {current_user.account}")
        # 获取前端传递的文件（name必须为"image"）
        file = request.files.get('image')
        if not file:
            return jsonify({'success': False, 'message': '未获取到上传文件', 'data': None}), 400

        # 实例化图片存储工具类（读取全局配置）
        image_storage = LocalImageStorage()
        save_result = image_storage.save_image(file)

        if save_result['status'] == 'success':
            print(f"【图片上传成功】URL: {save_result['url']}, 文件名: {save_result['filename']}")
            return jsonify({
                'success': True,
                'message': '图片上传成功',
                'data': {
                    'image_url': save_result['url'],  # 前端展示/数据库存储用
                    'filename': save_result['filename'],  # 后续删除图片用
                    'file_path': save_result['file_path']  # 本地存储路径（可选）
                }
            }), 200
        else:
            print(f"【图片上传失败】原因: {save_result['message']}")
            return jsonify({
                'success': False,
                'message': f'上传失败：{save_result["message"]}',
                'data': None
            }), 400

    except Exception as e:
        print(f"【图片上传异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'上传异常：{str(e)}',
            'data': None
        }), 500

# 公共图片删除接口（所有登录用户均可调用）
@common_bp.route('/delete/image', methods=['POST'])
@token_required
def delete_image(current_user):
    try:
        data = request.get_json()
        filename = data.get('filename')  # 前端传递上传时返回的"filename"
        image_url = data.get('image_url')  # 可选：前端也可传递image_url，后端解析文件名

        # 优先使用filename，若无则从image_url中解析
        if not filename and image_url:
            # 从URL中提取文件名（URL格式：/static/images/20251116-xxx.png）
            filename = image_url.split('/')[-1]
            print(f"【解析图片文件名】从URL提取: {filename}")

        if not filename:
            return jsonify({'success': False, 'message': '缺少文件名（filename）或图片URL（image_url）', 'data': None}), 400

        # 调用工具类删除本地图片
        image_storage = LocalImageStorage()
        delete_result = image_storage.delete_image(filename)

        if delete_result['status'] == 'success':
            return jsonify({'success': True, 'message': '图片删除成功', 'data': None}), 200
        else:
            return jsonify({'success': False, 'message': delete_result['message'], 'data': None}), 400

    except Exception as e:
        print(f"【图片删除异常】错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除异常：{str(e)}',
            'data': None
        }), 500