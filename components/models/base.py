
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class FlaskSQLAlchemyCompatibility:
    

    @staticmethod
    def get_session():
        
        try:
            return db.session
        except TypeError:
            return db.session()

compat_session = FlaskSQLAlchemyCompatibility.get_session


def get_table_comment_args(comment):
    
    try:
        engine_url = str(db.engine.url).lower()

        if 'mysql' in engine_url:
            return {'mysql_comment': comment}
        elif 'postgresql' in engine_url:
            return {'comment': comment}
        elif 'sqlite' in engine_url:
            return {}
        else:
            return {'comment': comment}
    except:
        return {}


class BaseUser(db.Model):
    
    __abstract__ = True

    def set_password(self, password):
        
        if not isinstance(password, str) or not password:
            raise ValueError('密码必须是非空字符串')
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        
        if not isinstance(password, str) or not password:
            raise ValueError('密码必须是非空字符串')
        return check_password_hash(self.password_hash, password)