@echo off
chcp 65001 >nul
cd /d %~dp0\..
echo === 成军台 · 真实标讯 + 智能问数一键启动 ===
echo.
echo 数据源：浙江省政府采购网 https://zfcg.czt.zj.gov.cn
echo 目标库：bid_telecom.db
echo.

REM 1) 依赖（幂等）
pip install flask aiohttp requests cachetools --quiet --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

echo [1/3] 刷新真实标讯（快速模式；全量请: python scripts\refresh_real_bids.py --full-rebuild）...
python scripts\refresh_real_bids.py --quick --timeout 180
if errorlevel 1 (
  echo.
  echo [warn] 本次抓取未成功或超时。若库内已有 real 行将继续使用；否则回落演示种子。
  echo        日志: logs\fetch.log / logs\fetch_status.json
  echo        手动: python scripts\refresh_real_bids.py --quick
  echo              python fetch_real_data.py --full-rebuild
)

echo.
echo [2/3] 启动 znws 问数后端 :8082 ...
start "chengjuntai-znws" cmd /k "cd /d %~dp0\.. && python znws_query_mock.py"

timeout /t 2 /nobreak >nul

echo [3/3] 启动 NL2SQL MCP :8765 ...
start "chengjuntai-mcp" cmd /k "cd /d %~dp0\.. && python mcp_http_nl2sql_v3.py"

echo.
echo 就绪后：
echo   - 健康: http://127.0.0.1:8082/health
echo   - MCP:  http://127.0.0.1:8765/mcp
echo   - Web 侧栏「智能问数」看行数/最近刷新；「标书工作台」优先读 DB
echo   - 文档: docs\REAL_DATA.md
echo.
pause
