@echo off
chcp 65001 >nul
cd /d %~dp0\..
echo === 成军台本地一键启动 ===
echo.
echo [path] A 天翼云试用公网: docs\CTYUN_TRIAL.md / DEPLOY天翼云.md
echo [path] B 主办方星辰/息壤 Token 到手后设 XIRANG_API_KEY（参赛 primary）
echo [path] Interim: config.yaml 已可写 Token Plan / SenseNova；或设 TOKEN_PLAN_API_KEY / SENSENOVA_API_KEY
echo.

cd content_factory
if not exist config.yaml (
  if exist config.yaml.example (
    copy /Y config.yaml.example config.yaml >nul
    echo [ok] 已从 config.yaml.example 生成 config.yaml
    echo [!!] 请把 interim Key 写入 config.yaml（已 gitignore）或设环境变量后重启
  ) else (
    echo [err] 缺少 config.yaml / config.yaml.example
    pause
    exit /b 1
  )
)
if not exist users.json (
  if exist users.json.example (
    copy /Y users.json.example users.json >nul
    echo [ok] 已从 users.json.example 生成 users.json
  ) else (
    echo [err] 缺少 users.json / users.json.example
    pause
    exit /b 1
  )
)

if defined XIRANG_API_KEY (
  echo [llm] primary: 已检测到 XIRANG_API_KEY（息壤/星辰）
) else if defined TOKENHUB_API_KEY (
  echo [llm] secondary: 已检测到 TOKENHUB_API_KEY
) else if defined TOKEN_PLAN_API_KEY (
  echo [llm] interim: 已检测到 TOKEN_PLAN_API_KEY（阿里云 Token Plan）
) else if defined SENSENOVA_API_KEY (
  echo [llm] interim: 已检测到 SENSENOVA_API_KEY
) else if defined DASHSCOPE_API_KEY (
  echo [llm] interim: 已检测到 DASHSCOPE_API_KEY（标准百炼）
) else (
  echo [llm] 环境变量未设 Key — 将读取 content_factory\config.yaml 中的 providers（已 gitignore）
  echo       若 config 已填 interim Key，健康检查 demo_ready 可为 true
  echo       Path B 稍后:  $env:XIRANG_API_KEY="主办方Key"  并开启 primary provider
  echo       双路径:   docs\CTYUN_TRIAL.md
)
echo.
echo 1) Web:  http://127.0.0.1:8090
echo 2) 账号: admin / chengjun2026   评委只读: judge / judge2026
echo 3) 健康: 另开终端运行  python scripts\health_check.py
echo 4) 智能问数: 另开终端运行  scripts\start_nl2sql_demo.bat（种子库+8082+8765）
echo 5) 样例战役: 启动时自动幂等写入演示快照
echo 6) 若 Web 已在 :8090 运行，改 Key 后请重启本脚本进程
echo.
pushd %~dp0\..
python scripts\seed_demo_campaigns.py
popd
echo.
python web_server.py
pause
