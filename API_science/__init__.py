# API_science/__init__.py
# 科普模块初始化文件

from .routes import (
    bp_science_user,
    bp_science_admin,
    bp_science_category,
    bp_science_public
)

__all__ = ['bp_science_user', 'bp_science_admin', 'bp_science_category', 'bp_science_public']
