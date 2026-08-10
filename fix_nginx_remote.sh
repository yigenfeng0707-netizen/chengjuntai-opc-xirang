#!/bin/bash
# ============================================================
# Nginx HTTPS 配置脚本 - opcopcos.cn (8443 端口, DNS-01 验证)
# 在 ECS VNC 终端以 root 执行: bash fix_nginx_remote.sh
#
# 背景:
#   国内 80/443 需 ICP 备案，运营商封禁未备案域名的 80/443 端口
#   故使用 8443 端口 + Let's Encrypt 证书 (DNS-01 验证, 走阿里云 DNS API)
#
# 功能:
#   1. 安装 certbot + certbot-dns-aliyun 插件
#   2. 写入阿里云 DNS 凭据 (~/.aliyun_dns.ini, 权限 600)
#   3. 通过 DNS-01 验证申请 Let's Encrypt 通配符证书 (*.opcopcos.cn + opcopcos.cn)
#   4. 部署 Nginx HTTPS 配置 (8443) + 保留 8088 降级备份
#   5. 设置证书自动续期
#
# 前提:
#   - 域名 opcopcos.cn 已解析到本机公网 IP（@ 和 www 都要解析）
#   - 天翼云安全组已放行 TCP 8443 + 8088
#   - 阿里云 AccessKey 有 DNS 管理权限（AliyunDNSFullAccess）
# ============================================================

set -e

DOMAIN="opcopcos.cn"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"

# ↓↓↓ 阿里云 DNS 凭据（DNS-01 验证用，请替换为实际值）↓↓↓
ALIYUN_AK_ID="<YOUR_ALIYUN_AK_ID>"
ALIYUN_AK_SECRET="<YOUR_ALIYUN_AK_SECRET>"

# ↓↓↓ 证书到期通知邮箱（可留空）↓↓↓
CERT_EMAIL=""

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step()  { echo -e "\n${CYAN}========== $1 ==========${NC}"; }

if [ "$EUID" -ne 0 ]; then
    error "请用 root 或 sudo 执行：sudo bash fix_nginx_remote.sh"
fi

# ==================== 0. 定位配置文件 ====================
step "0. 定位 Nginx 配置文件"
CONF_FILE=""
for f in /etc/nginx/sites-enabled/teleagent.conf \
         /etc/nginx/conf.d/teleagent.conf \
         /etc/nginx/sites-available/teleagent.conf; do
    if [ -f "$f" ]; then CONF_FILE="$f"; break; fi
done
if [ -z "$CONF_FILE" ]; then
    error "未找到 teleagent.conf，请先运行 deploy_to_ctyun.sh 部署基础 Nginx 配置"
fi
info "配置文件: $CONF_FILE"
cp "$CONF_FILE" "${CONF_FILE}.bak.$(date +%Y%m%d%H%M%S)"
info "原配置已备份"

# ==================== 1. 安装 certbot + aliyun 插件 ====================
step "1. 安装 certbot + certbot-dns-aliyun"

# 优先用 pip 在虚拟环境安装（兼容 CTyunOS/CentOS 等无 certbot 包的系统）
CERTBOT_VENV="/opt/certbot-venv"
CERTBOT_BIN="$CERTBOT_VENV/bin/certbot"

if [ ! -f "$CERTBOT_BIN" ]; then
    info "创建 certbot 虚拟环境: $CERTBOT_VENV"
    # 确保有 venv 模块
    if ! python3 -c "import venv" 2>/dev/null; then
        if command -v dnf &>/dev/null; then
            dnf install -y -q python3-devel gcc 2>/dev/null || true
        fi
    fi
    python3 -m venv "$CERTBOT_VENV"
    "$CERTBOT_VENV/bin/pip" install --upgrade pip --quiet -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
fi

# 安装 certbot + aliyun 插件（如未装）
if ! "$CERTBOT_VENV/bin/pip" show certbot &>/dev/null 2>&1; then
    info "安装 certbot + certbot-dns-aliyun (通过 pip)..."
    "$CERTBOT_VENV/bin/pip" install --quiet \
        certbot certbot-nginx certbot-dns-aliyun \
        -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com 2>&1 | tail -5
fi

# 链接到系统 PATH
ln -sf "$CERTBOT_BIN" /usr/local/bin/certbot

# 验证
if command -v certbot &>/dev/null && certbot plugins 2>&1 | grep -q dns-aliyun; then
    info "certbot + dns-aliyun 插件就绪: $(certbot --version 2>&1)"
else
    error "certbot-dns-aliyun 安装失败。可手动执行: $CERTBOT_VENV/bin/pip install certbot certbot-dns-aliyun"
fi

