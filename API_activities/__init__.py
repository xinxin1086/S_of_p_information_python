# API_activities 模块初始化文件
# 所有路由和工具类已整合到 routes.py 文件中

from flask import Blueprint

# 创建主蓝图，URL前缀为 /api/activities
api_activities_bp = Blueprint('api_activities', __name__, url_prefix='/api/activities')

def register_api_activities_blueprints(app):
    """
    注册 API_activities 模块的所有蓝图

    Args:
        app: Flask应用实例
    """
    # 从 routes.py 导入所有蓝图
    from .routes import (
        root_bp,
        user_ops_bp,
        admin_manage_bp,
        booking_bp,
        discussion_bp,
        bp_activities_public
    )

    # 注册所有蓝图到Flask应用
    app.register_blueprint(root_bp)
    app.register_blueprint(user_ops_bp)
    app.register_blueprint(admin_manage_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(discussion_bp)
    app.register_blueprint(bp_activities_public)

    print("【API_activities模块】所有蓝图注册完成")
    print("  - 根路由模块: /api/activities (活动创建)")
    print("  - 用户操作模块: /api/activities/user/*")
    print("  - 管理员模块: /api/activities/admin/*")
    print("  - 预约模块: /api/activities/booking/*")
    print("  - 讨论模块: /api/activities/discussion/*")
    print("  - 公开访问模块: /api/public/activities/*")

# 路由映射信息（用于文档和测试）
ROUTES_MAPPING = {
    'root': {
        'module': 'routes (原 root.py)',
        'description': '公开活动创建接口',
        'routes': [
            'POST   /api/activities                  - 创建活动'
        ]
    },
    'user_ops': {
        'module': 'routes (原 user/user_ops.py)',
        'description': '用户端活动操作（预约、评分、讨论）',
        'routes': [
            'POST   /api/activities/user/activities/{id}/booking              - 用户预约活动',
            'DELETE /api/activities/user/activities/{id}/booking              - 用户取消预约',
            'GET    /api/activities/user/bookings                             - 获取用户预约列表',
            'POST   /api/activities/user/activities/{id}/rating               - 用户为活动评分',
            'PUT    /api/activities/user/activities/{id}/rating               - 用户更新评分',
            'DELETE /api/activities/user/activities/{id}/rating               - 用户删除评分',
            'GET    /api/activities/user/ratings                              - 获取用户评分列表',
            'POST   /api/activities/user/activities/{id}/discussions          - 用户创建讨论',
            'PUT    /api/activities/user/discussions/{id}                     - 用户更新讨论',
            'DELETE /api/activities/user/discussions/{id}                     - 用户删除讨论',
            'GET    /api/activities/user/my-activities                        - 获取用户活动列表'
        ]
    },
    'admin_manage': {
        'module': 'routes (原 admin/activity_manage.py)',
        'description': '管理员活动管理（CRUD、审核预约）',
        'routes': [
            'POST   /api/activities/admin/activities                          - 管理员创建活动',
            'PUT    /api/activities/admin/activities/{id}                     - 管理员更新活动',
            'DELETE /api/activities/admin/activities/{id}                     - 管理员删除活动',
            'GET    /api/activities/admin/activities                          - 管理员获取活动列表',
            'GET    /api/activities/admin/activities/{id}                     - 管理员获取活动详情',
            'GET    /api/activities/admin/activities/{id}/bookings            - 管理员获取预约列表',
            'PUT    /api/activities/admin/activities/{id}/bookings/{bid}/status - 管理员更新预约状态',
            'POST   /api/activities/admin/activities/{id}/bookings/batch      - 管理员批量操作预约',
            'GET    /api/activities/admin/activities/{id}/statistics          - 管理员获取活动统计',
            'GET    /api/activities/admin/activities/summary                  - 管理员获取活动汇总'
        ]
    },
    'booking': {
        'module': 'routes (原 booking/booking.py)',
        'description': '预约专门接口（独立拆分）',
        'routes': [
            'POST   /api/activities/booking/activities/{id}/book              - 创建预约',
            'DELETE /api/activities/booking/activities/{id}/cancel            - 取消预约',
            'GET    /api/activities/booking/activities/{id}/bookings          - 获取活动预约列表',
            'GET    /api/activities/booking/my-bookings                       - 获取用户预约列表',
            'PUT    /api/activities/booking/bookings/{id}/status              - 更新预约状态',
            'POST   /api/activities/booking/activities/{id}/bookings/batch    - 批量操作预约',
            'GET    /api/activities/booking/activities/{id}/bookings/statistics - 预约统计',
            'GET    /api/activities/booking/activities/{id}/availability      - 检查可用性',
            'GET    /api/activities/booking/bookings/{id}                     - 获取预约详情',
            'DELETE /api/activities/booking/bookings/{id}                     - 删除预约记录',
            'GET    /api/activities/booking/activities/{id}/export/bookings   - 导出预约列表'
        ]
    },
    'discussion': {
        'module': 'routes (原 discussion/discuss.py)',
        'description': '讨论评论专门接口',
        'routes': [
            'POST   /api/activities/discussion/activities/{id}/discussions    - 创建讨论',
            'GET    /api/activities/discussion/activities/{id}/discussions    - 获取讨论列表',
            'GET    /api/activities/discussion/discussions/{id}               - 获取讨论详情',
            'PUT    /api/activities/discussion/discussions/{id}               - 更新讨论',
            'DELETE /api/activities/discussion/discussions/{id}               - 删除讨论',
            'POST   /api/activities/discussion/discussions/{id}/comments      - 创建留言',
            'GET    /api/activities/discussion/discussions/{id}/comments      - 获取留言列表',
            'GET    /api/activities/discussion/discussions/{id}/comments/nested - 获取嵌套留言',
            'PUT    /api/activities/discussion/comments/{id}                  - 更新留言',
            'DELETE /api/activities/discussion/comments/{id}                  - 删除留言',
            'GET    /api/activities/discussion/activities/{id}/discussions/search - 搜索讨论',
            'PUT    /api/activities/discussion/discussions/{id}/pin           - 置顶讨论',
            'GET    /api/activities/discussion/discussions/statistics         - 讨论统计'
        ]
    },
    'public': {
        'module': 'routes (原 public/activity.py)',
        'description': '活动公开访问接口（无需认证）',
        'routes': [
            'GET    /api/public/activities/activities                        - 获取活动列表',
            'GET    /api/public/activities/activities/{id}                   - 获取活动详情',
            'GET    /api/public/activities/activities/statistics             - 获取活动统计'
        ]
    }
}

def get_routes_info():
    """
    获取所有路由信息（用于文档生成）

    Returns:
        dict: 路由信息映射
    """
    return ROUTES_MAPPING

def print_routes_info():
    """
    打印所有路由信息（用于调试）
    """
    print("\n=== API_activities 模块路由信息 ===")
    for module_name, info in ROUTES_MAPPING.items():
        print(f"\n【{module_name}】{info['description']}")
        print(f"模块: {info['module']}")
        for route in info['routes']:
            print(f"  {route}")
    print("=" * 50)
