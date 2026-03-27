"""
数据库连接配置（暂时停用）
=============
数据库相关代码已注释，恢复时取消注释即可
"""

from sqlalchemy.orm import DeclarativeBase

# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
# from app.config import settings

# # bi_test 引擎
# engine = create_async_engine(
#     settings.DATABASE_URL,
#     echo=True,
#     pool_size=10,
#     max_overflow=20,
# )

# # bi_prod 引擎
# engine_prod = create_async_engine(
#     settings.DATABASE_URL_PROD,
#     echo=True,
#     pool_size=10,
#     max_overflow=20,
# )

# AsyncSessionLocal = async_sessionmaker(
#     bind=engine,
#     autocommit=False,
#     autoflush=False,
#     expire_on_commit=False,
# )

# AsyncSessionLocalProd = async_sessionmaker(
#     bind=engine_prod,
#     autocommit=False,
#     autoflush=False,
#     expire_on_commit=False,
# )


# ORM 模型基类（保留，db_models.py 依赖它）
class Base(DeclarativeBase):
    pass


# async def get_db():
#     """bi_test 数据库 Session（依赖注入）"""
#     async with AsyncSessionLocal() as session:
#         try:
#             yield session
#             await session.commit()
#         except Exception:
#             await session.rollback()
#             raise


# async def get_db_prod():
#     """bi_prod 数据库 Session（依赖注入）"""
#     async with AsyncSessionLocalProd() as session:
#         try:
#             yield session
#             await session.commit()
#         except Exception:
#             await session.rollback()
#             raise
