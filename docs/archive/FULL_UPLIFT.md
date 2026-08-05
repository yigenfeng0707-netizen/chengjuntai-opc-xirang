# 成军台 · 全量升级说明（FULL UPLIFT）

> 日期：2026-07-29 · 范围：内容工厂 UI 恢复 + 战役桥接 + 一周演示包 + 中档打磨

## 1) 内容工厂工作台（侧栏「内容工厂」）

多 Tab 工作区（不再是单按钮快测）：

| Tab | 能力 |
|-----|------|
| **选题池** | 采集、列表、分数、选用/废弃、从选题生成稿 |
| **稿件台** | 列表、预览、质检、导出 Word、关联到战役 |
| **流水线** | 一键全链路（选题→生成→质检→向量） |
| **向量检索** | search UI |
| **定时任务** | list + toggle |
| **任务队列** | load + pending |
| **标书/知识同步** | 同步/拉选题；路径缺失时展示降级说明，按钮仍可点 |

评委路径：登录 → **内容工厂** → 选题池「采集」→ 稿件台预览 / 导出 Word → 流水线可选一键。

## 2) 战役 ↔ 内容工厂

- 内容角色执行：`generate_article` + `quality_gate`，产物 meta 挂 `factory_article_id`
- 战役按钮：**同步到内容工厂**
- 稿件台：**关联到战役**（下拉选战役）
- 周报 MD/Word：含「内容工厂关联稿件」章节

## 3) 一周演示包

```bash
python scripts/seed_demo_week.py
```

| 类型 | ID |
|------|-----|
| 选题 | `demo_tp_01` … `demo_tp_05` |
| 工厂稿 | `ART_DEMO_WEEK_01` / `02` / `03` |
| 获客战役 | **`CMP_DEMO_WEEK_LEAD`**（lead_gen，富跟进表+渠道计划） |
| 综述战役 | **`CMP_DEMO_WEEK_BRIEF`**（industry_brief） |

评委：登录 judge → 战役列表打开上述 ID → 产物抽屉 / 导出 Word → 内容工厂看关联稿。

## 4) 中档打磨

- 智能问数：5 张预设问题卡 + 表格旁 CSS 柱状图
- 成效指标：按模板拆分 lead_gen / industry_brief
- 首页价值条：强调「缺编辑部的一人公司 → 完整内容生产闭环」
- 人审意见：approve 前可填，看板展示 `gate.note`
- lead_gen：渠道预览清单

## 5) 剩余缺口

- 定时任务 UI 仅配置开关，不在本机跑 cron 守护（需 scheduler 进程）
- 标书路径多数环境走本地 knowledge / NL2SQL 降级
- 全链路 PDF 依赖 reportlab；Word 为主交付
- 智能问数需 `scripts/start_nl2sql_demo.bat`（:8082+:8765）才算「真在线」

## 相关文件

- `content_factory/templates/index.html` — 工厂多 Tab / 问数卡 / 人审意见
- `content_factory/campaign/runner.py` — 内容角色 + sync + 周报关联
- `content_factory/agents.py` — `campaign_id` / `link_article_campaign`
- `content_factory/web_server.py` — bridge APIs / `full_pipeline` / `bid/status`
- `scripts/seed_demo_week.py`
