
from flask import Blueprint
common_bp = Blueprint('common', __name__, url_prefix='/api/common')

from common import routes