#!/bin/bash
# ECS 一键修复脚本：数据同步 + Werkzeug升级 + 服务重启
# 用法：在ECS上以root身份执行 bash fix_ecs_production.sh

set -euo pipefail

APP_DIR="/opt/nl2sql_teleagent_prod"
VENV="$APP_DIR/venv/bin"

echo "=== 成军台 ECS 生产修复脚本 ==="
echo "执行时间: $(date)"
echo ""

# Step 1: 检查数据目录
echo "=== 1. 检查数据目录 ==="
if [ ! -d "$APP_DIR/content_factory/data/campaigns" ]; then
    echo "  campaigns 目录不存在，创建中..."
    mkdir -p "$APP_DIR/content_factory/data/campaigns"
fi

CAMP_COUNT=$(ls "$APP_DIR/content_factory/data/campaigns/" 2>/dev/null | grep -c '\.json$' || echo 0)
echo "  当前战役文件: $CAMP_COUNT 个"

# Step 2: 如果数据为空，提示需要手动上传
if [ "$CAMP_COUNT" -eq 0 ]; then
    echo ""
    echo "  ⚠ 数据目录为空！你需要从本地上传 data/ 目录到ECS:"
    echo "     scp -r content_factory/data/* root@171.111.219.204:$APP_DIR/content_factory/data/"
    echo ""
    echo "  或运行 git pull 获取最新数据。"
    echo "  当前跳过数据同步，继续修复Werkzeug..."
fi

# Step 3: 修复Werkzeug版本
echo ""
echo "=== 2. 检查并修复Werkzeug版本 ==="

Werkzeug_VER=$($VENV/python -c "import werkzeug; print(werkzeug.__version__)" 2>/dev/null || echo "unknown")
echo "  当前Werkzeug: $Werkzeug_VER"

# 测试scrypt支持
SCRYPT_TEST=$($VENV/python -c "
from werkzeug.security import check_password_hash
try:
    result = check_password_hash('scrypt:32768:8:1\$RC9aUYCD8Bzszcc6\$c10c587b54b574fc85c6db0cbf326667f3c6ac04226dc54928881ea61c9e9825d67f421916d426a8b5954c07f342b596296c363308285bc39ccef7e7241610a0', 'chengjun2026')
    print('OK')
except Exception as e:
    print('FAIL:', str(e))
" 2>&1 || echo "FAIL: import error")

echo "  scrypt支持: $SCRYPT_TEST"

if [[ "$SCRYPT_TEST" != OK* ]]; then
    echo "  ⚠ Werkzeug版本不兼容，正在升级..."
    $VENV/pip install --force-reinstall "werkzeug>=3.0" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
    
    # 重新验证
    SCRYPT_TEST2=$($VENV/python -c "
from werkzeug.security import check_password_hash
try:
    result = check_password_hash('scrypt:32768:8:1\$RC9aUYCD8Bzszcc6\$c10c587b54b574fc85c6db0cbf326667f3c6ac04226dc54928881ea61c9e9825d67f421916d426a8b5954c07f342b596296c363308285bc39ccef7e7241610a0', 'chengjun2026')
    print('OK')
except Exception as e:
    print('FAIL:', str(e))
" 2>&1 || echo "FAIL")
    echo "  升级后scrypt支持: $SCRYPT_TEST2"
fi

# Step 4: 重启服务
echo ""
echo "=== 3. 重启服务 ==="
systemctl restart teleagent-web teleagent-backend teleagent-mcp
echo "  服务已重启"

# Step 5: 等待服务启动
echo ""
echo "=== 4. 等待服务启动（5秒）==="
sleep 5

# Step 6: 验证
echo ""
echo "=== 5. 验证 ==="

# 测试登录
LOGIN_RES=$(curl -s -X POST http://127.0.0.1:8090/api/login \
    -H "Content-Type: application/json" \
    -d '{"u":"admin","p":"chengjun2026"}' 2>/dev/null || echo "{\"error\":\"connection failed\"}")

if echo "$LOGIN_RES" | grep -q '"token"'; then
    TOKEN=$(echo "$LOGIN_RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('token',''))" 2>/dev/null || echo "")
    echo "  ✅ 登录成功，token: ${TOKEN:0:20}..."
    
    # 验证战役列表
    CAMPS=$(curl -s http://127.0.0.1:8090/api/campaigns \
        -H "Authorization: Bearer $TOKEN" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "?")
    echo "  ✅ 战役数: $CAMPS"
    
    # 验证产物中心
    ARTS=$(curl -s http://127.0.0.1:8090/api/artifacts/center \
        -H "Authorization: Bearer $TOKEN" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); ca=d.get('campaign_artifacts',[]); print(len(ca))" 2>/dev/null || echo "?")
    echo "  ✅ 产物数: $ARTS"
    
    # 验证标讯
    BIDS=$(curl -s http://127.0.0.1:8090/api/bid/projects \
        -H "Authorization: Bearer $TOKEN" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "?")
    echo "  ✅ 标讯数: $BIDS"
    
    echo ""
    echo "✅ 修复完成！请访问 http://171.111.219.204:8088 验证"
else
    ERR=$(echo "$LOGIN_RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','unknown'))" 2>/dev/null || echo "$LOGIN_RES")
    echo "  ❌ 登录失败: $ERR"
    echo ""
    echo "  可能原因:"
    echo "    1. 数据目录为空（需要上传本地data/目录）"
    echo "    2. users.json 密码哈希有问题"
    echo "    3. Werkzeug升级未生效（请检查pip输出）"
    echo ""
    echo "  排查命令:"
    echo "    systemctl status teleagent-web --no-pager"
    echo "    journalctl -u teleagent-web -n 20 --no-pager"
fi

echo ""
echo "=== 修复日志完成 ==="
