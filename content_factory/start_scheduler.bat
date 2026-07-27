@echo off
chcp 65001 >nul
cd /d %~dp0
echo 启动定时调度服务...
python scheduler.py
pause
