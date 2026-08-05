# 成军台 · P0 一周冲刺计划（冲 85+）


> **进度快照 (2026-07-30)**：真实标讯已刷新（real≥80）；成军台独立 GitHub 仓库已推送（见 README）；公网 Demo URL / Token / 视频仍待用户侧。ModelScope 非竞赛主路径，见 MODELSCOPE_INTERIM.md。

> 目标：预赛前具备 **公网 Demo +（有 Key 时）真实 E2E + 零讲解 60 秒路径 + 视频/PPT**。  
> 约束：星辰/息壤 Token **不能编造**；天翼云控制台 **仅用户可开**。Agent 侧做脚本/文档/UI；用户侧做控制台与录屏。  
> 总览替代关系：本文件为 **执行主表**；细节仍见 [`NEXT_SPRINT.md`](./NEXT_SPRINT.md)、[`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md)。  
> 账号口令：见本地 [`ADMIN_ACCESS.local.md`](./ADMIN_ACCESS.local.md)（已 gitignore，**勿提交、勿贴到公开文档**）。  
> **2026-07-30**：Token + ECS 试用标为 **用户审批中**；Agent **不阻塞**，继续本地加深（见 [`DEEPEN_LOG.md`](./DEEPEN_LOG.md)）。

---

## 冲分四件套（P0）

| # | 事项 | 阻塞 | 状态 | 本周验收 |
|---|------|------|------|----------|
| 1 | 星辰/息壤 Token 切为 primary | **用户内部审批中** | ⏳ 等用户 | 徽章显示息壤/星辰；`health_check` → `llm_providers=pass` |
| 2 | 天翼云试用公网 Demo + HTTPS + 改密 | **用户内部审批中** | ⏳ 等用户 | 公网 HTTPS 可登录；默认密码已改 |
| 3 | 3 分钟视频 + 12–15 页 PPT | 录屏/排版（文稿已加深） | 🟡 可本地录 | 成片可交；[`PPT_SPEAKER_DECK.md`](./PPT_SPEAKER_DECK.md) 可照念 |
| 4 | 「零讲解」评委 60 秒路径 | 无 | ✅ Agent 已收紧 | 首页大 CTA → 样例战役 → 产物/Word → 问数一表 |

用户个人待办精简版：[`USER_ONLY_TODO.md`](./USER_ONLY_TODO.md)。

**Agent 并行（不阻塞审批）**：P1/P2 本地加深已推进 —— 见 [`P1_P2_PROGRESS.md`](./P1_P2_PROGRESS.md)、[`DEEPEN_LOG.md`](./DEEPEN_LOG.md)。

---

## Day-by-day（D1–D7）

### D1 · 锁定叙事 + 申请 Token + 本地走通 60 秒

| 勾选 | 事项 | Owner | 链接 / 命令 |
|:----:|------|-------|-------------|
| [x] | 确认赛道一句话与 README / PPT / 视频一致 | Agent+用户 | `PROJECT_DOC.md`、[`ELEVATOR_PITCH.md`](./ELEVATOR_PITCH.md) |
| [ ] | **星辰/息壤 Token：用户审批中**（勿附隐私截图） | **用户** | [`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md) 「向主办方要 Token」 |
| [x] | 本地启动 + 评委 60 秒 CTA 走通（结构） | Agent | `scripts\start_local_demo.bat` → 「评委 60 秒体验」 |
| [ ] | `Ctrl+F5` 硬刷新后再截图/录屏 | **用户** | 避免旧 JS 缓存 |
| [ ] | （可选）Interim Key 做真实发起 | **用户** | env：`SENSENOVA_API_KEY` / `DASHSCOPE_API_KEY`；勿 commit |

**D1 验收**：judge 可零讲解走完样例战役 → Word → 问数样例表；Token **审批已发起**。

---

### D2 · Path A：天翼云试用上公网

| 勾选 | 事项 | Owner | 链接 / 命令 |
|:----:|------|-------|-------------|
| [ ] | **ECS 试用：用户审批中** → 开通后 Ubuntu 22.04 | **用户** | https://www.ctyun.cn/act/trial/central ；[`DEPLOY天翼云.md`](../DEPLOY天翼云.md) §3、[`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md) Path A |
| [ ] | 安全组放行 22 / 80 / 443 | **用户** | 控制台 |
| [ ] | 上传并执行 `deploy_to_ctyun.sh` | **用户** | `DEPLOY天翼云.md` |
| [ ] | 公网 URL 写入 Store 登记草稿 | **用户** | [`STORE_REGISTRATION.md`](./STORE_REGISTRATION.md) |
| [ ] | 确认评委账号可登录公网 | **用户** | 口令见 `ADMIN_ACCESS.local.md` |

