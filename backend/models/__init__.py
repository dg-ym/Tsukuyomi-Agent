from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession
from settings import DB_URI
from sqlalchemy.orm import sessionmaker,DeclarativeBase
from sqlalchemy import MetaData

# 修复 aiomysql/asyncmy 的 ping(reconnect) 与 SQLAlchemy pymysql 方言不兼容的问题
from sqlalchemy.dialects.mysql import pymysql as _pymysql_dialect

_original_do_ping = _pymysql_dialect.MySQLDialect_pymysql.do_ping

def _patched_do_ping(self, dbapi_connection):
    try:
        dbapi_connection.ping(False)
    except Exception:
        _original_do_ping(self, dbapi_connection)

_pymysql_dialect.MySQLDialect_pymysql.do_ping = _patched_do_ping

# 定义命名约定的Base类
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        # ix: index 索引
        "ix": "ix_%(column_0_label)s",
        # uq: unique constraint 唯一约束
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        # ck: check constraint 检查约束
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        # fk: foreign key 外键约束
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        # pk: primary key 主键约束
        "pk": "pk_%(table_name)s"
    })

# 使用相对导入确保 user.py 被识别为 models 包的子模块
from . import user
from . import user_file

engine = create_async_engine(
    DB_URI,
    # 将输出所有执行SQL的日志（默认是关闭的）
    echo=True,
    # 连接池的大小（默认是5个）
    pool_size=10,
    # 连接池达到最大尺寸后可以额外创建的连接数（默认是10个）
    max_overflow=20,
    # 连接池中连接的超时时间（默认是30s）
    pool_timeout=10,
    # 连接回收时间（默认是-1，代表永不回收）
    pool_recycle=3600,
    # 连接前是否预检查（默认是False）
    pool_pre_ping=True,
)

AsyncSessionFactory = sessionmaker(
    # Engine或者其子类对象（这里是AsyncEngine）
    bind=engine,
    # Session类的代替（默认是Session类）
    class_=AsyncSession,
    # 是否在查找之前执行flush操作（默认是True）
    autoflush=True,
    # 是否在执行commit操作后Session就过期（默认是True）
    expire_on_commit=False,
)

