"""
项目配置文件
==========
这里统一管理所有的配置项，包括：
- 服务器端口、Host 等基本配置
- API Key 等敏感信息（从 .env 文件读取，不会提交到 Git）
- CORS 跨域配置（允许前端页面访问这个后端）
- 数据库连接配置
"""

import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
# 相当于读取一个配置文件，里面存放 API Key 等敏感信息
load_dotenv()


class Settings:
    """应用配置类，集中管理所有配置项"""

    # ---- 服务器配置 ----
    # API 标题，会显示在自动生成的文档页面上
    APP_TITLE: str = "Python 后端 API 服务"
    APP_DESCRIPTION: str = "提供业务数据接口 + 大模型调用能力"
    APP_VERSION: str = "1.0.0"

    # 服务启动的 Host 和端口
    HOST: str = "0.0.0.0"   # 0.0.0.0 表示允许任何 IP 访问，localhost 只允许本机
    PORT: int = 8000

    # ---- CORS 跨域配置 ----
    # 前端页面（React/Vue 等）和后端不在同一个域名/端口时，浏览器会拒绝请求
    # 这里配置允许哪些来源可以访问这个后端
    CORS_ORIGINS: list = [
        "http://localhost:3000",    # React 开发服务器默认端口
        "http://localhost:5173",    # Vite 开发服务器默认端口
        "http://localhost:8080",    # 其他常见前端开发端口
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # ---- 大模型配置 ----
    # 从 .env 文件读取 API Key，os.getenv 读取不到时返回 None
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # 使用的 Claude 模型版本
    # claude-sonnet-4-6 是目前性价比最高的模型
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    # 模型最大输出 token 数（1 个中文字约等于 1.5 token）
    MAX_TOKENS: int = 2048

    # ---- 通义万相（文生图）配置 ----
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # ---- 阿里云 OSS 配置（图片持久化存储）----
    OSS_ACCESS_KEY_ID: str = os.getenv("OSS_ACCESS_KEY_ID", "")
    OSS_ACCESS_KEY_SECRET: str = os.getenv("OSS_ACCESS_KEY_SECRET", "")
    OSS_BUCKET_NAME: str = os.getenv("OSS_BUCKET_NAME", "")
    OSS_ENDPOINT: str = os.getenv("OSS_ENDPOINT", "oss-cn-shanghai.aliyuncs.com")
    OSS_IMAGE_PREFIX: str = os.getenv("OSS_IMAGE_PREFIX", "ai-generated-images/")

    @property
    def OSS_PUBLIC_URL_BASE(self) -> str:
        """拼接 OSS 公网访问 URL 前缀，如 https://bucket.oss-cn-shanghai.aliyuncs.com/"""
        return f"https://{self.OSS_BUCKET_NAME}.{self.OSS_ENDPOINT}/"

    # ---- PostgreSQL 数据库配置 ----
    # 从 .env 文件读取，格式说明：
    #   postgresql+asyncpg://用户名:密码@主机:端口/数据库名
    #   asyncpg 是异步驱动，比同步驱动性能更好，适合 FastAPI
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")       # PostgreSQL 默认端口

    # bi_test 数据库
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "bi_test")

    # bi_prod 数据库
    DB_USER_PROD: str = os.getenv("DB_USER_PROD", os.getenv("DB_USER", "postgres"))
    DB_PASSWORD_PROD: str = os.getenv("DB_PASSWORD_PROD", os.getenv("DB_PASSWORD", ""))
    DB_NAME_PROD: str = os.getenv("DB_NAME_PROD", "bi_prod")

    @property
    def DATABASE_URL(self) -> str:
        """bi_test 异步连接 URL"""
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_PROD(self) -> str:
        """bi_prod 异步连接 URL"""
        return (
            f"postgresql+asyncpg://{self.DB_USER_PROD}:{self.DB_PASSWORD_PROD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME_PROD}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """bi_test 同步连接 URL（给 Alembic 使用）"""
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


# 创建全局配置实例，其他文件 import 这个对象来使用配置
settings = Settings()