**D2 验收**：公网能打开登录页；结构 Demo 可用（可无竞赛 Token）。**Agent 不等待本段。**

---

### D3 · 生产加固 + 材料开录

| 勾选 | 事项 | Owner | 链接 / 命令 |
|:----:|------|-------|-------------|
| [ ] | **公网改密**（admin/operator；勿把新密提交 Git） | **用户** | [`PROD_HARDENING.md`](./PROD_HARDENING.md) |
| [ ] | HTTPS（证书 / Nginx 443） | **用户** | `scripts/nginx_chengjuntai.conf`、`PROD_HARDENING.md` |
| [ ] | 按脚本录 3 分钟视频（有 Key 优先正式成片） | **用户** | [`DEMO_VIDEO_SCRIPT.md`](./DEMO_VIDEO_SCRIPT.md) |
| [x] | 演讲稿 / HTML deck / Elevator 已加深 | Agent | [`PPT_SPEAKER_DECK.md`](./PPT_SPEAKER_DECK.md) / [`.html`](./PPT_SPEAKER_DECK.html) / [`ELEVATOR_PITCH.md`](./ELEVATOR_PITCH.md) |

**生产卫生（必记）**

- [ ] 公网部署前改掉默认密码；评委只读账号可保留但勿用弱密做 admin
- [ ] **禁止** commit：`config.yaml`、含真实 Key 的 `.env`、`users.json`（若已改密）、`ADMIN_ACCESS.local.md`
- [ ] **禁止** PPT/视频出现证件、人脸、手机号、完整邮箱等 PII 截图
- [ ] 无 Key 时必须橙色横幅 + 明确报错，禁止静默 mock

---

### D4 · PPT 定稿 + 截图对齐徽章

| 勾选 | 事项 | Owner | 链接 / 命令 |
|:----:|------|-------|-------------|
| [ ] | 按 15 页演讲稿截真实 UI（Ctrl+F5 后） | **用户** | `PPT_SPEAKER_DECK.md` 第 4–10 页 |
| [ ] | 徽章文案与口播一致（息壤/星辰或 interim 过渡说明） | **用户** | 双轨：[`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md) Path B |
| [ ] | 可选：浏览器打开 HTML deck 投影答辩 | 用户 | `docs/PPT_SPEAKER_DECK.html` |
| [x] | Agent：五维对位 + 电信/政企叙事写入稿 | Agent | 本仓库 docs |

**D4 验收**：PPT 可独立答辩，不依赖临场改稿。

---

### D5 · 提交口字段 + 自检

| 勾选 | 事项 | Owner | 链接 / 命令 |
|:----:|------|-------|-------------|
| [ ] | Demo URL / 仓库 / 赛道勾选写入登记表 | **用户** | [`STORE_REGISTRATION.md`](./STORE_REGISTRATION.md)、[`REGISTRATION_FILL.md`](./REGISTRATION_FILL.md) |
| [ ] | 走完 [`CHECKLIST.md`](./CHECKLIST.md) | 共同 | 勾选本周交付项 |
| [ ] | `python scripts/health_check.py` | Agent/用户 | 结构项 pass；有 Key 时 `demo_ready` |
| [ ] | （可选）`python scripts/smoke_e2e.py` | Agent | 登录 / 战役 / judge ACL |

---

### D6 · Token 到手日（可穿插任意日）· Path B 切换

> 无 Token 则跳过本段，继续用 interim 或结构 Demo。**当前：用户审批中。**

| 勾选 | 事项 | Owner | 验收 |
|:----:|------|-------|------|
| [ ] | 在**服务器/本机**注入 `XIRANG_API_KEY`（可选 `TOKENHUB_API_KEY`） | **用户** | 仅 env / 本地 config；**不 commit** |
| [ ] | 重启 Web / systemd | **用户** | 进程读到新 env |
| [ ] | `python scripts/health_check.py` | 用户/Agent | `llm_providers=pass`；primary 为息壤/星辰 |
| [ ] | UI 徽章与 PPT/视频口播一致 | **用户** | Ctrl+F5 后核对 |
| [ ] | 重录关键 20 秒徽章镜头（若成片已出） | **用户** | `DEMO_VIDEO_SCRIPT.md` |

切换步骤全文：[`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md) Path B。

