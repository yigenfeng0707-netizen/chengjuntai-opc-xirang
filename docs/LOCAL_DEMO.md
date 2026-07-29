# 本地 / 公网 Demo 说明

> 报名状态：已报名。预赛冲刺见 `NEXT_SPRINT.md`。  
> **双路径**：天翼云试用公网（现在）∥ 等主办方星辰/息壤 Token（之后）→ 详见 [`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md)。

## 标书 BidAutoPipeline

全路径演示（项目清单 / 知识同步 / 赛道选题 / 材料工作台）：见 [`BID_PIPELINE.md`](./BID_PIPELINE.md)。

```bat
python scripts\seed_bid_demo.py
scripts\start_nl2sql_demo.bat
```

## 本地一键启动

```bat
scripts\start_local_demo.bat
```

脚本会：自动补齐缺失的 `config.yaml` / `users.json`（从 example 复制）、检测 API Key、打印评委账号与健康检查提示。

或：

```bat
cd content_factory
python web_server.py
```

- 看板：http://127.0.0.1:8090
- 健康检查：http://127.0.0.1:8090/api/health
- 登录：`admin` / `chengjun2026`
- 评委只读：`judge` / `judge2026`

### 模型 Key（primary / interim）

```powershell
# Path B：主办方发放后（正式 primary —— 息壤 / 星辰 TokenHub）
$env:XIRANG_API_KEY="你的Key"
$env:TOKENHUB_API_KEY="..."   # 可选

# Interim：等 Token 期间真实 E2E（可选）
$env:SENSENOVA_API_KEY="..."
$env:DASHSCOPE_API_KEY="..."
```

| 状态 | 预期 UI / 行为 |
|------|----------------|
| 已配置息壤/星辰 | 徽章显示 primary；可真实「发起成军」 |
| 仅 SenseNova/百炼 | 徽章显示 fallback；可真实 E2E（口播说明 interim） |
| 全部未配置 | 橙色 **无可用 LLM** 横幅；「发起成军」明确报错——**预期行为**，禁止静默 mock |

级联顺序见 `content_factory/config.yaml.example`。

## 天翼云公网（Path A · 试用可先上）

1. 按根目录 `DEPLOY天翼云.md` §3 开通 **免费试用** ECS（https://www.ctyun.cn/act/trial/central）并执行 `deploy_to_ctyun.sh`
2. 使用 `scripts/nginx_chengjuntai.conf` 反代 8090
3. 按 `docs/PROD_HARDENING.md` 开启 HTTPS 与密钥治理
4. 将公网 URL 写入 `docs/STORE_REGISTRATION.md`
5. **不必等 Token**：无 Key 也可先公网结构 Demo；Token 到手后按 `CTYUN_TRIAL.md` Path B 注入并重启

## 验收命令

```bash
python scripts/health_check.py
python tests/test_campaign_core.py
python scripts/run_demo_campaign.py
```

`health_check.py`：无 Key 时本地结构仍可通过（`ok=true`，`demo_ready=false`），并在 stderr 打印下一步提示（含试用部署与向主办方要 Token）。
