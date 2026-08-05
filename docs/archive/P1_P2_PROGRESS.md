# 成军台 · P1 / P2 进度（2026-07-30）

> Token / ECS **用户审批中**；本轮不编造 Key、不部署 ECS、不 commit。  
> 详情 changelog：[`DEEPEN_LOG.md`](./DEEPEN_LOG.md) · 执行主表：[`P0_WEEK_PLAN.md`](./P0_WEEK_PLAN.md)

---

## P1 — 可演示性（已交付）

| # | 事项 | 状态 | 验证要点 |
|---|------|------|----------|
| 5 | 内容工厂 × 战役叙事「缺编辑部的一人公司」；非评委首页减仪表盘感 | ✅ | 首页 claim / value-strip / story-rail；内容工厂横幅 |
| 6 | 标讯→一键成军丝滑路径 | ✅ | 标书工作台点「一键获客」→ toast → 自动打开看板 + 引导条 |
| 7 | 「本周故事」绑定演示周包 + 真实/演示标讯计数 | ✅ | `/api/metrics` 含 `week_story`、`bid_real_count`；成效页卡片 |
| 8 | 新注册密码哈希；旧账号兼容；PROD_HARDENING / gitignore | ✅ | 注册新用户后 `users.json` 为 `pbkdf2:`/`scrypt:`；旧 judge/admin 仍可登录并惰性升级 |

## P2 — 可推进项（已交付子集）

| # | 事项 | 状态 | 验证要点 |
|---|------|------|----------|
| 9 | 轻量调度器：内嵌线程 + bat + UI 状态 | ✅ | 内容工厂→定时任务→「启动调度器」；或 `start_scheduler.bat` |
| 10 | 标书材料包 Word（封面+清单+矩阵） | ✅ | 拆解→矩阵→「导出材料包 Word」 |
| 11 | 用户作用域战役 + 超管洞察（哈希后） | ✅ | 普通 user 仅见自己的战役；admin 洞察仍可用 |

## 仍开放（等用户）

- 星辰/息壤 Token → primary 徽章
- 天翼云 ECS 公网 + HTTPS + 改密（设 `CHENGJUNTAI_PUBLIC=1`）
- 正式录屏 / PPT 截图（Ctrl+F5 后）

## 快速验证

```bat
cd D:\APPs\天翼息壤杯\chengjuntai
python scripts\smoke_auth.py
python scripts\health_check.py
```

浏览器 http://127.0.0.1:8090 → **Ctrl+F5**：judge 60s · admin 标讯一键成军 · 成效「本周故事」· 注册新邮箱登录。