# ==================== 2. 写入阿里云 DNS 凭据 ====================
step "2. 写入阿里云 DNS 凭据"
ALIYUN_INI="/root/.aliyun_dns.ini"
cat > "$ALIYUN_INI" << EOF
dns_aliyun_access_key = "$ALIYUN_AK_ID"
dns_aliyun_access_key_secret = "$ALIYUN_AK_SECRET"
EOF
chmod 600 "$ALIYUN_INI"
info "凭据已写入: $ALIYUN_INI (权限 600)"

# ==================== 3. 申请 SSL 证书 (DNS-01) ====================
step "3. 申请 SSL 证书 (DNS-01 验证)"
if [ -f "$CERT_DIR/fullchain.pem" ]; then
    info "证书已存在，跳过申请: $CERT_DIR/fullchain.pem"
else
    info "开始向 Let's Encrypt 申请证书（DNS-01 验证，域名: $DOMAIN + *.$DOMAIN）"
    # certbot 5.x 需要显式指定 authenticator 插件
    CERTBOT_ARGS="certonly --non-interactive --agree-tos --no-eff-email \
        --authenticator dns-aliyun \
        --dns-aliyun-credentials $ALIYUN_INI \
        --dns-aliyun-propagation-seconds 30 \
        -d $DOMAIN -d *.$DOMAIN"

    if [ -n "$CERT_EMAIL" ]; then
        certbot $CERTBOT_ARGS -m "$CERT_EMAIL"
    else
        warn "未设置 CERT_EMAIL，将不注册到期通知邮箱"
        certbot $CERTBOT_ARGS --register-unsafely-without-email
    fi
    info "证书申请完成: $CERT_DIR"
fi

# ==================== 4. 部署 HTTPS Nginx 配置 ====================
step "4. 部署 Nginx HTTPS 配置 (8088 端口)"
# 方案说明：
#   - 80/443 因 ICP 备案被运营商封禁
#   - 8443 规则加错安全组（sg-or32mfxs0x 没绑定到 ECS，ECS 绑的是 Default-Security-Group）
#   - 8088 已在 Default-Security-Group 放行，直接复用 8088 做 HTTPS
#   - 不再单独保留 HTTP 降级备份端口（8088 本身是备用端口，评委用手机 4G/公网能访问即可）
cat > "$CONF_FILE" << 'NGINX_HTTPS'
# 限流区域定义
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# ---------- HTTPS(8088): 主服务 ----------
server {
    listen 8088 ssl http2;
    server_name opcopcos.cn;

    ssl_certificate     /etc/letsencrypt/live/opcopcos.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/opcopcos.cn/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    client_max_body_size 50M;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location / {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /api/v1/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:8082/api/v1/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Content-Type $http_content_type;
        proxy_connect_timeout 10s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /mcp {
        proxy_pass http://127.0.0.1:8765/mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_connect_timeout 10s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /health {
        proxy_pass http://127.0.0.1:8082/health;
        access_log off;
    }
}
NGINX_HTTPS

nginx -t 2>/dev/null && info "Nginx 配置测试通过" || error "Nginx 配置测试失败"
nginx -s reload
info "Nginx 已重载"

# ==================== 5. 设置证书自动续期 ====================
step "5. 设置证书自动续期"
CRON_LINE="0 3 * * * $CERTBOT_BIN renew --quiet --post-hook 'nginx -s reload'"
( crontab -l 2>/dev/null | grep -v "certbot renew" ; echo "$CRON_LINE" ) | crontab -
info "已添加 cron: 每天 03:00 检查续期"

# ==================== 6. 验证 ====================
step "6. 验证 HTTPS 服务"
sleep 2

echo ""
echo "--- 本地 curl: https://127.0.0.1:8088/api/health ---"
HTTP_LOCAL=$(curl -sk -o /dev/null -w "%{http_code}" https://127.0.0.1:8088/api/health 2>/dev/null || echo "000")
echo "HTTP $HTTP_LOCAL"

echo ""
echo "--- 外网 curl: https://$DOMAIN:8088/api/health ---"
HTTP_REMOTE=$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 10 https://$DOMAIN:8088/api/health 2>/dev/null || echo "000")
echo "HTTP $HTTP_REMOTE"

echo ""
echo "--- 证书信息 ---"
openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -subject -dates 2>/dev/null || warn "无法读取证书信息"

echo ""
echo "===== 配置完成 ====="
if [ "$HTTP_LOCAL" = "200" ]; then
    echo -e "  ${GREEN}✓${NC} HTTPS 服务正常 (8088)"
    echo ""
    echo "  主访问地址: https://$DOMAIN:8088"
    echo ""
    echo "  如需查看证书: ls -la $CERT_DIR/"
    echo "  手动续期测试: certbot renew --dry-run"
else
    echo -e "  ${YELLOW}!${NC} HTTPS 健康检查返回 $HTTP_LOCAL（服务可能还在启动中）"
fi
