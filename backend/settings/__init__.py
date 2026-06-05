from datetime import timedelta
DB_URI = "mysql+asyncmy://root:root@127.0.0.1:3306/数据库名称?charset=utf8mb4"

# 邮箱相关配置
MAIL_USERNAME="用来发送验证码的邮箱"
MAIL_PASSWORD="邮件服务码"
MAIL_FROM="用来发送验证码的邮箱"
MAIL_PORT=587
MAIL_SERVER="邮件服务提供方"
MAIL_FROM_NAME="名字"
MAIL_STARTTLS=True
MAIL_SSL_TLS=False

JWT_SECRET_KEY = "密钥"
JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=15)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

# 文件上传配置
UPLOAD_DIR = "uploads"                       # 原文件存储目录
MAX_UPLOAD_SIZE = 20 * 1024 * 1024           # 单文件最大 20MB