# 成军台 · 产品升级说明（息壤杯反馈响应）

> 日期：2026-07-29 · 范围：可演示性加固 → **全量升级见 [FULL_UPLIFT.md](./FULL_UPLIFT.md)**

## 1) 生成内容去哪看？

| 入口 | 怎么点 |
|------|--------|
| **成军看板** | 打开战役 → 高亮「产物抽屉」→ **打开产物 / 预览**（自动预览最新一件） |
| **内容工厂** | 多 Tab：选题池 / 稿件台 / 流水线 / 向量 / 定时 / 队列 / 标书同步 |
| **产物中心** | 汇总战役产物 + 内容工厂文章，统一打开/导出 |

修复：内容官产物路径（`campaign/runner` 误拼 `campaign/articles`）已改为 `ARTICLES_DIR`；产物读取兼容相对路径。

## 2) Markdown → 富文本 Word

- 依赖：`python-docx`（见根目录 `requirements.txt`）
- 模块：`content_factory/docx_exporter.py`（标题 / 粗体 / 列表）
- API：
  - `POST /api/campaign/{id}/report_docx` + `GET .../report_docx/file`
  - `POST /api/campaign/{id}/artifact/{aid}/docx`
  - `GET|POST /api/article/{id}/docx`
- UI：战役看板主按钮 **导出 Word**；PDF/MD 降为次要「导出周报(MD/PDF)」

## 3) 智能问数看板 · 真查库

- 修复数据参谋 MCP 协议：`type=call_tool` + `question`（原 JSON-RPC/`query` 无效）
- 直连 znws `:8082` 兜底；空库自动 `seed_demo_db.py`
- 侧栏 **智能问数**：5 预设问题卡 + 表格 + CSS 柱状图；离线横幅 +「写入演示库」
- 脚本：`scripts/start_nl2sql_demo.bat`（种子库 + 8082 + 8765）
- `start_local_demo.bat` 启动时幂等写入样例战役

## 4) 演示叙事更锋利

- 首页价值条：**缺编辑部的一人公司 → 完整内容生产闭环**
- `lead_gen` / `industry_brief` 提示词强化（跟进表 10 行、渠道计划、综述三段）
- `scripts/seed_demo_campaigns.py`：3 个已完成样例战役快照
- **`scripts/seed_demo_week.py`**：一周故事包（选题+稿件+LEAD/BRIEF 战役）
- `docs/PROJECT_DOC.md` / 本文件 / **FULL_UPLIFT.md**

## 评委 60 秒路径

1. 登录页或首页点 **「评委 60 秒体验」**（自动 judge 登录）  
2. 打开样例战役（优先 `CMP_DEMO_WEEK_LEAD`）→ 产物抽屉预览  
3. 引导条 **导出 Word**  
4. **智能问数**：在线跑预设卡；离线展示标注清楚的缓存样例表  

详见 `docs/P0_WEEK_PLAN.md` · `docs/DEMO_VIDEO_SCRIPT.md`。
