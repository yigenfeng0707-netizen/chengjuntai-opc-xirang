# 仅你（冯亦根）必须做的事

> Agent 已准备文档 / UI / 脚本，并在 **不等待 Token/ECS** 的前提下继续本地加深。  
> 下列事项 **无法代劳**（控制台、主办方、录屏、改密）。  
> 总计划：[`P0_WEEK_PLAN.md`](./P0_WEEK_PLAN.md)。口令只查本地 `ADMIN_ACCESS.local.md`（勿外传、勿 commit）。  
> 加深日志：[`DEEPEN_LOG.md`](./DEEPEN_LOG.md)。

---

## Agent 已完成（本机可核验）

| 事项 | 状态 | 说明 |
|------|------|------|
| 真实标讯刷新 | **已完成** | `python scripts/refresh_real_bids.py --timeout 900` → real≈382 / demo≈12 / rows≈394（以 `db_stats()` 为准） |
| GitHub 成军台仓库 | **已创建并推送** | 见 README 顶部仓库链接；旧底座 `nl2sql-teleagent` 保留为 legacy |
| Demo 公网 URL | **待你** | 依赖天翼云 ECS；本地 Demo 仍为 `http://127.0.0.1:8090` |
| 星辰/息壤 Token | **待你审批** | Agent 不编造 Key |
| ModelScope | **非主路径** | 见 [MODELSCOPE_INTERIM.md](./MODELSCOPE_INTERIM.md)；Store 等天翼云 |

---

## 状态：用户审批中（Agent 不阻塞）

| 事项 | 状态 | 说明 |
|------|------|------|
| 星辰 / 息壤 Token | **用户内部审批中** | 到手后按 Path B 注入；此前可用 interim 或结构 Demo |
| 天翼云试用 ECS | **用户内部审批中** | 开通后按 Path A 部署公网；本地 :8090 可继续演示 |

Agent **不会**编造 API Key，**不会**假装已有公网 IP。

---

## 今天优先（按顺序）

1. **推进星辰 / 息壤 Token 内部审批**（若尚未发出申请）  
   - 按 [`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md) 话术联系主办方 / 内部流程  
   - 不要发证件、人脸、完整账单或含隐私的控制台截图  

2. **推进天翼云试用 ECS 内部审批**（可与 Token 并行）  
   - https://www.ctyun.cn/act/trial/central  
   - 步骤：[`DEPLOY天翼云.md`](../DEPLOY天翼云.md) + [`CTYUN_TRIAL.md`](./CTYUN_TRIAL.md)  
   - 安全组放行 22 / 80 / 443 → 跑部署脚本 → 把公网 URL 写入 [`STORE_REGISTRATION.md`](./STORE_REGISTRATION.md)  

3. **公网上线前改默认密码**（有公网后立刻做）  
   - 见 [`PROD_HARDENING.md`](./PROD_HARDENING.md)  
   - 新密码只写在本机 `ADMIN_ACCESS.local.md` 或密码管理器，**禁止提交 Git**  

4. **录 3 分钟 Demo 视频**（本地亦可先录结构成片）  
   - 点击表：[`DEMO_VIDEO_SCRIPT.md`](./DEMO_VIDEO_SCRIPT.md)（已与 60s CTA 逐钮对齐）  
   - 录前浏览器 **Ctrl+F5**；优先真实 Key；无竞赛 Token 时可用 interim 并口播说明  

---

## Token 到手当天（Path B）

1. 在服务器 / 本机注入 `XIRANG_API_KEY`（可选 `TOKENHUB_API_KEY`）——仅环境变量或 gitignore 的配置  
2. 重启服务 → `python scripts/health_check.py`  
3. Ctrl+F5 确认顶栏徽章为息壤/星辰  
4. 若视频已出，补录徽章相关镜头  

详细清单：[`P0_WEEK_PLAN.md`](./P0_WEEK_PLAN.md) D6。

---

## 本周内补齐

- [ ] HTTPS（443）——依赖 ECS 审批通过  
- [ ] 按 [`PPT_SPEAKER_DECK.md`](./PPT_SPEAKER_DECK.md) 截真实图并定稿（可用 [`PPT_SPEAKER_DECK.html`](./PPT_SPEAKER_DECK.html) 投影；含五维对位）  
- [ ] 赛事后台 / Store 提交：Demo URL、仓库、赛道勾选  
- [ ] 公网用 judge 走一遍「评委 60 秒体验」≤ 60 秒  

可先本地练口播：[`ELEVATOR_PITCH.md`](./ELEVATOR_PITCH.md)。

---

## 明确不要做

- 不要把 API Key、生产密码、改密后的 `users.json` 提交到仓库  
- 不要在 PPT/视频里放 PII 截图  
- 不要等 Token 才开天翼云——Path A 与 Token **并行审批**即可  
- 不要等公网才练 60 秒——本地 `http://127.0.0.1:8090` 已可走通  
