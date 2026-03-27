# ================================
# Dockerfile - 把项目打包成容器镜像
# ================================
# 类比前端：相当于把你的项目打包成一个"环境完整的安装包"
# 服务器只需要安装 Docker，不用关心 Python 版本、依赖等问题

# 基础镜像：Python 3.11（生产环境推荐用稳定版，不用最新的 3.14）
FROM python:3.11-slim

# 设置工作目录（容器内的项目路径）
WORKDIR /app

# 先只复制依赖文件（利用 Docker 缓存层，依赖没变就不重新安装）
COPY requirements.txt .

# 安装依赖（使用阿里云镜像加速，在国内服务器上更快）
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

# 复制项目所有文件到容器
COPY . .

# 声明服务监听的端口（和 .env 里的 PORT 保持一致）
EXPOSE 8000

# 启动命令：用 uvicorn 启动 FastAPI
# --host 0.0.0.0 表示允许外部访问（容器内必须这样设置）
# 生产环境去掉 --reload，减少资源消耗
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
