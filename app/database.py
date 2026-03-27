"""
数据库连接配置
=============
这个文件负责：
1. 创建数据库连接引擎（相当于数据库连接池管理器）
2. 创建 Session 工厂（每次请求从连接池拿一个连接用）
3. 提供 get_db 依赖函数（供路由函数注入使用）

类比前端理解：
- engine     → 数据库连接池（管理多个连接，按需分配）
- Session    → 单次数据库会话（一个请求用一个 session，用完关闭）
- get_db     → 类似 React 的 useContext，把 db 注入到需要的函数里
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ==============================
# 创建异步数据库引擎（连接池）
# ==============================
# create_async_engine 创建一个异步引擎，支持 async/await 语法
# 相当于建立一个"管道"连接到数据库，后续所有操作都走这个管道
#
# echo=True → 开发模式：打印每条执行的 SQL 语句（方便调试，生产环境改为 False）
# pool_size=10 → 连接池大小：同时最多保持 10 个数据库连接
# max_overflow=20 → 连接池溢出上限：超过 pool_size 后最多再开 20 个临时连接
# bi_test 引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_size=10,
    max_overflow=20,
)

# bi_prod 引擎
engine_prod = create_async_engine(
    settings.DATABASE_URL_PROD,
    echo=True,
    pool_size=10,
    max_overflow=20,
)


# ==============================
# 创建 Session 工厂
# ==============================
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# bi_prod Session 工厂
AsyncSessionLocalProd = async_sessionmaker(
    bind=engine_prod,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ==============================
# ORM 模型基类
# ==============================
# 所有数据库表对应的 Python 类都要继承这个 Base
# SQLAlchemy 通过 Base 追踪所有模型，用于建表和迁移
# 类比：就像 TypeORM 的 @Entity 装饰器
class Base(DeclarativeBase):
    pass


# ==============================
# 数据库依赖函数（最重要）
# ==============================
# 这是 FastAPI 的"依赖注入"机制
# 每个需要操作数据库的路由函数，都可以通过参数声明 db: AsyncSession = Depends(get_db)
# FastAPI 会自动调用 get_db，把 db 传进去
#
# 类比前端：类似 React 的 Context.Provider + useContext
#   get_db 相当于 Provider 提供数据库连接
#   路由函数里的 Depends(get_db) 相当于 useContext 消费连接
async def get_db():
    """bi_test 数据库 Session（依赖注入）"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_prod():
    """bi_prod 数据库 Session（依赖注入）"""
    async with AsyncSessionLocalProd() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
