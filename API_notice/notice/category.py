
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from components import db, token_required
import logging

logger = logging.getLogger(__name__)
from components.models.notice_models import Notice, NoticeAttachment
from components.models.user_models import Admin
from API_notice.common.utils import NoticePermissionUtils, NoticeQueryUtils


def admin_required(f):
    
    def decorated_function(current_user, *args, **kwargs):
        current_admin = Admin.query.filter_by(account=current_user.account).first()
        if not current_admin:
            return jsonify({
                'success': False,
                'message': '需要管理员权限',
                'data': None
            }), 403
        return f(current_user, *args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


bp_notice_category = Blueprint('notice_category', __name__, url_prefix='/api/notice')


NOTICE_TYPES = {
    'SYSTEM': {
        'name': '系统通知',
        'description': '系统级重要通知，所有用户可见',
        'color': '#ff4d4f',
        'icon': 'system',
        'target_users': ['ALL'],
        'priority': 1
    },
    'ACTIVITY': {
        'name': '活动公告',
        'description': '活动类公告，普通用户可见',
        'color': '#faad14',
        'icon': 'activity',
        'target_users': ['USER'],
        'priority': 2
    },
    'GENERAL': {
        'name': '其他公告',
        'description': '其他类型的公告，普通用户可见',
        'color': '#52c41a',
        'icon': 'general',
        'target_users': ['USER'],
        'priority': 3
    }
}


NOTICE_TEMPLATES = [
    {
        'id': 'system_maintenance',
        'name': '系统维护公告',
        'type': 'SYSTEM',
        'template': ,
        'variables': [
            {'name': 'maintenance_time', 'label': '维护时间', 'required': True},
            {'name': 'maintenance_scope', 'label': '维护范围', 'required': True},
            {'name': 'impact_content', 'label': '影响内容', 'required': True},
            {'name': 'support_contact', 'label': '技术支持', 'required': False},
            {'name': 'service_hotline', 'label': '服务热线', 'required': False},
            {'name': 'company_name', 'label': '公司名称', 'required': True},
            {'name': 'date', 'label': '公告日期', 'required': True}
        ]
    },
    {
        'id': 'feature_update',
        'name': '功能更新公告',
        'type': 'GENERAL',
        'template': ,
        'variables': [
            {'name': 'new_features', 'label': '新增功能', 'required': False},
            {'name': 'improved_features', 'label': '功能优化', 'required': False},
            {'name': 'fixed_issues', 'label': '问题修复', 'required': False},
            {'name': 'update_time', 'label': '更新时间', 'required': True},
            {'name': 'version_number', 'label': '版本号', 'required': True},
            {'name': 'company_name', 'label': '公司名称', 'required': True},
            {'name': 'date', 'label': '公告日期', 'required': True}
        ]
    },
    {
        'id': 'holiday_notice',
        'name': '节假日通知',
        'type': 'GENERAL',
        'template': ,
        'variables': [
            {'name': 'holiday_name', 'label': '节假日名称', 'required': True},
            {'name': 'holiday_period', 'label': '放假时间', 'required': True},
            {'name': 'holiday_notes', 'label': '注意事项', 'required': False},
            {'name': 'emergency_contact', 'label': '紧急联系方式', 'required': False},
            {'name': 'company_name', 'label': '公司名称', 'required': True},
            {'name': 'date', 'label': '公告日期', 'required': True}
        ]
    },
    {
        'id': 'activity_announcement',
        'name': '活动发布公告',
        'type': 'ACTIVITY',
        'template': ,
        'variables': [
            {'name': 'activity_name', 'label': '活动名称', 'required': True},
            {'name': 'activity_time', 'label': '活动时间', 'required': True},
            {'name': 'activity_location', 'label': '活动地点', 'required': True},
            {'name': 'activity_content', 'label': '活动内容', 'required': True},
            {'name': 'signup_method', 'label': '报名方式', 'required': False},
            {'name': 'highlights', 'label': '活动亮点', 'required': False},
            {'name': 'contact_info', 'label': '联系方式', 'required': False},
            {'name': 'company_name', 'label': '公司名称', 'required': True},
            {'name': 'date', 'label': '公告日期', 'required': True}
        ]
    }
]


@bp_notice_category.route('/types', methods=['GET'])
@token_required
def get_notice_types(current_user):
    
    try:
        logger.info(f"【公告类型查询】用户: {current_user.account}")

        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None

        if is_admin:
            visible_types = NOTICE_TYPES
        else:
            visible_types = {
                k: v for k, v in NOTICE_TYPES.items()
                if k in ['SYSTEM', 'GENERAL']
            }

        type_list = []
        for type_code, type_info in visible_types.items():
            type_item = {
                'code': type_code,
                'name': type_info['name'],
                'description': type_info['description'],
                'color': type_info['color'],
                'icon': type_info['icon'],
                'priority': type_info['priority']
            }
            type_list.append(type_item)

        type_list.sort(key=lambda x: x['priority'])

        logger.info(f"【公告类型查询成功】用户: {current_user.account}, 类型数: {len(type_list)}")
        return jsonify({
            'success': True,
            'message': '公告类型查询成功',
            'data': {
                'types': type_list,
                'is_admin': is_admin
            }
        }), 200

    except Exception:
        logger.exception("【公告类型查询异常】")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_category.route('/types/<type_code>', methods=['GET'])
@token_required
def get_notice_type_detail(current_user, type_code):
    
    try:
        logger.info(f"【公告类型详情查询】用户: {current_user.account}, 类型: {type_code}")

        if type_code not in NOTICE_TYPES:
            return jsonify({
                'success': False,
                'message': '公告类型不存在',
                'data': None
            }), 404

        current_admin = Admin.query.filter_by(account=current_user.account).first()
        is_admin = current_admin is not None


        type_info = NOTICE_TYPES[type_code]

        total_count = Notice.query.filter_by(notice_type=type_code).count()
        active_count = Notice.query.filter(
            and_(
                Notice.notice_type == type_code,
                Notice.status == 'APPROVED',
                or_(
                    Notice.expiration.is_(None),
                    Notice.expiration > datetime.utcnow()
                )
            )
        ).count()

        result = {
            'code': type_code,
            'name': type_info['name'],
            'description': type_info['description'],
            'color': type_info['color'],
            'icon': type_info['icon'],
            'priority': type_info['priority'],
            'target_users': type_info['target_users'],
            'statistics': {
                'total_count': total_count,
                'active_count': active_count
            }
        }

        logger.info(f"【公告类型详情查询成功】用户: {current_user.account}, 类型: {type_code}")
        return jsonify({
            'success': True,
            'message': '公告类型详情查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【公告类型详情查询异常】")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_category.route('/templates', methods=['GET'])
@token_required
@admin_required
def get_notice_templates(current_user):
    
    try:
        logger.info(f"【公告模板查询】管理员: {current_user.account}")

        templates = []
        for template in NOTICE_TEMPLATES:
            template_data = {
                'id': template['id'],
                'name': template['name'],
                'type': template['type'],
                'type_name': NOTICE_TYPES[template['type']]['name'],
                'variables': template['variables']
            }
            templates.append(template_data)

        logger.info(f"【公告模板查询成功】管理员: {current_user.account}, 模板数: {len(templates)}")
        return jsonify({
            'success': True,
            'message': '公告模板查询成功',
            'data': {
                'templates': templates
            }
        }), 200

    except Exception:
        logger.exception("【公告模板查询异常】")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_category.route('/templates/<template_id>', methods=['GET'])
@token_required
@admin_required
def get_notice_template_detail(current_user, template_id):
    
    try:
        logger.info(f"【公告模板详情查询】管理员: {current_user.account}, 模板ID: {template_id}")

        template = next((t for t in NOTICE_TEMPLATES if t['id'] == template_id), None)
        if not template:
            return jsonify({
                'success': False,
                'message': '模板不存在',
                'data': None
            }), 404

        result = {
            'id': template['id'],
            'name': template['name'],
            'type': template['type'],
            'template': template['template'],
            'variables': template['variables']
        }

        logger.info(f"【公告模板详情查询成功】管理员: {current_user.account}, 模板: {template['name']}")
        return jsonify({
            'success': True,
            'message': '模板详情查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【公告模板详情查询异常】")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_category.route('/templates/apply', methods=['POST'])
@token_required
@admin_required
def apply_notice_template(current_user):
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据不能为空',
                'data': None
            }), 400

        template_id = data.get('template_id')
        variables = data.get('variables', {})

        if not template_id:
            return jsonify({
                'success': False,
                'message': '模板ID不能为空',
                'data': None
            }), 400

        logger.info(f"【应用公告模板】管理员: {current_user.account}, 模板ID: {template_id}")

        template = next((t for t in NOTICE_TEMPLATES if t['id'] == template_id), None)
        if not template:
            return jsonify({
                'success': False,
                'message': '模板不存在',
                'data': None
            }), 404

        required_vars = [v['name'] for v in template['variables'] if v.get('required', False)]
        missing_vars = [var for var in required_vars if var not in variables or not variables[var]]
        if missing_vars:
            return jsonify({
                'success': False,
                'message': f'缺少必填变量：{", ".join(missing_vars)}',
                'data': None
            }), 400

        try:
            content = template['template'].format(**variables)
        except KeyError as e:
            return jsonify({
                'success': False,
                'message': f'模板变量缺失：{str(e)}',
                'data': None
            }), 400

        result = {
            'template_id': template_id,
            'template_name': template['name'],
            'notice_type': template['type'],
            'title': variables.get('title', template['name']),
            'content': content,
            'applied_variables': variables
        }

        logger.info(f"【应用公告模板成功】管理员: {current_user.account}, 模板: {template['name']}")
        return jsonify({
            'success': True,
            'message': '模板应用成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【应用公告模板异常】")
        return jsonify({
            'success': False,
            'message': f'应用失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_category.route('/push-rules', methods=['GET'])
@token_required
@admin_required
def get_push_rules(current_user):
    
    try:
        logger.info(f"【推送规则查询】管理员: {current_user.account}")

        push_rules = {
            'SYSTEM': {
                'target_users': ['ALL'],
                'push_channels': ['web', 'email', 'sms'],
                'priority': 'high',
                'immediate': True,
                'description': '系统通知立即推送给所有用户'
            },
            'ACTIVITY': {
                'target_users': ['USER'],
                'push_channels': ['web', 'email'],
                'priority': 'medium',
                'immediate': False,
                'description': '活动公告推送给普通用户并可通过邮件或站内消息提醒'
            },
            'GENERAL': {
                'target_users': ['USER'],
                'push_channels': ['web'],
                'priority': 'low',
                'immediate': False,
                'description': '其他公告按计划推送给普通用户'
            }
        }

        user_types = [
            {'value': 'ALL', 'label': '所有用户'},
            {'value': 'ADMIN', 'label': '管理员'},
            {'value': 'USER', 'label': '普通用户'}
        ]

        push_channels = [
            {'value': 'web', 'label': '站内消息'},
            {'value': 'email', 'label': '邮件通知'},
            {'value': 'sms', 'label': '短信通知'}
        ]

        result = {
            'push_rules': push_rules,
            'user_types': user_types,
            'push_channels': push_channels
        }

        logger.info(f"【推送规则查询成功】管理员: {current_user.account}")
        return jsonify({
            'success': True,
            'message': '推送规则查询成功',
            'data': result
        }), 200

    except Exception:
        logger.exception("【推送规则查询异常】")
        return jsonify({
            'success': False,
            'message': f'查询失败：{str(e)}',
            'data': None
        }), 500


@bp_notice_category.route('/validate', methods=['POST'])
@token_required
@admin_required
def validate_notice_config(current_user):
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据不能为空',
                'data': None
            }), 400

        notice_type = data.get('notice_type', '').strip()
        target_user_type = data.get('target_user_type', '').strip()
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        expiration = data.get('expiration', '').strip()

        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }

        if notice_type not in NOTICE_TYPES:
            validation_result['is_valid'] = False
            validation_result['errors'].append('无效的公告类型')
        else:
            if not NoticePermissionUtils.validate_notice_access_scope(notice_type, target_user_type):
                validation_result['is_valid'] = False
                validation_result['errors'].append('公告类型与推送范围不匹配')

        if not title:
            validation_result['is_valid'] = False
            validation_result['errors'].append('公告标题不能为空')
        elif len(title) > 150:
            validation_result['is_valid'] = False
            validation_result['errors'].append('公告标题不能超过150个字符')

        if not content:
            validation_result['is_valid'] = False
            validation_result['errors'].append('公告内容不能为空')
        elif len(content) > 10000:
            validation_result['warnings'].append('公告内容较长，建议控制在10000字符以内')

        if expiration:
            try:
                expiration_date = datetime.fromisoformat(expiration.replace('Z', '+00:00'))
                if expiration_date.tzinfo:
                    expiration_date = expiration_date.replace(tzinfo=None)
                if expiration_date <= datetime.utcnow():
                    validation_result['is_valid'] = False
                    validation_result['errors'].append('到期时间不能早于当前时间')
                elif expiration_date > datetime.utcnow() + timedelta(days=365):
                    validation_result['warnings'].append('到期时间过远，建议设置在一年内')
            except ValueError:
                validation_result['is_valid'] = False
                validation_result['errors'].append('到期时间格式无效')
        else:
            validation_result['warnings'].append('建议设置公告到期时间')

        logger.info(f"【公告配置验证】管理员: {current_user.account}, 验证结果: {validation_result['is_valid']}")

        return jsonify({
            'success': True,
            'message': '配置验证完成',
            'data': validation_result
        }), 200

    except Exception:
        logger.exception("【公告配置验证异常】")
        return jsonify({
            'success': False,
            'message': f'验证失败：{str(e)}',
            'data': None
        }), 500