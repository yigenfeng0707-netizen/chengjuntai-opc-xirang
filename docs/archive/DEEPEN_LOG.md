# 成军台 · 本地加深日志（DEEPEN_LOG）

> 日期：2026-07-30  
> 约束：不编造息壤/星辰 Key；不等待 ECS/公网；不 commit；不打印 secrets / 不索要 PII。  
> 并行：用户内部审批 **星辰 Token + 天翼云 ECS 试用**；Agent 继续本地深化。

---

## 本轮加深摘要（P1 + P2）

进度表：[`P1_P2_PROGRESS.md`](./P1_P2_PROGRESS.md)

### P1 · 可演示性

1. **叙事默认「缺编辑部的一人公司」**  
   - 登录页 / 首页 OPC claim / value-strip / 内容工厂横幅对齐同一闭环  
   - 非评委（admin/operator）首页：去掉大块 metrics 卡片，改为 story-rail + 链到成效/标书，减后台仪表盘感

2. **标讯 → 一键成军丝滑路径**  
   - `bidStartCamp`：toast → 自动 `nav('home')` + `openCamp` → 粘性引导条（人审 / 产物 / Word）  
   - `REAL_*` 项目名/ID 写入战役目标（既有 `theme_to_campaign`）

3. **本周故事**  
   - `metrics_snapshot` 注入 `bid_real_count` / `bid_demo_count` / `bid_row_count` / `demo_campaign_count`  
   - 文案绑定演示周包 + 真实/演示标讯计数

4. **生产卫生（本地可做）**  
   - **密码**：新注册 / add_user / change_password → werkzeug 哈希；旧明文演示账号登录成功后惰性升级  
   - [`PROD_HARDENING.md`](./PROD_HARDENING.md)：勾选 gitignore 审计、哈希策略、公网默认密码横幅  
   - `.gitignore`：补 `export_docx/`、`bid_workspace/`、`schedule_config.json`  
   - 公网旗标：`CHENGJUNTAI_PUBLIC=1` 或 `public_deploy: true` → 登录页强提醒改密（不打印口令）

### P2 · 已推进

5. **调度器**：`scheduler.start_background()` 内嵌守护线程；`/api/schedule/start|stop|status`；UI「启动调度器」；仍可用 `start_scheduler.bat`  
6. **标书 Word 材料包**：封面 + Checklist + 证据矩阵 + 缺口建议（非法律排版）  
7. **多用户**：`created_by` 过滤不变；公开用户 API 不带 password；超管洞察继续读 usage

### 更早一轮（保留）

- 评委 60s CTA、答辩材料、标讯桥接初版、本周故事初版

---

## 本地如何验证

```bat
cd D:\APPs\天翼息壤杯\chengjuntai
python scripts\seed_demo_week.py
scripts\start_local_demo.bat
```

1. **Ctrl+F5** → http://127.0.0.1:8090  
2. 评委 60 秒 → Word → 问数  
3. **旧账号**：admin / judge 登录（若曾为明文，登录后自动哈希）  
4. **新注册**：邮箱注册 → `users.json` 中 password 以 `pbkdf2:` / `scrypt:` 开头  
5. 标书工作台 → 一键获客 → toast + 自动打开看板  
6. 成效指标 → 「本周故事」含标讯条数  
7. 内容工厂 → 定时任务 → 启动调度器（状态变运行中）  
8. 可选：`python scripts/smoke_auth.py` / `health_check.py`

---

## 仍等待用户审批

| 项 | 说明 |
|----|------|
| 星辰 / 息壤 Token | 到手后注入 env，切 primary 徽章 |
| 天翼云 ECS 试用 | 开通后部署公网 + HTTPS + 改密；设 `CHENGJUNTAI_PUBLIC=1` |

---

## 未做 / 明确延后

- 真实公网 IP / 正式竞赛 Token（不可发明）  
- Git commit（按用户要求不提交）  
- 系统级 Windows 任务计划程序 / 正式 cron  
- 标书 Word 法律级排版
