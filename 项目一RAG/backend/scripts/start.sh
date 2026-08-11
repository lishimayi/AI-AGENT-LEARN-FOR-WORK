#!/bin/bash

# 企业级产品需求智能 Agent 启动脚本

set -e

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "============================================"
echo "企业级产品需求智能 Agent 启动脚本"
echo "============================================"

# 创建必要的目录
mkdir -p data/uploads data/chroma data/faiss_index logs

# 加载环境变量
if [ -f backend/.env ]; then
    echo "加载环境变量..."
    set -a
    source backend/.env
    set +a
fi

# 检查 Python 依赖
echo "检查 Python 依赖..."
if ! pip show fastapi > /dev/null 2>&1; then
    echo "安装 Python 依赖..."
    cd backend
    pip install -r requirements.txt
    cd ..
fi

# 启动后端服务
echo "启动后端服务..."
cd backend
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

echo "后端服务已启动: http://localhost:8000"
echo "API 文档: http://localhost:8000/docs"
