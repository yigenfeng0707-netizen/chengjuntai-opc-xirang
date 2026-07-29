#!/bin/bash
# ============================================================
# 天翼云 ECS 一键部署脚本
# NL2SQL TeleAgent + AI 内容工厂 公测版
#
# 适用系统: Ubuntu 20.04/22.04, CentOS 7/8/9, Debian 11/12
# 使用方法: sudo bash deploy_to_ctyun.sh
# 前提条件: 项目文件已上传至 /opt/nl2sql_teleagent_prod/
# ============================================================

set -e

# ==================== 配置区 ====================
APP_DIR="/opt/nl2sql_teleagent_prod"
VENV_DIR="$APP_DIR/venv"
PYTHON_BIN="python3.12"
SERVICE_USER="teleagent"

# 端口
PORT_BACKEND=8082   # znws_query_mock.py (Flask)
PORT_MCP=8765       # mcp_http_nl2sql_v3.py (aiohttp)
PORT_WEB=8090       # web_server.py (FastAPI)

# Nginx
NGINX_HTTP_PORT=80

# ==================== 颜色 ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step()  { echo -e "\n${CYAN}========== $1 ==========${NC}"; }

# ==================== 0. 前置检查 ====================
step "0. 前置检查"

if [ "$EUID" -ne 0 ]; then
    error "请用 root 或 sudo 执行：sudo bash deploy_to_ctyun.sh"
fi

if [ ! -d "$APP_DIR" ]; then
    error "项目目录不存在: $APP_DIR\n请先上传项目文件到该目录（scp / rsync / git clone）"
fi

if [ ! -f "$APP_DIR/znws_query_mock.py" ]; then
    error "未找到 znws_query_mock.py，请确认项目文件完整"
fi

info "项目目录检查通过: $APP_DIR"

# 检测操作系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID=$ID
    OS_VER=$VERSION_ID
    info "操作系统: $PRETTY_NAME"
else
    error "无法检测操作系统版本"
fi

IS_UBUNTU=false
IS_CENTOS=false
case "$OS_ID" in
    ubuntu|debian)
        IS_UBUNTU=true
        ;;
    centos|rhel|rocky|almalinux|fedora)
        IS_CENTOS=true
        ;;
    *)
        warn "未测试的发行版: $OS_ID，将按 Ubuntu 方式尝试"
        IS_UBUNTU=true
        ;;
esac

# ==================== 1. 安装系统依赖 ====================
step "1. 安装系统依赖 (Python 3.12 + Nginx)"

