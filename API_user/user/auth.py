# API_user 用户端认证接口
# 用户个人信息相关的认证操作

from flask import request
from components import token_required, db, LocalImageStorage
from components.models import User, Admin
from components.response_service import ResponseService, UserInfoService, handle_api_exception
from . import user_bp
from ..common.utils import UserDataProcessor, UserValidator

@user_bp.route('/avatar', methods=['POST'])
@token_required
def upload_avatar(current_user):
    """
    用户头像上传接口
    支持用户和管理员上传头像
    自动删除旧头像
    """
    try:
        print(f"【头像上传请求】用户: {current_user.account}")
        avatar_file = request.files.get('avatar')

        if not avatar_file:
            return ResponseService.error('缺少头像文件', status_code=400)

        # 确定当前用户类型和记录
        target_user = None
        target_user_type = None

        target_user = User.query.filter_by(account=current_user.account).first()
        if target_user:
            target_user_type = 'user'
        else:
            target_user = Admin.query.filter_by(account=current_user.account).first()
            if target_user:
                target_user_type = 'admin'

        if not target_user:
            return ResponseService.error('用户信息不存在', status_code=404)

        # 删除旧头像
        if target_user.avatar:
            old_filename = target_user.avatar.split('/')[-1]
            LocalImageStorage().delete_image(old_filename)
            print(f"【上传新头像】删除旧头像：{old_filename}")

        # 保存新头像
        image_storage = LocalImageStorage()
        save_result = image_storage.save_image(avatar_file)

        if save_result['status'] != 'success':
            return ResponseService.error(f'图片上传失败：{save_result["message"]}', status_code=400)

        # 更新头像URL
        target_user.avatar = save_result['url']
        db.session.commit()

        print(f"【头像上传成功】用户: {current_user.account}, 新头像URL: {save_result['url']}")

        return ResponseService.success(
            data={
                'avatar_url': save_result['url'],
                'filename': save_result['filename']
            },
            message='头像上传成功（旧头像已删除）'
        )

    except Exception as e:
        db.session.rollback()
        print(f"【头像上传异常】错误: {str(e)}")
        return ResponseService.error(f'头像上传失败：{str(e)}', status_code=500)

@user_bp.route('/avatar', methods=['DELETE'])
@token_required
def delete_avatar(current_user):
    """
    删除用户头像接口
    """
    try:
        print(f"【头像删除请求】用户: {current_user.account}")

        # 确定当前用户类型和记录
        target_user = None

        target_user = User.query.filter_by(account=current_user.account).first()
        if not target_user:
            target_user = Admin.query.filter_by(account=current_user.account).first()

        if not target_user:
            return ResponseService.error('用户信息不存在', status_code=404)

        # 删除头像文件和数据库记录
        if target_user.avatar:
            filename = target_user.avatar.split('/')[-1]
            LocalImageStorage().delete_image(filename)
            print(f"【删除头像文件】用户: {target_user.account}, 文件: {filename}")

            target_user.avatar = None
            db.session.commit()

        return ResponseService.success(message='头像删除成功')

    except Exception as e:
        db.session.rollback()
        print(f"【头像删除异常】错误: {str(e)}")
        return ResponseService.error(f'头像删除失败：{str(e)}', status_code=500)

print("【API_user 用户端认证接口模块加载完成】")