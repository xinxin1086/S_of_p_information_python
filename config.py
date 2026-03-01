
class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:root@localhost:3306/s_of_p_information?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = 'your-secret-key-123'
    JWT_EXPIRATION_DELTA = 3600

    IMAGE_STORAGE_DIR = 'static/images'
    ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ALLOWED_IMAGE_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    MAX_IMAGE_SIZE = 5 * 1024 * 1024

    AUTO_CREATE_TABLES = True
    INIT_TEST_DATA = True

    DEFAULT_AVATAR_URL = '/static/images/default-avatar.png'