if [ "$IS_UBUNTU" = true ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq software-properties-common curl wget git nginx \
        python3.12 python3.12-venv python3.12-dev \
        build-essential libffi-dev libssl-dev 2>/dev/null || {
        # Ubuntu 20.04 可能需要 deadsnakes PPA
        warn "系统源无 Python 3.12，添加 deadsnakes PPA..."
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update -qq
        apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
    }
    PYTHON_BIN="python3.12"
elif [ "$IS_CENTOS" = true ]; then
    # CentOS 7/8/9
    if command -v dnf &>/dev/null; then
        PKG_MGR=dnf
    else
        PKG_MGR=yum
    fi
    $PKG_MGR install -y -q epel-release 2>/dev/null || true
    $PKG_MGR install -y -q curl wget git nginx gcc make \
        python3 python3-devel python3-pip redhat-rpm-config libffi-devel openssl-devel 2>/dev/null
    # CentOS 默认 Python 3.6/3.9，尝试安装 3.12
    if $PKG_MGR module list python3.12 &>/dev/null 2>&1; then
        $PKG_MGR module enable -y python3.12
        $PKG_MGR install -y -q python3.12 python3.12-devel
        PYTHON_BIN="python3.12"
    else
        PYTHON_BIN="python3"
        warn "CentOS 未找到 Python 3.12，使用默认 $PYTHON_BIN（可能影响部分功能）"
    fi
fi

# 验证 Python
if ! command -v $PYTHON_BIN &>/dev/null; then
    # 兜底用 python3
    PYTHON_BIN="python3"
fi
PYTHON_VER=$($PYTHON_BIN --version 2>&1)
info "Python 版本: $PYTHON_VER ($PYTHON_BIN)"

# ==================== 2. 创建服务用户 + 目录 ====================
step "2. 创建服务用户与目录"

if ! id -u $SERVICE_USER &>/dev/null; then
    useradd -r -s /sbin/nologin -d $APP_DIR $SERVICE_USER
    info "已创建系统用户: $SERVICE_USER"
else
    info "用户 $SERVICE_USER 已存在"
fi

# 创建必要目录
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/content_factory/logs"
mkdir -p "$APP_DIR/content_factory/data"
mkdir -p "$APP_DIR/content_factory/articles"
mkdir -p "$APP_DIR/content_factory/vector_db"
mkdir -p "$APP_DIR/content_factory/knowledge"

chown -R $SERVICE_USER:$SERVICE_USER "$APP_DIR"
info "目录权限已设置"

# ==================== 3. 创建 Python 虚拟环境 ====================
step "3. 创建 Python 虚拟环境"

if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_BIN -m venv "$VENV_DIR"
    info "虚拟环境已创建: $VENV_DIR"
else
    info "虚拟环境已存在，跳过"
fi

PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python"

# 升级 pip
$PIP install --upgrade pip -q -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
info "pip 已升级"

# ==================== 4. 安装 Python 依赖 ====================
step "4. 安装 Python 依赖"

# 合并所有服务的依赖
$PIP install -q \
    flask>=3.0 \
    aiohttp>=3.9 \
    requests>=2.31 \
    cachetools>=5.3 \
    pyyaml>=6.0 \
    fastapi>=0.110 \
    "uvicorn[standard]>=0.27" \
    jinja2>=3.1 \
    python-multipart>=0.0.9 \
    feedparser>=6.0 \
    reportlab>=4.0 \
    "numpy>=1.26" \
    "scikit-learn>=1.4" \
    pydantic>=2.0 \
    -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

info "所有 Python 依赖安装完成"

# 验证关键包
$PYTHON -c "import flask, aiohttp, requests, cachetools, yaml, fastapi, uvicorn, numpy, sklearn, reportlab; print('依赖验证通过')" || \
    error "依赖安装验证失败"

# ==================== 5. 生成生产环境配置 ====================
step "5. 生成生产环境配置 (config.yaml)"

# 生成随机 Token 和密码
API_TOKEN=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)
WEB_PASSWORD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 16)

CONFIG_FILE="$APP_DIR/content_factory/config.yaml"
CONFIG_BACKUP="$APP_DIR/content_factory/config.yaml.bak"

# 备份原始配置
if [ -f "$CONFIG_FILE" ] && [ ! -f "$CONFIG_BACKUP" ]; then
    cp "$CONFIG_FILE" "$CONFIG_BACKUP"
    info "原始配置已备份: config.yaml.bak"
fi

cat > "$CONFIG_FILE" << 'YAMLEOF'
# ========== 生产环境配置 (天翼云 ECS) ==========
# 由 deploy_to_ctyun.sh 自动生成

project_root: "./content_factory"
bid_pipeline_root: "/opt/nl2sql_teleagent_prod/content_factory/knowledge"
knowledge_sync_folder: "/opt/nl2sql_teleagent_prod/content_factory/knowledge/library"
vector_sync_path: "/opt/nl2sql_teleagent_prod/content_factory/vector_db"

nl2sql_mcp_url: "http://127.0.0.1:8765/mcp"
nl2sql_default_dataset: "bid_projects"
nl2sql_default_user_id: ""

nl2sql_backend:
  znws_query_url: "http://127.0.0.1:8082/api/v1"
  api_token: "${API_TOKEN}"
  mcp_host: "127.0.0.1"
  mcp_port: 8765
  cache_ttl: 300

auto_path_fix: true
network_timeout: 15
max_retry: 3
retry_interval: 10

smtp_server: ""
smtp_port: 465
smtp_user: ""
smtp_password: ""
mail_receivers: []

web_host: "127.0.0.1"
web_port: 8090
web_username: "admin"
web_password: "${WEB_PASSWORD}"

log_roll_days: 30

