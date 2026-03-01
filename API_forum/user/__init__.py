
from flask import Blueprint

user_bp = Blueprint('forum_user', __name__, url_prefix='/api/forum/users')

from . import user_ops