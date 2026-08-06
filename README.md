# 成军台 · OPC OS on 息壤

> 息壤育智 · 一人成军  
> 2026「息壤杯」全国人工智能 OPC 创新大赛 · **惠民产品创新 / AI+自选开放场景**

你只说目标，成军台在息壤上拉起 **调研官 / 内容官 / 数据参谋 / 运营官 / 复盘官**，自动拆解任务、协同推进、导出成军周报。

**GitHub（成军台主仓库）**：https://github.com/yigenfeng0707-netizen/chengjuntai-opc-xirang  

工程底座演进自 [nl2sql-teleagent](https://github.com/yigenfeng0707-netizen/nl2sql-teleagent)（legacy remote；NL2SQL TeleAgent + AI 内容工厂 + 天翼云部署）。本仓为息壤杯 OPC 成军台交付主线，不以旧仓为参赛主故事。

---

## 评委 60 秒路径（零讲解）

1. 启动 Web：`scripts\start_local_demo.bat`（或 `python content_factory/web_server.py`）
2. 打开 http://127.0.0.1:8090 → 点 **「评委 60 秒体验」**（或登录后首页同名大按钮）  
   - 只读评委账号：`judge`（口令当面提供，详见本地 `docs/ADMIN_ACCESS.local.md`，勿提交）
   - 演示写操作账号：`admin`（口令当面提供）
3. 自动打开最佳样例战役（优先 `CMP_DEMO_WEEK_LEAD`）→ **产物抽屉**
4. **导出 Word** 成军周报
5. **智能问数**一张表（离线时显示标注清楚的缓存样例，不假装实时）

> 正式演示：`XIRANG_API_KEY` / `TOKENHUB_API_KEY`（主办方星辰/息壤）。等 Token 期间可用 SenseNova/百炼 interim；全无 Key 时看板显式横幅并**明确报错**，禁止静默 mock。  
> 公众号草稿：本机配置 `WECHAT_APP_ID`/`WECHAT_APP_SECRET`（或 `config.wechat.local.yaml`，勿贴密钥到聊天）→ 稿件台「推送到公众号草稿」。见 [docs/WECHAT_PUBLISH.md](./docs/WECHAT_PUBLISH.md)。  
> 报名状态：**已报名**。**P0 一周执行表** [docs/P0_WEEK_PLAN.md](./docs/P0_WEEK_PLAN.md)；用户亲办 [docs/USER_ONLY_TODO.md](./docs/USER_ONLY_TODO.md)；双路径 [docs/CTYUN_TRIAL.md](./docs/CTYUN_TRIAL.md)。

---

## 快速开始

```bash
cd content_factory
# Windows
copy config.yaml.example config.yaml
copy users.json.example users.json
# 注入密钥（PowerShell）
$env:XIRANG_API_KEY="你的息壤或星辰Key"

pip install -r requirements
python web_server.py
```

健康检查：

```bash
python scripts/health_check.py
```

无 Key 状态机回归（仅 CI/结构验证，会显式开启 mock）：

```bash
python tests/test_campaign_core.py
python scripts/run_demo_campaign.py
```

---

## 架构要点

- **司令 Agent** `commander.py`：目标 → 任务树 + 人审卡点
- **战役状态机** `campaign/`：planned → running → awaiting_review → completed
- **LLM** `llm_client.py`：息壤/星辰主链路 + SenseNova/百炼级联；占位 Key 视为未配置
- **数据参谋**：联动 NL2SQL MCP；离线时显式标注非真实库查询
- **MCP（已封装，评委 60s 不强制走）**：见下节

---

## MCP 工具（Cursor / TeleAgent 挂载）

成军台有 **两套 stdio MCP**（与 Web 同源战役能力），外加可选的 **NL2SQL HTTP MCP**（智能问数）：

| 服务 | 文件 | 用途 |
|------|------|------|
| `chengjuntai-campaign` | `content_factory/mcp_campaign_server.py` | 战役：`start_campaign` / `list_campaigns` / `list_tasks` / `approve_gate` / `export_report` |
| `content-factory` | `content_factory/mcp_server.py` | 内容工厂工具：选题/成稿/质检/公众号草稿/回流/向量/PDF/队列等 |
| NL2SQL（可选） | `mcp_http_nl2sql_v3.py` | HTTP `:8765`，智能问数；`scripts\start_nl2sql_demo.bat` |

**挂载**：仓库根 [`mcp.json`](./mcp.json)（Cursor MCP 宿主 / TeleAgent）。`content_factory/mcp.json` 为同目录 cwd 副本。

**冒烟（无需 Key）**：

```bash
python scripts/smoke_mcp.py
```

看板顶栏徽章 **「MCP 工具已就绪」** 表示封装文件在位；评委主路径仍是 Web「评委 60 秒体验」，MCP 是同能力的 Agent 入口。

---

## 部署

- 试用公网（现在就能做）：[docs/CTYUN_TRIAL.md](./docs/CTYUN_TRIAL.md) + [DEPLOY天翼云.md](./DEPLOY天翼云.md)
- 加固：[docs/PROD_HARDENING.md](./docs/PROD_HARDENING.md)

---

## 参赛材料

- [docs/P0_WEEK_PLAN.md](./docs/P0_WEEK_PLAN.md) **P0 一周执行主表（冲 85+）**
- [docs/USER_ONLY_TODO.md](./docs/USER_ONLY_TODO.md) 仅用户必须做的事
- [docs/CTYUN_TRIAL.md](./docs/CTYUN_TRIAL.md) 天翼云试用 + 星辰 Token 双路径
- [docs/NEXT_SPRINT.md](./docs/NEXT_SPRINT.md) 报名后一周冲刺摘要
- [docs/PROJECT_DOC.md](./docs/PROJECT_DOC.md) 项目文档 / BP
- [docs/PPT_SPEAKER_DECK.md](./docs/PPT_SPEAKER_DECK.md) 15 页演讲稿 · [HTML deck](./docs/PPT_SPEAKER_DECK.html)
- [docs/PPT_OUTLINE.md](./docs/PPT_OUTLINE.md) 答辩大纲
- [docs/DEMO_VIDEO_SCRIPT.md](./docs/DEMO_VIDEO_SCRIPT.md) 3 分钟 + 60 秒点击表
- [docs/LOCAL_DEMO.md](./docs/LOCAL_DEMO.md) 本地与公网 Demo
- [docs/STORE_REGISTRATION.md](./docs/STORE_REGISTRATION.md) 智云 Store / 提交口字段
- [docs/CHECKLIST.md](./docs/CHECKLIST.md) 预赛自检

---

## 许可证与声明

- 衍生自 nl2sql-teleagent 参赛演进版
- 演示数据与 mock 内容仅供结构验证；对外正式演示须使用真实息壤/星辰模型调用