llm:
  enabled: true
  temperature: 0.7
  max_tokens: 8192
  enable_thinking: false
  require_real_llm: true
  providers:
    # Path B: 主办方星辰/息壤 Token 到手后注入（或设环境变量 XIRANG_API_KEY）
    - name: "primary-天翼云息壤-星辰TokenHub"
      api_base: "https://wishub-x1.ctyun.cn/v1"
      api_key: "YOUR_XIRANG_OR_TOKENHUB_API_KEY"
      api_key_env: "XIRANG_API_KEY"
      model: "DeepSeek-V3"
      enabled: true
      timeout: 90
    - name: "secondary-星辰TokenHub"
      api_base: "https://api.teleai.com.cn/v1"
      api_key: "YOUR_TOKENHUB_API_KEY"
      api_key_env: "TOKENHUB_API_KEY"
      model: "TeleChat2-35B"
      enabled: true
      timeout: 90
    # Interim: 等竞赛 Token 期间可用
    - name: "fallback-商汤SenseNova"
      api_base: "https://token.sensenova.cn/v1"
      api_key: "YOUR_SENSENOVA_API_KEY"
      api_key_env: "SENSENOVA_API_KEY"
      model: "sensenova-6.7-flash-lite"
      enabled: true
      timeout: 60
    - name: "fallback-阿里云百炼"
      api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
      api_key: "YOUR_ALIYUN_API_KEY"
      api_key_env: "DASHSCOPE_API_KEY"
      model: "qwen-plus"
      enabled: true
      timeout: 90

rss_sources: []

article:
  target_min_words: 800
  target_max_words: 4000
  require_code_block: true

reserved_ports: [8082, 8765]
YAMLEOF

# 替换占位符
sed -i "s|\${API_TOKEN}|$API_TOKEN|g" "$CONFIG_FILE"
sed -i "s|\${WEB_PASSWORD}|$WEB_PASSWORD|g" "$CONFIG_FILE"

chown $SERVICE_USER:$SERVICE_USER "$CONFIG_FILE"
chmod 600 "$CONFIG_FILE"

info "生产配置已生成: config.yaml"
warn "LLM API Key 尚未配置：优先等主办方息壤/星辰 Token；interim 可用 SenseNova/百炼；全无也可先结构 Demo"
warn "请编辑 config.yaml 或注入环境变量（勿 commit 真实 Key）"

# 保存凭据到安全文件
CRED_FILE="$APP_DIR/CREDENTIALS.txt"
cat > "$CRED_FILE" << EOF
# ==================== 生产环境凭据 ====================
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')
# 请妥善保管，不要提交到 Git
#
# NL2SQL API Token (后端鉴权):
$API_TOKEN
#
# Web 面板密码 (用户名 admin):
$WEB_PASSWORD
#
# LLM API Key 尚未配置，请编辑 config.yaml 填入
EOF
chmod 600 "$CRED_FILE"
info "凭据已保存: $CRED_FILE （请记录后删除此文件）"

# ==================== 6. 更新 users.json ====================
step "6. 更新用户密码"

USERS_FILE="$APP_DIR/content_factory/users.json"
cat > "$USERS_FILE" << EOF
{
  "users": [
    {
      "username": "admin",
      "password": "$WEB_PASSWORD",
      "role": "super_admin",
      "enabled": true,
      "created_at": "$(date '+%Y-%m-%d')"
    },
    {
      "username": "operator",
      "password": "$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 16)",
      "role": "operator",
      "enabled": true,
      "created_at": "$(date '+%Y-%m-%d')"
    }
  ],
  "roles": {
    "super_admin": ["*"],
    "operator": ["run_task", "view", "export", "queue_control", "schedule_control"]
  }
}
EOF
chmod 600 "$USERS_FILE"
info "用户密码已随机生成（见 CREDENTIALS.txt）"

# ==================== 7. 初始化数据库 ====================
step "7. 初始化数据库 (抓取浙江政采网真实数据)"

# 先创建表结构（fetch_real_data.py 只导入数据，不建表）
info "创建数据库表结构..."
$PYTHON -c "
import sqlite3, os
db_path = os.path.join('$APP_DIR', 'bid_telecom.db')
conn = sqlite3.connect(db_path)
conn.execute('''CREATE TABLE IF NOT EXISTS bid_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT,
    industry TEXT,
    region TEXT,
    bid_date TEXT,
    win_amount REAL,
    status TEXT,
    owner_user_id TEXT
)''')
conn.commit()
conn.close()
print('表 bid_projects 已就绪')
"

