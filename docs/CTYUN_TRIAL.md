# 天翼云试用 + 星辰 Token 双路径

> 适用：已可开 **天翼云 ECS 免费试用**，但 **星辰 TokenHub / 息壤 API Key 尚在等主办方发放**。  
> 详细 ECS 点击步骤见根目录 [`DEPLOY天翼云.md`](../DEPLOY天翼云.md) 第 3–6 章。

---

## 两条并行路径

| 路径 | 何时做 | 目标 | Key 策略 |
|------|--------|------|----------|
| **A · 天翼云试用部署公网 Demo** | **现在** | 公网 URL、登录页、看板结构、评委账号可访问 | 可先无息壤 Key；有 SenseNova/百炼则开真实 E2E，否则显式「无 Key」横幅 |
| **B · 切 primary LLM 为息壤/星辰** | 主办方发 Token 后 | 模型徽章显示息壤/星辰；预赛正式演示 | 注入 `XIRANG_API_KEY` / `TOKENHUB_API_KEY`，重启服务 |

两条路径互不阻塞：先上公网（A），再换主模型（B）。  
一周勾选执行表：[`P0_WEEK_PLAN.md`](./P0_WEEK_PLAN.md) · 用户亲办：[`USER_ONLY_TODO.md`](./USER_ONLY_TODO.md)。

---

## Path A：本周立刻做（试用 ECS）

控制台入口与点击顺序（摘自 `DEPLOY天翼云.md`）：

1. 打开试用中心：https://www.ctyun.cn/act/trial/central  
2. 选择「云主机 ECS」免费试用  
3. 规格建议：4 核 8G / 系统盘 60G / 带宽 3M / **Ubuntu 22.04**  
4. 设置并**自行保管** root 密码（勿发到群、勿提交仓库）  
5. 控制台 → 云主机 → **安全组**：入站放行 TCP **22**（建议限源 IP）、**80**、**443**  
6. 本机打包上传项目后，在 ECS 执行：`sudo bash deploy_to_ctyun.sh`  
7. 将公网 URL 写入 `docs/STORE_REGISTRATION.md` 的「Demo 地址」

生产加固（改密 / HTTPS）见 `docs/PROD_HARDENING.md`。

---

## Path B：等主办方 Token 后（切主链路）

1. 收到星辰 TokenHub / 息壤 Key 后，**仅**写入环境变量或服务器上的 `config.yaml`（勿 commit）  
2. PowerShell 本地示例：

```powershell
$env:XIRANG_API_KEY="主办方发放的Key"
# 若单独发放 TokenHub：
$env:TOKENHUB_API_KEY="..."
```

3. 重启 Web / systemd 服务，跑 `python scripts/health_check.py`  
4. 验收：`llm_providers=pass`，看板徽章为息壤/星辰（非仅 SenseNova/百炼）

主链路 endpoint 以 `config.yaml.example` 中 `primary-天翼云息壤-星辰TokenHub` 为准；若主办方给了不同 `api_base` / `model`，只改本地/服务器配置，不改 example 里的占位语义。

---

## Interim：等 Token 期间的 LLM

| 情况 | 做法 |
|------|------|
| 已有 **SenseNova** 或 **百炼** Key | 设 `SENSENOVA_API_KEY` / `DASHSCOPE_API_KEY`，走 fallback 做真实 E2E；徽章会显示对应 fallback 名 |
| **都没有** | 保持结构 Demo：看板可浏览 + 橙色 **无可用 LLM** 横幅；「发起成军」明确报错（禁止静默 mock） |
| 主办方 Token 到手 | 优先注入息壤/星辰，fallback 可保留作灾备 |

级联顺序（见 `config.yaml.example`）：**息壤/星辰 primary → TokenHub secondary → SenseNova → 百炼**。

---

## 向主办方要 Token 时说什么（勿附截图/隐私）

建议私信/邮件只写业务必要信息：

- 队伍/作品名：**成军台（OPC OS on 息壤）**  
- 赛道：惠民产品创新 / AI+自选开放场景  
- 用途：预赛公网 Demo 的 **primary LLM**（星辰 TokenHub / 息壤 OpenAI 兼容网关）  
- 需要：`API Key`、推荐 `api_base`、可用 `model` 名称、额度/有效期  
- 已具备：天翼云试用 ECS 公网部署能力，拿到 Key 即可切换主链路  

**不要**发送：身份证、人脸、银行卡、完整账单截图、含隐私的控制台全屏图、真实密码。

---

## 切勿提交到 Git

- `content_factory/config.yaml`（含真实 Key / 生产密码）  
- `content_factory/users.json`（若已改密）  
- 任何 `.env`、密钥文件、试用开通截图里的账号敏感信息  
- 服务器 root 密码、SSH 私钥  

仓库只保留 `*.example` 与文档中的占位符。
