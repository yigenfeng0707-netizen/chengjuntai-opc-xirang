@echo off
chcp 65001 >nul
cd /d %~dp0
echo 启动 Web 管理面板 (http://127.0.0.1:8090)...
pip install -r requirements --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com >nul 2>&1
python web_server.py
pause
