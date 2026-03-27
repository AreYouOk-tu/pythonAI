"""
FastAPI 主入口文件
=================
这是整个后端服务的启动入口，相当于 Node.js 项目中的 index.js / server.js

启动命令：
  python main.py
  或者
  uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from app.config import settings
from app.routes import employee, ai, efficiency, image


# ==============================
# 生命周期管理（启动 & 关闭钩子）
# ==============================
# @asynccontextmanager 把这个函数变成一个"上下文管理器"
# FastAPI 的 lifespan 参数接收这种函数，在服务启动/关闭时自动调用
#
# 类比前端：
#   yield 之前的代码 → 相当于 React 的 useEffect 里的初始化逻辑
#   yield 之后的代码 → 相当于 useEffect 返回的清理函数（组件卸载时执行）
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    服务生命周期钩子
    - yield 前：服务启动时执行（建表、初始化数据等）
    - yield 后：服务关闭时执行（释放资源等）
    """
    # ---- 服务启动时 ----
    print("[启动] 服务启动中，正在初始化数据库...")

    from sqlalchemy import text
    from app.database import engine, Base, AsyncSessionLocal
    from app.services.employee import init_default_employee_types

    # 自动建表：根据 db_models.py 中定义的表结构，在数据库里创建对应的表
    # checkfirst=True（SQLAlchemy 默认行为）→ 表已存在则跳过，不会重复创建
    # 相当于 "CREATE TABLE IF NOT EXISTS ..."
    async with engine.begin() as conn:
        # Hologres（阿里云数据仓库）限制：每个实例最多 160 个 shard
        # 建表时会自动分配 shard，超出上限会报错
        # 这行 SQL 关闭当前 session 的 shard 数量上限检查，允许继续建表
        await conn.execute(text("SET hg_experimental_enable_shard_count_cap=off"))

        # run_sync 用于在异步环境中运行同步函数
        # Base.metadata.create_all 是同步函数，所以需要 run_sync 包装
        await conn.run_sync(Base.metadata.create_all)
    print("[完成] 数据库表初始化完成")

    # 插入初始数据（如果数据库是空的）
    from app.services.efficiency import init_default_efficiency_data
    async with AsyncSessionLocal() as db:
        await init_default_employee_types(db)
        await init_default_efficiency_data(db)
        await db.commit()

    # ---- 启动定时任务调度器 ----
    from app.scheduler import create_scheduler
    scheduler = create_scheduler()
    scheduler.start()
    print("[启动] 定时任务调度器已启动")

    yield  # 服务正式开始运行，处理请求

    # ---- 服务关闭时 ----
    # 关闭定时任务调度器
    scheduler.shutdown()
    print("[关闭] 定时任务调度器已关闭")
    # 关闭数据库连接池，释放资源
    await engine.dispose()
    print("[关闭] 服务已关闭，数据库连接已释放")


# ==============================
# 创建 FastAPI 应用实例
# ==============================
app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,

    # 注册生命周期管理函数
    lifespan=lifespan,

    # 关闭默认 docs（我们下面自定义，解决国内 CDN 加载失败问题）
    docs_url=None,
    redoc_url="/redoc",
)


# 自定义 Swagger UI，替换成 jsdelivr CDN（国内可正常访问）
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=settings.APP_TITLE,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


# ==============================
# 配置 CORS 跨域中间件
# ==============================
# 中间件（Middleware）相当于请求/响应的拦截器
# CORS 中间件会自动给每个响应加上允许跨域的 HTTP 头
app.add_middleware(
    CORSMiddleware,

    # 允许哪些前端域名访问这个后端
    allow_origins=settings.CORS_ORIGINS,

    # 是否允许携带 Cookie（登录状态等）
    allow_credentials=True,

    # 允许所有 HTTP 方法（GET、POST、PUT、DELETE 等）
    allow_methods=["*"],

    # 允许所有 HTTP 请求头
    allow_headers=["*"],
)


# ==============================
# 注册路由模块
# ==============================
# 相当于 Express.js 中的 app.use('/api/employee', employeeRouter)
app.include_router(employee.router)
app.include_router(ai.router)
app.include_router(efficiency.router)
app.include_router(image.router)


# ==============================
# 根路径 - 健康检查接口
# ==============================
@app.get("/", tags=["系统"], summary="健康检查")
async def root():
    """
    服务健康检查接口

    前端可以通过这个接口检查后端是否正常运行
    运维监控也常用这类接口
    """
    return {
        "code": 0,
        "message": "服务运行正常",
        "data": {
            "service": settings.APP_TITLE,
            "version": settings.APP_VERSION,
            "docs": "http://localhost:8000/docs",
        }
    }


# ==============================
# 启动服务
# ==============================
if __name__ == "__main__":
    # 只有直接运行 python main.py 时才会执行这里
    # 如果通过 uvicorn main:app 启动则不会执行
    import uvicorn

    print(f"""
╔══════════════════════════════════════════════╗
║         Python 后端 API 服务 启动中          ║
╠══════════════════════════════════════════════╣
║  本地访问: http://localhost:{settings.PORT}           ║
║  API 文档: http://localhost:{settings.PORT}/docs      ║
╚══════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "main:app",           # 格式："文件名:FastAPI实例变量名"
        host=settings.HOST,
        port=settings.PORT,
        reload=True,          # 开发模式：文件修改后自动重启（生产环境应关闭）
        reload_dirs=["app"],  # 只监听 app 目录的变化
    )
