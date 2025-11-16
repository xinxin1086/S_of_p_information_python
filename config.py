class Config:
    # 数据库配置（所有模块共享）
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:root@localhost:3306/s_of_p_information?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT配置
    JWT_SECRET_KEY = 'your-secret-key-123'  # 生产环境需更换
    JWT_EXPIRATION_DELTA = 3600  # 令牌有效期（秒）

    # 图片存储相关配置（供LocalImageStorage读取）图片存储目录（项目根目录下）
    IMAGE_STORAGE_DIR = 'static/images'
    ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ALLOWED_IMAGE_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    # 最大5MB
    MAX_IMAGE_SIZE = 5 * 1024 * 1024

