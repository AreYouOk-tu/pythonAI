@echo off
chcp 65001 > nul
echo.
echo ╔══════════════════════════════════════════════╗
echo ║         启动 Python 后端 API 服务            ║
echo ╚══════════════════════════════════════════════╝
echo.

:: 检查虚拟环境是否存在
if not exist .venv (
    echo [错误] 虚拟环境不存在，请先运行 install.bat 安装依赖
    pause
    exit /b 1
)

:: 激活虚拟环境并启动服务
echo 正在启动服务...
echo 本地访问: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo 按 Ctrl+C 停止服务
echo.

call .venv\Scripts\activate.bat
python main.py
pause
