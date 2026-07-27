@echo off
chcp 65001 >nul
cd /d %~dp0
echo 启动 MCP 服务（stdio 协议）...
pip install -r requirements --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com >nul 2>&1
python mcp_server.py
pause