**UI 切换核对清单（Token 到手当日）**

- [ ] 登录页横幅不再写「仅过渡模型」（若 primary 已启）
- [ ] 顶栏徽章：息壤/星辰名称 + model
- [ ] 发起一场短战役或打开样例，周报/战役 `llm_provider` 字段可信
- [ ] 无 Key 回退场景仍显式失败（关掉 Key 抽测一次）

---

### D7 · 评委路径预演 + 备份

| 勾选 | 事项 | Owner | 链接 / 命令 |
|:----:|------|-------|-------------|
| [ ] | 公网用 **judge** 走「评委 60 秒体验」≤60s | **用户** | 首页大 CTA；样例 `CMP_DEMO_WEEK_LEAD` |
| [ ] | 备份战役与库 | 用户/Agent | `scripts/backup_campaigns.sh` 或等价打包 |
| [ ] | 真实标讯/问数（若答辩要秀） | 用户 | [`REAL_DATA.md`](./REAL_DATA.md)、`scripts\start_real_data.bat` |
| [ ] | 最终材料打包：视频链接、PPT、Demo URL、仓库 | **用户** | `CHECKLIST.md` |

**D7 验收**：陌生人（模拟评委）不听讲解也能点出 Word + 一张问数表。

---

## 评委 60 秒路径（产品侧 · 零讲解）

1. 打开 Demo → 点 **「评委 60 秒体验」**（登录页或登录后首页）  
2. 自动登录 judge（只读）并打开最佳样例战役（优先 `CMP_DEMO_WEEK_LEAD`）  
3. 产物抽屉可见 → 一键 **导出 Word**  
4. 跳转 **智能问数**：在线则跑预设卡；离线则展示 **标注清楚的缓存样例表**（禁止假装实时）  

录屏点击清单与旁白对齐：[`DEMO_VIDEO_SCRIPT.md`](./DEMO_VIDEO_SCRIPT.md)。

---

## 文档地图

| 文档 | 用途 |
|------|------|
| [`USER_ONLY_TODO.md`](./USER_ONLY_TODO.md) | 仅冯亦根必须亲自动手的事项 |
| [`P1_P2_PROGRESS.md`](./P1_P2_PROGRESS.md) | P1/P2 交付勾选与验证 |
| [`DEEPEN_LOG.md`](./DEEPEN_LOG.md) | Agent 本地加深变更日志 |
| [`ELEVATOR_PITCH.md`](./ELEVATOR_PITCH.md) | 30s / 60s / 3min 口播 |
| [`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md) | 天翼云试用 ∥ 星辰 Token 双路径 |
| [`PROD_HARDENING.md`](./PROD_HARDENING.md) | HTTPS / 改密 / 关 mock |
| [`REAL_DATA.md`](./REAL_DATA.md) | 真实标讯 + 问数库 |
| [`PPT_SPEAKER_DECK.md`](./PPT_SPEAKER_DECK.md) | 15 页演讲稿（含五维对位） |
| [`DEMO_VIDEO_SCRIPT.md`](./DEMO_VIDEO_SCRIPT.md) | 3 分钟 + 60 秒点击表 |
| [`CHECKLIST.md`](./CHECKLIST.md) | 提交前自检 |
| [`ADMIN_ACCESS.local.md`](./ADMIN_ACCESS.local.md) | 本地口令（勿提交） |

---

## Agent vs 用户（边界）

| Agent 可做 | 用户必须做 |
|------------|------------|
| 文档、脚本、UI 60 秒路径、本地冒烟 | 申请主办方 Token（**审批中**） |
| PPT/视频文案与 HTML deck | 天翼云试用开通与安全组（**审批中**） |
| 部署脚本与加固清单 | 公网改密、HTTPS 证书 |
| 结构回归 / smoke / 产品加深 | 录视频、终审 PPT、赛事后台提交 |
| — | 任何含真实 Key/密码的注入（Agent 不代填、不打印） |
