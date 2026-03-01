
from flask import Blueprint

reply_bp = Blueprint('reply', __name__, url_prefix='/api/forum/replies')

from . import routes