#!/bin/bash

# 确保脚本退出时清理所有后台进程
trap "kill 0" EXIT

echo ">>> 正在启动 LuluGo 后端服务..."
# 后台启动 Python 服务，日志重定向到文件以保持终端清爽
python main.py > server.log 2>&1 &
SERVER_PID=$!
echo ">>> 后端服务已启动 (PID: $SERVER_PID)"
echo ">>> 日志文件: server.log"

echo ">>> 正在清理代理并启动 Ngrok..."
# 清理代理环境变量
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

# 后台启动 ngrok
ngrok http 8000 > /dev/null 2>&1 &
NGROK_PID=$!

# 等待 ngrok 初始化
echo ">>> 等待网络穿透初始化 (3秒)..."
sleep 5

# 自动获取 ngrok 网址
echo "=========================================================="
echo "✅ 游戏服务已就绪！"
echo "🌍 请将下方网址复制给你的朋友："
echo ""
curl -s http://127.0.0.1:4040/api/tunnels | grep -o 'https://[^"]*\.ngrok[^"]*'
echo ""
echo "=========================================================="
echo "按 Ctrl+C 停止所有服务"

# 保持脚本运行
wait