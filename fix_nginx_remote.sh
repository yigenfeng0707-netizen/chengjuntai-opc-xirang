#!/bin/bash
# ============================================================
# Nginx 路由修复脚本 - 在 ECS VNC 终端中执行
# 问题：Nginx 把所有 /api/ 路由转发到 Flask:8082，
#       导致 FastAPI:8090 的 /api/health, /api/login 等被拦截返回 401
# 修复：将 Flask 代理从 /api/ 改为 /api/v1/（Flask 路由本身就是 /api/v1/*）
# ============================================================

set -e

echo "===== 1. 查看当前 Nginx 配置 ====="
# 找到配置文件
CONF_FILE=""
for f in /etc/nginx/sites-enabled/teleagent.conf \
         /etc/nginx/conf.d/teleagent.conf \
         /etc/nginx/sites-available/teleagent.conf; do
    if [ -f "$f" ]; then
        CONF_FILE="$f"
        break
    fi
done

if [ -z "$CONF_FILE" ]; then
    echo "[ERROR] 未找到 teleagent.conf，列出所有 nginx 配置："
    ls -la /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null
    echo "请手动检查 nginx 配置"
    exit 1
fi

echo "配置文件: $CONF_FILE"
echo "--- 当前内容 ---"
cat "$CONF_FILE"
echo "----------------"

echo ""
echo "===== 2. 备份当前配置 ====="
cp "$CONF_FILE" "${CONF_FILE}.bak.$(date +%Y%m%d%H%M%S)"
echo "已备份"

echo ""
echo "===== 3. 写入修复后的配置 ====="
cat > "$CONF_FILE" << 'NGINXEOF'
# 限流区域定义
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    listen 8088;
    server_name _;
    client_max_body_size 50M;

    # 安全响应头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Web 面板 (FastAPI, 8090) - 包含所有 /api/ 路由
    location / {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # NL2SQL Flask 后端 (8082) - 只匹配 /api/v1/（避免与 FastAPI /api/ 冲突）
    location /api/v1/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:8082/api/v1/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Content-Type $http_content_type;
    }

    # MCP 服务 (aiohttp, 8765)
    location /mcp {
        proxy_pass http://127.0.0.1:8765/mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # 健康检查 (Flask, 8082)
    location /health {
        proxy_pass http://127.0.0.1:8082/health;
        access_log off;
    }
}
NGINXEOF

echo "新配置已写入"

echo ""
echo "===== 4. 测试 Nginx 配置 ====="
nginx -t && echo "[OK] 配置测试通过" || { echo "[FAIL] 配置测试失败"; exit 1; }

echo ""
echo "===== 5. 重载 Nginx ====="
nginx -s reload && echo "[OK] Nginx 已重载" || { echo "[FAIL] 重载失败"; exit 1; }

echo ""
echo "===== 6. 验证修复效果 ====="
sleep 1

echo "--- /api/health (应返回 200 + JSON) ---"
curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:8088/api/health
echo ""
curl -s http://127.0.0.1:8088/api/health
echo ""

echo ""
echo "--- /api/v1/dataset/list (应返回 200 + 数据集) ---"
curl -s -o /dev/null -w "HTTP %{http_code}" -H "Authorization: cj2026xirangopc0820" http://127.0.0.1:8088/api/v1/dataset/list
echo ""
curl -s -H "Authorization: cj2026xirangopc0820" http://127.0.0.1:8088/api/v1/dataset/list | head -c 200
echo ""

echo ""
echo "--- /health (Flask 后端, 应返回 200) ---"
curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:8088/health
echo ""

echo ""
echo "--- / (首页, 应返回 200) ---"
curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:8088/
echo ""

echo ""
echo "===== 修复完成 ====="
echo "如果所有检查都返回 200，则修复成功！"
echo "公网访问地址: http://171.111.219.204:8088"
