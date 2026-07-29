@echo off
chcp 65001 >nul
cd /d %~dp0
echo 启动成军台 Web http://127.0.0.1:8090
if defined XIRANG_API_KEY (
  echo [llm] XIRANG_API_KEY 已设（参赛 primary）
) else if defined TOKEN_PLAN_API_KEY (
  echo [llm] TOKEN_PLAN_API_KEY 已设（interim）
) else if defined SENSENOVA_API_KEY (
  echo [llm] SENSENOVA_API_KEY 已设（interim）
) else (
  echo [llm] 将使用 config.yaml 中的 providers（gitignore）；无 Key 则看板可开、发起战役报错
)
echo 改 Key 后需重启本进程；健康检查: python ..\scripts\health_check.py
python web_server.py
pause