info "开始全量抓取...（预计 3~5 分钟）"
cd "$APP_DIR"
su -s /bin/bash $SERVICE_USER -c "$PYTHON $APP_DIR/fetch_real_data.py --full-rebuild" || {
    warn "数据抓取失败，服务仍可启动（数据库为空）"
    warn "可稍后手动执行: $PYTHON $APP_DIR/fetch_real_data.py --full-rebuild"
}

# 检查数据量
if [ -f "$APP_DIR/bid_telecom.db" ]; then
    DB_COUNT=$($PYTHON -c "import sqlite3; print(sqlite3.connect('$APP_DIR/bid_telecom.db').execute('SELECT COUNT(*) FROM bid_projects').fetchone()[0])" 2>/dev/null || echo "0")
    info "数据库记录数: $DB_COUNT 条"
else
    warn "数据库文件不存在，服务将以空库启动"
fi

# ==================== 8. 创建 systemd 服务 ====================
step "8. 创建 systemd 服务 (3 个服务)"

# --- 8.1 NL2SQL 后端 (Flask, 8082) ---
cat > /etc/systemd/system/teleagent-backend.service << EOF
[Unit]
Description=NL2SQL TeleAgent Backend (Flask, port $PORT_BACKEND)
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
ExecStart=$PYTHON $APP_DIR/znws_query_mock.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# --- 8.2 MCP 服务 (aiohttp, 8765) ---
cat > /etc/systemd/system/teleagent-mcp.service << EOF
[Unit]
Description=NL2SQL MCP Service (aiohttp, port $PORT_MCP)
After=network.target teleagent-backend.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
ExecStart=$PYTHON $APP_DIR/mcp_http_nl2sql_v3.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# --- 8.3 内容工厂 Web 面板 (FastAPI, 8090) ---
cat > /etc/systemd/system/teleagent-web.service << EOF
[Unit]
Description=AI Content Factory Web Panel (FastAPI, port $PORT_WEB)
After=network.target teleagent-mcp.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR/content_factory
ExecStart=$PYTHON $APP_DIR/content_factory/web_server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# --- 8.4 定时抓取服务 (crontab) ---
CRON_LINE="0 9 * * * $PYTHON $APP_DIR/fetch_real_data.py >> $APP_DIR/logs/cron_fetch.log 2>&1"
( crontab -l -u $SERVICE_USER 2>/dev/null | grep -v "fetch_real_data.py" ; echo "$CRON_LINE" ) | crontab -u $SERVICE_USER -
info "定时任务已设置: 每日 09:00 自动抓取增量数据"

systemctl daemon-reload
info "systemd 服务文件已创建"

# ==================== 9. 配置 Nginx 反向代理 ====================
step "9. 配置 Nginx 反向代理"

# 获取服务器公网 IP
PUBLIC_IP=$(curl -s --connect-timeout 5 http://ifconfig.me 2>/dev/null || \
            curl -s --connect-timeout 5 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || \
            echo "YOUR_SERVER_IP")

cat > /etc/nginx/sites-available/teleagent.conf << 'NGINXEOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 50M;

    # Web 面板 (FastAPI, 8090)
    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # NL2SQL API (Flask, 8082)
    location /api/ {
        proxy_pass http://127.0.0.1:8082/api/;
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

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8082/health;
        access_log off;
    }
}
NGINXEOF

# 启用站点
if [ -d /etc/nginx/sites-enabled ]; then
    ln -sf /etc/nginx/sites-available/teleagent.conf /etc/nginx/sites-enabled/teleagent.conf
    # 移除默认站点
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
elif [ -d /etc/nginx/conf.d ]; then
    cp /etc/nginx/sites-available/teleagent.conf /etc/nginx/conf.d/teleagent.conf
fi

# 测试 Nginx 配置
nginx -t 2>/dev/null && info "Nginx 配置测试通过" || warn "Nginx 配置测试失败，请检查"

systemctl enable nginx
systemctl restart nginx 2>/dev/null || systemctl start nginx
info "Nginx 已启动 (端口 $NGINX_HTTP_PORT)"

# ==================== 10. 配置防火墙 ====================
step "10. 配置防火墙"

