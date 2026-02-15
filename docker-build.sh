#!/bin/bash
echo "========================================"
echo " game-hall-admin Docker 构建并启动"
echo "========================================"

IMAGE_NAME="game-hall-admin"
CONTAINER_NAME="game-hall-admin"
PORT=8002
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_PATH="${SCRIPT_DIR}/config.json"
LOGS_PATH="${SCRIPT_DIR}/logs"

# 创建日志目录
mkdir -p "$LOGS_PATH"

# 构建镜像
echo ""
echo "[1/3] 构建镜像..."
docker build -t ${IMAGE_NAME}:latest "$SCRIPT_DIR"
if [ $? -ne 0 ]; then
    echo "构建失败！"
    exit 1
fi
echo "构建成功"

# 停止并删除旧容器
echo ""
echo "[2/3] 清理旧容器..."
docker stop ${CONTAINER_NAME} 2>/dev/null
docker rm ${CONTAINER_NAME} 2>/dev/null

# 启动新容器
echo ""
echo "[3/3] 启动容器..."
docker run -d \
  --name ${CONTAINER_NAME} \
  --restart always \
  -p ${PORT}:8002 \
  -v "${CONFIG_PATH}":/app/config.json:ro \
  -v "${LOGS_PATH}":/app/logs \
  ${IMAGE_NAME}:latest

if [ $? -ne 0 ]; then
    echo "启动失败！"
    exit 1
fi

echo ""
echo "========================================"
echo " 启动成功！"
echo " 接口地址: http://localhost:${PORT}"
echo " 健康检查: http://localhost:${PORT}/health"
echo " 查看日志: docker logs -f ${CONTAINER_NAME}"
echo "========================================"
