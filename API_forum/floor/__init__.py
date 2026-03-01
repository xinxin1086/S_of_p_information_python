
from flask import Blueprint

floor_bp = Blueprint('floor', __name__, url_prefix='/api/forum/floors')

from . import routes