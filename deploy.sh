#!/bin/bash
# ================================
# deploy.sh - 一键部署脚本
# ================================
# 使用方式：
#   首次部署：bash deploy.sh
#   更新代码：bash deploy.sh
#
# 前提条件（在服务器上执行一次）：
#   1. 安装 Docker：  curl -fsSL https://get.docker.com | bash
#   2. 上传项目：     git clone 你的仓库地址 或 scp 上传
#   3. 创建 .env：    cp .env.example .env && vim .env（填入真实配置）

set -e  # 任意命令失败就立即退出，防止错误被忽略

APP_NAME="bio-news-api"   # 容器名称
IMAGE_NAME="bio-news-api" # 镜像名称
PORT=8000                 # 对外暴露的端口

echo "=============================="
echo " 开始部署 $APP_NAME"
echo "=============================="

# ---- 第一步：检查 .env 文件 ----
if [ ! -f ".env" ]; then
    echo "[错误] 未找到 .env 文件！"
    echo "  请先创建 .env 文件并填入配置："
    echo "  cp .env.example .env && vim .env"
    exit 1
fi
echo "[完成] .env 文件检查通过"

# ---- 第二步：构建 Docker 镜像 ----
echo "[执行] 正在构建 Docker 镜像..."
docker build -t $IMAGE_NAME .
echo "[完成] 镜像构建完成"

# ---- 第三步：停止并删除旧容器（如果存在）----
if docker ps -a --format '{{.Names}}' | grep -q "^${APP_NAME}$"; then
    echo "[执行] 正在停止旧容器..."
    docker stop $APP_NAME
    docker rm $APP_NAME
    echo "[完成] 旧容器已清理"
fi

# ---- 第四步：启动新容器 ----
echo "[执行] 正在启动新容器..."
docker run -d \
    --name $APP_NAME \
    --restart always \           # 容器崩溃或服务器重启后自动重启
    -p $PORT:8000 \              # 把服务器的 8000 端口映射到容器的 8000 端口
    --env-file .env \            # 从 .env 文件加载所有环境变量
    -v $(pwd)/logs:/app/logs \   # 把日志文件映射到服务器本地（方便查看）
    $IMAGE_NAME

echo "[完成] 容器启动成功！"
echo ""
echo "=============================="
echo " 部署完成"
echo "=============================="
echo " 服务地址：http://$(curl -s ifconfig.me):$PORT"
echo " API 文档：http://$(curl -s ifconfig.me):$PORT/docs"
echo " 查看日志：docker logs -f $APP_NAME"
echo " 停止服务：docker stop $APP_NAME"
echo "=============================="
