# API_science/common/__init__.py

"""
科普模块公共工具包
包含通用工具函数、参数校验、响应格式化等
"""

# 导入公共工具函数
from .utils import (
    validate_article_data,
    get_user_identifier,
    record_article_visit,
    toggle_article_like,
    get_like_status,
    format_article_data,
    check_article_permission,
    build_article_query
)

__all__ = [
    'validate_article_data',
    'get_user_identifier',
    'record_article_visit',
    'toggle_article_like',
    'get_like_status',
    'format_article_data',
    'check_article_permission',
    'build_article_query'
]