# 数据模型包初始化文件

# 基础模型
from .base import BaseUser, db, compat_session

# 用户相关模型
from .user_models import Admin, User, DeletedUser

# 公告相关模型
from .notice_models import Notice, NoticeAttachment, NoticeRead

# 科普相关模型
from .science_models import ScienceArticle, ScienceArticleLike, ScienceArticleVisit

# 活动相关模型
from .activity_models import Activity, ActivityBooking, ActivityRating, ActivityDiscuss, ActivityDiscussComment

# 论坛相关模型
from .forum_models import ForumPost, ForumFloor, ForumReply, ForumVisit, ForumLike

# 其他模型
from .other_models import Attachment

# 导出所有模型类
__all__ = [
    # 基础类
    'db',
    'compat_session',
    'BaseUser',

    # 用户管理相关
    'Admin',
    'User',
    'DeletedUser',

    # 公告相关
    'Notice',
    'NoticeAttachment',
    'NoticeRead',

    # 科普相关
    'ScienceArticle',
    'ScienceArticleLike',
    'ScienceArticleVisit',

    # 活动管理相关
    'Activity',
    'ActivityBooking',
    'ActivityRating',
    'ActivityDiscuss',
    'ActivityDiscussComment',

    # 论坛相关
    'ForumPost',
    'ForumFloor',
    'ForumReply',
    'ForumVisit',
    'ForumLike',

    # 通用功能相关
    'Attachment',
]