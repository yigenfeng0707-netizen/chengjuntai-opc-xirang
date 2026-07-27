@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo   AI 内容工厂 - 全功能启动
echo ========================================
echo [1/3] 环境自检...
python env_check.py
if errorlevel 1 (
    echo.
    echo [X] 环境自检未通过，已阻断启动。请按修复建议处理后重试。
    pause
    exit /b 1
)
echo.
echo [2/3] 检查依赖...
python -c "import fastapi,uvicorn,yaml,feedparser,numpy,sklearn,reportlab" 2>nul
if errorlevel 1 (
    echo 依赖缺失，自动安装...
    pip install -r requirements --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
)
echo.
echo [3/3] 启动调度 + Web 面板...
echo  定时调度后台运行中...
start "" /B python scheduler.py
echo  Web 面板启动中...
python web_server.py
pause
