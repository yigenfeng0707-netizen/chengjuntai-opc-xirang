# 生产加固清单（Phase 3）

依据 `DEPLOY天翼云.md` 第十章，成军台上线前完成：

## 必须

1. **HTTPS**：certbot 或天翼云证书；强制跳转 443
2. **密钥治理**：仅环境变量 / 密钥托管；删除服务器 `CREDENTIALS.txt`
3. **账号**：修改 admin/operator；保留 judge 只读；关闭演示默认密码
4. **关闭 mock**：`demo_mode.allow_mock_llm: false`，`llm.require_real_llm: true`
5. **备份**：每日打包 `data/campaigns` + SQLite 到对象存储（脚本见 `scripts/backup_campaigns.sh`）

## 建议

- SQLite → 天翼云 MySQL
- 云监控告警（CPU/内存/8090 探活）
- Nginx 限流与 fail2ban
- 操作审计日志保留 ≥30 天

## 评委账号策略

| 账号 | 角色 | 权限 |
|------|------|------|
| admin | super_admin | 全权限（勿公开密码） |
| operator | operator | 可跑战役 |
| judge | guest | 只读查看 |

## 本地可做（Agent / 预赛）

| 勾选 | 事项 | 说明 |
|:----:|------|------|
| [x] | **gitignore 审计** | `users.json` / `config.yaml` / `ADMIN_ACCESS.local.md` / `*.env` / `export_docx/` / `bid_workspace/` / `schedule_config.json` 已忽略 |
| [x] | **新注册密码哈希** | `auth_users`：werkzeug 哈希；旧演示账号明文仍可登录，成功后惰性升级 |
| [x] | **公网默认密码横幅** | `CHENGJUNTAI_PUBLIC=1` 或 `config.public_deploy: true` 时，登录页强提醒改密（不打印口令） |
| [ ] | **公网改密** | 用户在 ECS 上改 admin/operator（勿 commit 新密） |
| [ ] | **HTTPS** | 用户侧证书 / Nginx |
| [ ] | **关 mock** | 公网 config 确认 `allow_mock_llm: false` |

### 公网部署旗标

```bash
# 环境变量（推荐）
export CHENGJUNTAI_PUBLIC=1

# 或 config.yaml（勿提交含密钥的 config）
public_deploy: true
```

登录页在 `public_deploy` 且演示账号仍启用时显示橙色安全横幅。

### 密码策略摘要

- **新注册 / add_user / change_password**：写入 werkzeug 哈希
- **旧明文演示账号**：仍可登录；登录成功后自动改为哈希
- **会话 / 用户洞察**：公开 API 不返回 password 字段

## 健康检查

```bash
python scripts/health_check.py
curl http://127.0.0.1:8090/api/health
```

`/api/health` 含 `password_hygiene`（无口令）、`scheduler`、`auth.password_hashing`。
