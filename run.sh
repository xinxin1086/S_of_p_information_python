#!/bin/bash
# ==========================================
# Flask API 服务器快速启动脚本 (Linux/macOS)
# ==========================================
# 功能：启动 S_of_p_information_python 项目下的 Flask 应用
# 用法：在项目目录下运行 ./run.sh

set -e

echo ""
echo "=========================================="
echo " Flask API Server Startup"
echo "=========================================="
echo ""

# 切换到脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 验证 Python 安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3 环境"
    echo "请确保 Python3 已安装"
    exit 1
fi

echo "[✓] Python 环境已检测"
echo ""

# 启动 Flask 应用
echo "[启动] Flask 开发服务器..."
echo "[信息] 访问地址: http://127.0.0.1:5000"
echo "[信息] API 文档: http://127.0.0.1:5000/api/public/notice/types"
echo ""

python3 -u app.py
