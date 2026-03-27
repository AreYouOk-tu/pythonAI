"""
Alembic 迁移工具配置文件
========================
Alembic 是数据库迁移工具，相当于数据库的"版本管理"
就像 git 管理代码版本，Alembic 管理数据库表结构的版本

常用命令：
  # 生成迁移文件（检测模型变化，自动生成 SQL）
  alembic revision --autogenerate -m "描述本次变更"

  # 执行迁移（把变化应用到数据库）
  alembic upgrade head

  # 回滚到上一个版本
  alembic downgrade -1

  # 查看当前版本
  alembic current
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 导入我们的配置和数据库模型
# 这两行是关键：让 Alembic 知道数据库地址和要管理哪些表
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import settings
from app.database import Base
import app.models.db_models  # 导入所有模型，让 Base 知道所有表结构

# Alembic 的配置对象（读取 alembic.ini 文件）
config = context.config

# 从我们的 settings 中读取数据库连接字符串
# 覆盖 alembic.ini 里的默认配置
# 注意：Alembic 不支持异步，所以用同步版本的 URL（psycopg2）
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

# 配置日志（让 Alembic 的输出更可读）
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 告诉 Alembic 要管理哪些表（通过 Base.metadata 获取所有模型信息）
# autogenerate 功能依赖这个：对比 metadata 里的表和数据库里的实际表，找出差异
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    离线模式迁移（生成 SQL 文件，不直接连接数据库）
    适合生产环境：先生成 SQL 文件，审查后再手动执行
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式迁移（直接连接数据库执行）
    适合开发环境：直接把变化应用到数据库
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool：迁移完不保留连接，避免资源占用
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


# 根据当前模式执行对应的迁移函数
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
