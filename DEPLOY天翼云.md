# 天翼云 ECS 部署手册 — 成军台（OPC OS on 息壤）/ NL2SQL TeleAgent + AI 内容工厂

> 版本: 1.2 | 更新: 2026-07-29 | 适用: 天翼云 ECS (Ubuntu 22.04 / CentOS 8+)
> 产品升级：本仓库已升维为「成军台」参赛交付版，Web 默认入口为成军看板（端口 8090）。
>
> **参赛双路径**：可先用 **ECS 免费试用** 部署公网 Demo（不必等星辰 Token）；主办方发放息壤/星辰 Key 后再切 primary LLM。  
> 精简清单与话术 → [`docs/CTYUN_TRIAL.md`](./docs/CTYUN_TRIAL.md)

---

## 目录

1. [概述](#1-概述)
2. [前置条件](#2-前置条件)
3. [开通天翼云 ECS](#3-开通天翼云-ecs)
4. [配置安全组](#4-配置安全组)
5. [上传项目文件](#5-上传项目文件)
6. [执行一键部署](#6-执行一键部署)
7. [配置 LLM API Key](#7-配置-llm-api-key)
8. [验证部署](#8-验证部署)
9. [日常运维](#9-日常运维)
10. [生产加固清单](#10-生产加固清单)
11. [故障排查](#11-故障排查)

---

## 1. 概述

本项目包含两个子系统，部署后会以三个 systemd 服务 + Nginx 反向代理的架构运行：

| 服务 | 端口 | 说明 |
|------|------|------|
| NL2SQL 后端 | 8082 | Flask，电信投标数据查询 + 自然语言转 SQL |
| MCP 服务 | 8765 | aiohttp，MCP 协议接入层 |
| 内容工厂 Web | 8090 | FastAPI，Web 管理面板 |
| Nginx | 80 | 反向代理，对外统一入口 |

数据库：SQLite（`bid_telecom.db`），当前 60 条浙江省政采网真实通信类项目数据。

数据来源：浙江省政府采购网（zfcg.czt.zj.gov.cn），自动抓取，每日 09:00 增量更新。

---

## 2. 前置条件

- 天翼云账号（可先走 **免费试用**；企业实名按控制台要求）
- 本地项目目录完整（本仓库 `chengjuntai/`，或历史路径 `nl2sql_teleagent_prod/`）
- **LLM Key（可延后）**：
  - **正式 primary**：星辰 TokenHub / 息壤 Key（常由主办方发放；未到手也可先部署结构 Demo）
  - **Interim 真实 E2E（可选）**：商汤 SenseNova 或阿里云百炼
  - **全无 Key**：公网仍可上线看板 + 显式无 Key 横幅（禁止静默 mock）
- SSH 客户端（Windows 自带 OpenSSH 或 PuTTY）
- SCP/WinSCP 文件传输工具

---

## 3. 开通天翼云 ECS

### 3.1 免费试用（7 天）

1. 访问 https://www.ctyun.cn/act/trial/central
2. 选择「云主机 ECS」免费试用
3. 配置选择：
   - 规格：4 核 8G（免费试用默认）
   - 系统盘：60G
   - 带宽：3M
   - 操作系统：**Ubuntu 22.04**（推荐）或 CentOS 8
4. 设置 root 密码并记录

### 3.2 付费购买（试用期后）

1. 访问天翼云控制台 → 弹性云主机
2. 推荐配置（公测）：
   - 规格：4 核 8G（s6.large.2 或同等）
   - 系统盘：40G SSD
   - 带宽：5M 按流量计费
3. **电信员工**: 拨打 400-810-9889 转 1 咨询内部补贴政策

### 3.3 记录服务器信息

部署完成后，记录以下信息：
- 公网 IP：`xxx.xxx.xxx.xxx`
- 内网 IP：`xxx.xxx.xxx.xxx`
- root 密码

---

## 4. 配置安全组

天翼云控制台 → 云主机 → 安全组 → 创建安全组

### 入站规则（必填）

| 协议 | 端口 | 来源 | 说明 |
|------|------|------|------|
| TCP | 22 | 你的 IP/32 | SSH 管理 |
| TCP | 80 | 0.0.0.0/0 | HTTP 公测访问 |
| TCP | 443 | 0.0.0.0/0 | HTTPS（后续启用） |

> 8082/8765/8090 端口不需要对外开放，Nginx 会通过 127.0.0.1 内部转发。

### 出站规则

默认全部放行即可。

---

## 5. 上传项目文件

### 方式 A：SCP 命令行（推荐）

在 Windows 终端执行：

```powershell
# 打包项目（排除不必要的文件）
cd D:\
tar -czf nl2sql_teleagent_prod.tar.gz `
  --exclude="nl2sql_teleagent_prod/__pycache__" `
  --exclude="nl2sql_teleagent_prod/.temp" `
  --exclude="nl2sql_teleagent_prod/archive" `
  --exclude="nl2sql_teleagent_prod/bid_telecom.db" `
  --exclude="nl2sql_teleagent_prod/logs" `
  nl2sql_teleagent_prod/

# 上传到 ECS
scp nl2sql_teleagent_prod.tar.gz root@你的公网IP:/opt/

# SSH 登录 ECS
ssh root@你的公网IP
```

在 ECS 上解压：

```bash
mkdir -p /opt/nl2sql_teleagent_prod
cd /opt
tar -xzf nl2sql_teleagent_prod.tar.gz
ls /opt/nl2sql_teleagent_prod/  # 确认文件
```

### 方式 B：WinSCP 图形界面

1. 下载安装 WinSCP
2. 连接 ECS（SFTP 协议，公网 IP，root 账号）
3. 将 `D:\nl2sql_teleagent_prod\` 整个目录拖入 `/opt/`

### 方式 C：Git 克隆（如已推送到仓库）

```bash
cd /opt
git clone https://github.com/你的用户名/nl2sql_teleagent_prod.git
```

---

## 6. 执行一键部署

SSH 登录 ECS 后执行：

```bash
cd /opt/nl2sql_teleagent_prod
sudo bash deploy_to_ctyun.sh
```

脚本会自动完成：
1. 安装 Python 3.12 + Nginx
2. 创建虚拟环境 + 安装所有依赖
3. 生成生产配置（随机 Token / 密码）
4. 抓取浙江政采网 60 条真实数据（约 3-5 分钟）
5. 创建 3 个 systemd 服务 + 定时任务
6. 配置 Nginx 反向代理
7. 配置防火墙
8. 启动服务并验证

部署完成后，终端会显示凭据和服务地址。

---

## 7. 配置 LLM API Key

部署脚本生成的 `config.yaml` 中 LLM API Key 为占位符。  
**推荐顺序**：主办方息壤/星辰（Path B）→ interim SenseNova/百炼 → 全无则保持占位 + 看板无 Key 横幅。

也可用环境变量（优先，避免把 Key 写进文件）：`XIRANG_API_KEY` / `TOKENHUB_API_KEY` / `SENSENOVA_API_KEY` / `DASHSCOPE_API_KEY`。  
完整模板见仓库 `content_factory/config.yaml.example`；双路径说明见 `docs/CTYUN_TRIAL.md`。

```bash
nano /opt/nl2sql_teleagent_prod/content_factory/config.yaml
# 或本仓库路径：
# nano /opt/chengjuntai/content_factory/config.yaml
```

找到 `llm.providers` 部分，按需替换：

### 方案 A：天翼云息壤 / 星辰 TokenHub（参赛 primary · 主办方 Token 到手后）

```yaml
    - name: "primary-天翼云息壤-星辰TokenHub"
      api_base: "https://wishub-x1.ctyun.cn/v1"   # 以主办方/控制台实际地址为准
      api_key: "主办方发放的Key"                 # 或留占位，改用环境变量 XIRANG_API_KEY
      api_key_env: "XIRANG_API_KEY"
      model: "DeepSeek-V3"                       # 以主办方可用模型为准
      enabled: true
      timeout: 90
```

> 息壤相关产品页：https://www.ctyun.cn/products/xisiang  
> 优势：赛事主链路、模型徽章可展示息壤/星辰，符合预赛叙事。

### 方案 B：商汤 SenseNova（Interim 真实 E2E · 等 Token 期间）

```yaml
    - name: "fallback-商汤SenseNova"
      api_base: "https://token.sensenova.cn/v1"
      api_key: "sk-你的真实Key"        # ← 替换这里；或 SENSENOVA_API_KEY
      api_key_env: "SENSENOVA_API_KEY"
      model: "sensenova-6.7-flash-lite"
      enabled: true
      timeout: 60
```

### 方案 C：阿里云百炼 DashScope（Interim 兜底）

```yaml
    - name: "fallback-阿里云百炼"
      api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
      api_key: "sk-你的DashScopeKey"
      api_key_env: "DASHSCOPE_API_KEY"
      model: "qwen-plus"
      enabled: true
      timeout: 90
```

填入后保存，重启服务：

```bash
systemctl restart teleagent-backend teleagent-mcp teleagent-web
```

---

## 8. 验证部署

### 8.1 服务状态

```bash
systemctl status teleagent-backend
systemctl status teleagent-mcp
systemctl status teleagent-web
# 三个服务都应显示 active (running)
```

### 8.2 健康检查

```bash
# 后端健康检查
curl http://127.0.0.1:8082/health

# 通过 Nginx 访问
curl http://127.0.0.1/health
```

### 8.3 浏览器访问

打开 `http://你的公网IP/`

- 用户名：`admin`
- 密码：见 `/opt/nl2sql_teleagent_prod/CREDENTIALS.txt`

### 8.4 NL2SQL 验证

在 Web 面板中测试以下自然语言查询：

```
1. 浙江省通信类项目总金额是多少？
2. 按地区统计项目数量
3. 按行业分类统计金额
4. 金额最高的5个项目
5. 2025年6月以来的项目有多少？
6. 中标状态分布
7. 政企信息化类项目的平均金额
```

### 8.5 命令行验证

```bash
cd /opt/nl2sql_teleagent_prod
source venv/bin/activate
python test_nl2sql_7.py
# 预期：7/7 全部正确
```

---

## 9. 日常运维

### 9.1 服务管理

```bash
# 重启单个服务
systemctl restart teleagent-backend
systemctl restart teleagent-mcp
systemctl restart teleagent-web

# 查看日志
journalctl -u teleagent-backend -f     # 实时跟踪
journalctl -u teleagent-mcp -f
journalctl -u teleagent-web -f
journalctl -u teleagent-backend -n 100  # 最近100行

# 查看所有服务状态
systemctl status teleagent-{backend,mcp,web}
```

### 9.2 数据更新

```bash
# 手动全量重建
cd /opt/nl2sql_teleagent_prod
source venv/bin/activate
python fetch_real_data.py --full-rebuild

# 仅抓取不导入（检查数据）
python fetch_real_data.py --fetch-only

# 定时任务已自动配置（每日 09:00）
crontab -l -u teleagent
```

### 9.3 Nginx 管理

```bash
systemctl restart nginx
nginx -t                          # 测试配置
tail -f /var/log/nginx/access.log # 访问日志
tail -f /var/log/nginx/error.log  # 错误日志
```

### 9.4 修改配置

```bash
# 编辑配置
nano /opt/nl2sql_teleagent_prod/content_factory/config.yaml

# 修改后重启
systemctl restart teleagent-backend teleagent-mcp teleagent-web
```

### 9.5 修改 Web 面板密码

```bash
# 方式1：编辑 config.yaml 中 web_password 字段
# 方式2：编辑 users.json
nano /opt/nl2sql_teleagent_prod/content_factory/users.json

systemctl restart teleagent-web
```

---

## 10. 生产加固清单

公测阶段满足基本安全要求，正式上线前需完成以下加固：

### 10.1 必须（上线前）

- [ ] **HTTPS**: 配置 SSL 证书（天翼云免费 SSL 或 Let's Encrypt）
  ```bash
  apt install certbot python3-certbot-nginx
  certbot --nginx -d 你的域名
  ```
- [ ] **更换所有默认密码**: CREDENTIALS.txt 中的 Token / 密码已随机，但需确认已修改
- [ ] **删除凭据文件**: 记录密码后删除 `CREDENTIALS.txt`
- [ ] **LLM Key 降级**: 从个人阿里云 API 切换为天翼云息壤或企业商汤账号
- [ ] **SSH 密钥登录**: 禁用 root 密码登录，改用密钥对
  ```bash
  # 编辑 /etc/ssh/sshd_config
  PermitRootLogin prohibit-password
  PasswordAuthentication no
  systemctl restart sshd
  ```

### 10.2 建议（公测稳定后）

- [ ] **数据库迁移**: SQLite → 天翼云 MySQL（高可用 + 备份）
- [ ] **日志持久化**: 接入天翼云日志服务
- [ ] **监控告警**: 天翼云云监控 + 告警通知（CPU/内存/带宽/端口）
- [ ] **自动备份**: 每日打包 `bid_telecom.db` + `articles/` 到天翼云对象存储
- [ ] **CDN 加速**: 天翼云 CDN 加速静态资源
- [ ] **DDoS 防护**: 天翼云DDoS高防（如遇攻击）

### 10.3 架构演进（正式生产）

- [ ] **多实例**: 前端 Nginx + 多个后端实例 + 天翼云 ELB 负载均衡
- [ ] **Redis 缓存**: 替换 cachetools 内存缓存，支持多进程共享
- [ ] **消息队列**: 天翼云 DMS（Kafka）替代内存任务队列
- [ ] **容器化**: 用已有的 Dockerfile + docker-compose 部署

---

## 11. 故障排查

### 服务启动失败

```bash
# 查看详细错误
journalctl -u teleagent-backend -n 50 --no-pager
journalctl -u teleagent-mcp -n 50 --no-pager
journalctl -u teleagent-web -n 50 --no-pager
```

### 常见问题

**Q: Python 3.12 安装失败（CentOS）**

CentOS 7 默认只有 Python 3.6。推荐使用 Ubuntu 22.04 镜像。如必须用 CentOS，可通过源码编译安装 Python 3.12，或使用 SCL 软件源。

**Q: Nginx 502 Bad Gateway**

后端服务未启动或正在重启。等待 5 秒后刷新。如持续 502：
```bash
systemctl restart teleagent-backend teleagent-mcp teleagent-web
sleep 3
curl http://127.0.0.1:8082/health
```

**Q: 数据抓取失败（fetch_real_data.py 报错）**

浙江政采网可能有反爬限制。检查：
```bash
cd /opt/nl2sql_teleagent_prod
source venv/bin/activate
python fetch_real_data.py --full-rebuild 2>&1 | tail -20
```
如持续失败，等待 10-30 分钟后重试（IP 频率限制会自动解除）。

**Q: NL2SQL 查询返回"降级为规则模式"**

LLM API Key 未配置或已失效。检查 config.yaml 中的 `llm.providers`，确认：
1. `api_key` 已填入真实 Key（非占位符）
2. `enabled: true`
3. 对应的 API 服务可用

```bash
# 快速测试 LLM 连通性
source /opt/nl2sql_teleagent_prod/venv/bin/activate
python -c "
import sys; sys.path.insert(0, '/opt/nl2sql_teleagent_prod/content_factory')
import llm_client
print(llm_client.call_llm('你好，请回复OK'))
"
```

**Q: 端口被占用**

```bash
# 查看端口占用
ss -tlnp | grep -E '8082|8765|8090|80'

# 杀掉占用进程
kill -9 <PID>

# 重启服务
systemctl restart teleagent-backend teleagent-mcp teleagent-web
```

**Q: 磁盘空间不足**

```bash
# 查看磁盘
df -h

# 清理日志（保留最近 7 天）
find /opt/nl2sql_teleagent_prod/logs -name "*.log" -mtime +7 -delete
journalctl --vacuum-time=7d
```

---

## 附录：架构图

```
                    Internet
                       |
                  [天翼云 ECS]
                       |
                   [Nginx :80]
                   /    |    \
                  /     |     \
        [Flask:8082] [aiohttp:8765] [FastAPI:8090]
              |           |              |
           [SQLite DB]   MCP协议      Web面板
          bid_telecom.db
              |
        [政采网抓取]
      fetch_real_data.py
      (每日 09:00 自动)
```

---

## 附录：文件清单

```
/opt/nl2sql_teleagent_prod/
├── deploy_to_ctyun.sh          ← 部署脚本
├── znws_query_mock.py           ← 后端服务 (8082)
├── mcp_http_nl2sql_v3.py        ← MCP 服务 (8765)
├── fetch_real_data.py           ← 数据抓取
├── logger_config.py             ← 日志配置
├── test_nl2sql_7.py             ← 验证脚本
├── bid_telecom.db               ← SQLite 数据库
├── venv/                        ← Python 虚拟环境
├── CREDENTIALS.txt              ← 凭据（部署后删除）
├── content_factory/
│   ├── web_server.py            ← Web 面板 (8090)
│   ├── config.yaml              ← 统一配置
│   ├── users.json               ← 用户认证
│   ├── data_feedback.py         ← 数据回流层
│   ├── topic_collector.py       ← 选题采集
│   ├── agents.py                ← 多Agent写作
│   ├── llm_client.py            ← LLM 客户端
│   └── ...                      ← 其他模块
├── logs/                        ← 运行日志
└── /etc/systemd/system/
    ├── teleagent-backend.service
    ├── teleagent-mcp.service
    └── teleagent-web.service
```

> AI生成