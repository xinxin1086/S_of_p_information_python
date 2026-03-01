
from flask import Blueprint

post_bp = Blueprint('post', __name__, url_prefix='/api/forum/posts')

from . import routes
from . import public