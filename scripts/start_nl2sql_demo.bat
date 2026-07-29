@echo off
chcp 65001 >nul
cd /d %~dp0\..
echo === 成军台 · 智能问数（优先真实库）===
echo.
echo 推荐：scripts\start_real_data.bat（先刷新政采网再启 znws/MCP）
echo 本脚本：若库空则写演示种子；有真实行则跳过 seed。
echo 标书清单优先读 bid_telecom.db；JSON 仅冷回退。见 docs\REAL_DATA.md
echo.

REM 1) 仅当库空时 seed 演示；有数据则保留
python -c "from seed_demo_db import ensure_demo_db; print(ensure_demo_db(force=False))"
if errorlevel 1 (
  echo [err] seed_demo_db 失败
  pause
  exit /b 1
)

REM 2) 依赖（幂等）
pip install flask aiohttp requests cachetools --quiet --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

echo.
echo [1/2] 启动 znws 问数后端 :8082 ...
start "chengjuntai-znws" cmd /k "cd /d %~dp0\.. && python znws_query_mock.py"

timeout /t 2 /nobreak >nul

echo [2/2] 启动 NL2SQL MCP :8765 ...
start "chengjuntai-mcp" cmd /k "cd /d %~dp0\.. && python mcp_http_nl2sql_v3.py"

echo.
echo 就绪后：
echo   - 后端健康: http://127.0.0.1:8082/health
echo   - MCP:      http://127.0.0.1:8765/mcp
echo   - Web「智能问数」；「标书工作台」；刷新: python scripts\refresh_real_bids.py --quick
echo.
echo 可保持本窗口关闭；两个子窗口继续运行。
pause
