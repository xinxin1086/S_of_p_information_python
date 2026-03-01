
from flask import Blueprint

admin_bp = Blueprint('forum_admin', __name__, url_prefix='/api/forum/admin')

from . import forum_manage