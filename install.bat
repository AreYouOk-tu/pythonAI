@echo off
chcp 65001 > nul
echo.
echo ╔══════════════════════════════════════════════╗
echo ║       Python 后端项目 - 一键安装脚本         ║
echo ╚══════════════════════════════════════════════╝
echo.

:: 检查 Python 是否安装
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 检测到 Python 版本：
python --version
echo.

:: 创建虚拟环境
:: 虚拟环境 = 为这个项目独立安装包，不影响系统其他 Python 项目
echo [2/4] 创建虚拟环境 (.venv)...
if exist .venv (
    echo      虚拟环境已存在，跳过创建
) else (
    python -m venv .venv
    echo      虚拟环境创建成功
)
echo.

:: 激活虚拟环境
echo [3/4] 激活虚拟环境...
call .venv\Scripts\activate.bat
echo      虚拟环境已激活
echo.

:: 安装依赖包
echo [4/4] 安装依赖包（可能需要几分钟，请耐心等待）...
:: 使用国内镜像源加速下载（阿里云镜像）
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
echo.

:: 检查 .env 文件是否存在
if not exist .env (
    echo [提示] 正在从模板创建 .env 配置文件...
    copy .env.example .env > nul
    echo      已创建 .env 文件，请用记事本打开并填入你的 API Key
    echo.
)

echo ╔══════════════════════════════════════════════╗
echo ║              安装完成！                      ║
echo ╠══════════════════════════════════════════════╣
echo ║                                              ║
echo ║  下一步：                                    ║
echo ║  1. 编辑 .env 文件，填入 ANTHROPIC_API_KEY   ║
echo ║  2. 运行 start.bat 启动服务                  ║
echo ║  3. 浏览器打开 http://localhost:8000/docs    ║
echo ║                                              ║
echo ╚══════════════════════════════════════════════╝
echo.
pause
