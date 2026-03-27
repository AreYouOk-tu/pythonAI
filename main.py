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
from app.routes import ai
# from app.routes import employee, efficiency, image  # 暂时停用（依赖数据库）


# ==============================
# 生命周期管理（启动 & 关闭钩子）
# ==============================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    服务生命周期钩子
    - yield 前：服务启动时执行（建表、初始化数据等）
    - yield 后：服务关闭时执行（释放资源等）
    """
    # ---- 数据库初始化（暂时停用）----
    # print("[启动] 服务启动中，正在初始化数据库...")
    # from sqlalchemy import text
    # from app.database import engine, Base, AsyncSessionLocal
    # from app.services.employee import init_default_employee_types
    # async with engine.begin() as conn:
    #     await conn.execute(text("SET hg_experimental_enable_shard_count_cap=off"))
    #     await conn.run_sync(Base.metadata.create_all)
    # print("[完成] 数据库表初始化完成")
    # from app.services.efficiency import init_default_efficiency_data
    # async with AsyncSessionLocal() as db:
    #     await init_default_employee_types(db)
    #     await init_default_efficiency_data(db)
    #     await db.commit()

    # ---- 启动定时任务调度器 ----
    from app.scheduler import create_scheduler
    scheduler = create_scheduler()
    scheduler.start()
    print("[启动] 定时任务调度器已启动")

    yield  # 服务正式开始运行，处理请求

    # ---- 服务关闭时 ----
    scheduler.shutdown()
    print("[关闭] 定时任务调度器已关闭")
    # await engine.dispose()  # 暂时停用


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================
# 注册路由模块
# ==============================
app.include_router(ai.router)
# app.include_router(employee.router)   # 暂时停用（依赖数据库）
# app.include_router(efficiency.router)  # 暂时停用（依赖数据库）
# app.include_router(image.router)       # 暂时停用（依赖数据库）


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