if command -v ufw &>/dev/null; then
    ufw allow 22/tcp 2>/dev/null || true
    ufw allow 80/tcp 2>/dev/null || true
    ufw allow 443/tcp 2>/dev/null || true
    ufw --force enable 2>/dev/null || true
    info "UFW 防火墙已配置 (开放 22/80/443)"
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-port=80/tcp 2>/dev/null || true
    firewall-cmd --permanent --add-port=443/tcp 2>/dev/null || true
    firewall-cmd --permanent --add-port=22/tcp 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    info "Firewalld 已配置 (开放 22/80/443)"
else
    warn "未检测到防火墙工具，请手动在安全组放行端口 80/443"
fi

warn "同时请在天翼云控制台安全组中放行: TCP 80, 443, 22"

# ==================== 11. 启动服务 ====================
step "11. 启动服务"

systemctl restart teleagent-backend
sleep 2
systemctl restart teleagent-mcp
sleep 2
systemctl restart teleagent-web
sleep 2

systemctl enable teleagent-backend teleagent-mcp teleagent-web

info "三个服务已启动并设为开机自启"

# ==================== 12. 验证 ====================
step "12. 服务验证"

echo ""
sleep 3

check_service() {
    local name=$1
    local port=$2
    if systemctl is-active --quiet $name; then
        echo -e "  ${GREEN}✓${NC} $name (port $port) — 运行中"
    else
        echo -e "  ${RED}✗${NC} $name (port $port) — 未运行"
        warn "查看日志: journalctl -u $name -n 30"
    fi
}

check_service "teleagent-backend" $PORT_BACKEND
check_service "teleagent-mcp" $PORT_MCP
check_service "teleagent-web" $PORT_WEB

# HTTP 健康检查
echo ""
HTTP_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8082/health 2>/dev/null || echo "000")
if [ "$HTTP_CHECK" = "200" ]; then
    echo -e "  ${GREEN}✓${NC} 后端健康检查通过 (HTTP 200)"
else
    echo -e "  ${YELLOW}!${NC} 后端健康检查返回: $HTTP_CHECK (服务可能还在启动中)"
fi

NGINX_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/ 2>/dev/null || echo "000")
if [ "$NGINX_CHECK" != "000" ]; then
    echo -e "  ${GREEN}✓${NC} Nginx 反向代理正常 (HTTP $NGINX_CHECK)"
else
    echo -e "  ${YELLOW}!${NC} Nginx 响应异常"
fi

# ==================== 13. 输出摘要 ====================
step "部署完成"

cat << SUMMARY

╔══════════════════════════════════════════════════════════╗
║              天翼云 ECS 部署完成                          ║
╠══════════════════════════════════════════════════════════╣
║
║  服务地址:
║    Web 面板:    http://$PUBLIC_IP/
║    NL2SQL API:  http://$PUBLIC_IP/api/
║    MCP 服务:    http://$PUBLIC_IP/mcp
║
║  内部端口:
║    后端 (Flask):   $PORT_BACKEND
║    MCP (aiohttp):  $PORT_MCP
║    Web (FastAPI):  $PORT_WEB
║
║  凭据 (见 $CRED_FILE):
║    API Token:  $API_TOKEN
║    Web 密码:   $WEB_PASSWORD
║
║  管理命令:
║    重启后端:  systemctl restart teleagent-backend
║    重启MCP:   systemctl restart teleagent-mcp
║    重启Web:   systemctl restart teleagent-web
║    查看日志:  journalctl -u teleagent-backend -f
║    重启Nginx: systemctl restart nginx
║    手动抓取:  $PYTHON $APP_DIR/fetch_real_data.py --full-rebuild
║
║  下一步:
║    1. LLM: 优先 XIRANG_API_KEY（主办方星辰/息壤）；interim 可用 SenseNova/百炼
║       无 Key 也可先公网结构 Demo（看板无 Key 横幅）。详见 docs/CTYUN_TRIAL.md
║    2. 天翼云控制台 → 安全组 → 放行 TCP 80/443/22
║    3. 浏览器访问 http://$PUBLIC_IP/ 验证
║    4. 记录凭据后删除 CREDENTIALS.txt（勿把 Key/密码提交 Git）
║
╚══════════════════════════════════════════════════════════╝

SUMMARY

info "部署脚本执行完毕"
