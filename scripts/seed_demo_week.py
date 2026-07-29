# -*- coding: utf-8 -*-
"""
一周演示数据包（评委可浏览）：选题池 + 工厂稿件 + 1 个 lead_gen 完成战役 + 1 个 industry_brief。
幂等：同 ID 已存在则跳过对应段。可叠加 scripts/seed_demo_campaigns.py 旧样例。
"""
import os
import sys
import json
import datetime
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "content_factory")
sys.path.insert(0, CF)

from campaign import store  # noqa: E402
from config_loader import DATA_DIR, ARTICLES_DIR  # noqa: E402

TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")
ARTICLES_META = os.path.join(DATA_DIR, "articles_meta.json")


def _now(offset_days=0, hour=10):
    base = datetime.datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
    return (base - datetime.timedelta(days=offset_days)).isoformat(timespec="seconds")


WEEK_TOPICS = [
    {
        "id": "demo_tp_01",
        "title": "一人成军：缺编辑部也能跑通选题到周报",
        "summary": "一人公司用 AI 员工矩阵补齐调研/内容/问数/运营，交付可验收 Word。",
        "source": "demo-week",
        "scores": {"受众价值": 9, "实操落地性": 9, "竞品稀缺度": 8, "流量潜力": 9, "市场热度": 7},
        "total_score": 42.0,
        "status": "selected",
        "created_at": _now(6),
    },
    {
        "id": "demo_tp_02",
        "title": "NL2SQL 智能问数在政企投标场景的量化收益",
        "summary": "自然语言查中标库，把「问数参谋」嵌进获客战役。",
        "source": "demo-week",
        "scores": {"受众价值": 8, "实操落地性": 8, "竞品稀缺度": 9, "流量潜力": 8, "市场热度": 8},
        "total_score": 41.0,
        "status": "selected",
        "created_at": _now(5),
    },
    {
        "id": "demo_tp_03",
        "title": "MCP 协议实战：把工具链挂进内容工厂",
        "summary": "标准化工具调用降低 Agent 集成成本，适合知识库与标书联动。",
        "source": "demo-week",
        "scores": {"受众价值": 8, "实操落地性": 7, "竞品稀缺度": 9, "流量潜力": 7, "市场热度": 6},
        "total_score": 37.0,
        "status": "candidate",
        "created_at": _now(4),
    },
    {
        "id": "demo_tp_04",
        "title": "渠道投放计划模板：公域种草 + 社群跟进",
        "summary": "10 人跟进表 + 渠道验收标准，专为 lead_gen 战役设计。",
        "source": "demo-week",
        "scores": {"受众价值": 9, "实操落地性": 9, "竞品稀缺度": 7, "流量潜力": 8, "市场热度": 7},
        "total_score": 40.0,
        "status": "selected",
        "created_at": _now(3),
    },
    {
        "id": "demo_tp_05",
        "title": "息壤+一人公司行业综述：机会点与风险",
        "summary": "机会/风险/知识库要点三段，可入库复用。",
        "source": "demo-week",
        "scores": {"受众价值": 8, "实操落地性": 7, "竞品稀缺度": 8, "流量潜力": 8, "市场热度": 7},
        "total_score": 38.0,
        "status": "candidate",
        "created_at": _now(2),
    },
]

WEEK_ARTICLES = [
    {
        "id": "ART_DEMO_WEEK_01",
        "title": "一人成军实战：用息壤拉起 AI 员工矩阵",
        "file": "ART_DEMO_WEEK_01_一人成军实战：用息壤拉起 AI 员工矩阵.md",
        "tags": ["成军台", "demo-week", "lead_gen"],
        "summary": "从目标到周报 Word 的完整闭环；内容工厂与成军战役双向关联。",
        "review_pass": True,
        "review": {"pass": True, "issues": [], "suggestions": "演示稿通过"},
        "created_at": _now(5, 14),
        "campaign_id": "CMP_DEMO_WEEK_LEAD",
        "body": """---
id: ART_DEMO_WEEK_01
title: 一人成军实战：用息壤拉起 AI 员工矩阵
campaign_id: CMP_DEMO_WEEK_LEAD
---

# 一人成军实战：用息壤拉起 AI 员工矩阵

## 为什么需要「内容生产闭环」

缺编辑部的一人公司，最痛的不是「不会写」，而是：**选题 → 成稿 → 质检 → 入库 → 战役复盘** 断档。

## 成军台怎么补齐

1. **内容工厂**：选题池 / 稿件台 / 质检 / 向量检索
2. **成军战役**：调研 · 内容 · 问数 · 运营 · 复盘
3. **可验收交付**：产物抽屉 + 导出 Word 周报

## 本周可执行清单

- 发 3 条种草
- 建 10 人跟进表
- 导出成军周报 Word 归档

```python
def run_week():
    collect_topics()
    generate_article()
    quality_gate()
    export_weekly_report_docx()
    return True
assert run_week() in (True, False)
```
""",
    },
    {
        "id": "ART_DEMO_WEEK_02",
        "title": "种草内容包与转化话术（一周演示）",
        "file": "ART_DEMO_WEEK_02_种草内容包与转化话术.md",
        "tags": ["成军台", "demo-week", "content"],
        "summary": "短文案×3 + 话题标签 + 首触/跟进/逼单话术。",
        "review_pass": True,
        "review": {"pass": True, "issues": [], "suggestions": "演示稿通过"},
        "created_at": _now(4, 16),
        "campaign_id": "CMP_DEMO_WEEK_LEAD",
        "body": """---
id: ART_DEMO_WEEK_02
title: 种草内容包与转化话术（一周演示）
campaign_id: CMP_DEMO_WEEK_LEAD
---

# 种草内容包与转化话术

## 短文案 ×3

1. **一人公司也能成军**：输入目标，拉起调研/内容/问数/运营。
2. **别再只聊天**：成军台给可验收周报与 Word。
3. **息壤上的 OPC OS**：目标驱动 AI 员工矩阵。

## 话题标签

#一人成军 #息壤杯 #AI获客 #OPC #内容工厂

## 话术

- 首触：您好，看到您在关注 AI 获客…
- 跟进：本周已为您准备渠道清单+跟进表…
- 逼单：导出成军周报 Word，方便对内同步…

```python
assert len(['文案1','文案2','文案3']) == 3
```
""",
    },
    {
        "id": "ART_DEMO_WEEK_03",
        "title": "息壤+一人公司行业综述（演示入库稿）",
        "file": "ART_DEMO_WEEK_03_息壤一人公司行业综述.md",
        "tags": ["成军台", "demo-week", "industry_brief"],
        "summary": "机会点 / 风险 / 可落地知识库要点。",
        "review_pass": True,
        "review": {"pass": True, "issues": [], "suggestions": "演示稿通过"},
        "created_at": _now(2, 11),
        "campaign_id": "CMP_DEMO_WEEK_BRIEF",
        "body": """---
id: ART_DEMO_WEEK_03
title: 息壤+一人公司行业综述（演示入库稿）
campaign_id: CMP_DEMO_WEEK_BRIEF
---

# 息壤+一人公司行业综述

## 机会点

一人公司用 AI 员工矩阵补齐调研/内容/问数/运营；息壤/星辰底座降低模型接入成本。

## 风险

幻觉、空话产物、无验收物；无战役状态机则不可演示。

## 可落地知识库要点

- 战役模板：AI获客跟进 / 行业综述
- 人审卡点 + 人审意见
- 产物中心 + 导出 Word + 内容工厂关联

```python
def knowledge_pack():
    return ['机会点','风险','要点']
assert len(knowledge_pack()) == 3
```
""",
    },
]


def _seed_topics():
    history = []
    if os.path.exists(TOPICS_FILE):
        try:
            with open(TOPICS_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    existing = {t.get("id") for t in history}
    added = []
    for t in WEEK_TOPICS:
        if t["id"] in existing:
            print(f"[skip] topic {t['id']}")
            continue
        history.append(t)
        added.append(t["id"])
        print(f"[ok] topic {t['id']}")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return added


def _seed_articles():
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    meta = []
    if os.path.exists(ARTICLES_META):
        try:
            with open(ARTICLES_META, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = []
    existing = {a.get("id") for a in meta}
    added = []
    for raw in WEEK_ARTICLES:
        a = {k: v for k, v in raw.items() if k != "body"}
        body = raw["body"]
        fpath = os.path.join(ARTICLES_DIR, a["file"])
        if not os.path.exists(fpath):
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(body)
        if a["id"] in existing:
            for m in meta:
                if m.get("id") == a["id"] and a.get("campaign_id"):
                    m["campaign_id"] = a["campaign_id"]
            print(f"[skip] article meta {a['id']} (file ensured)")
            continue
        meta.append(a)
        added.append(a["id"])
        print(f"[ok] article {a['id']}")
        try:
            import vector_store
            vector_store.index_document(a["id"], a["title"], body, a.get("tags") or [], source="demo_week")
        except Exception as ex:
            print(f"[warn] vector index {a['id']}: {ex}")
    with open(ARTICLES_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return added


def _write_camp(sample: dict) -> bool:
    cid = sample["id"]
    if store.get_campaign(cid):
        print(f"[skip] campaign {cid}")
        return False
    bodies = sample.pop("artifacts_body")
    camp = {
        "id": cid,
        "goal": sample["goal"],
        "template": sample["template"],
        "status": sample["status"],
        "created_by": sample.get("created_by", "admin"),
        "created_at": sample.get("created_at", _now(6)),
        "updated_at": _now(0),
        "plan": sample["plan"],
        "tasks": sample["tasks"],
        "artifacts": [],
        "gate": {
            "required": True,
            "approved": True,
            "note": sample.get("gate_note", "一周演示包 · 人审通过"),
        },
        "llm_provider": sample.get("llm_provider", "demo-week"),
        "error": None,
        "metrics": {"hours_saved_est": sample["plan"].get("hours_saved_est", 6)},
        "report": {},
        "demo_snapshot": True,
        "demo_week": True,
    }
    os.makedirs(store.CAMPAIGNS_DIR, exist_ok=True)
    with open(store._path(cid), "w", encoding="utf-8") as f:
        json.dump(camp, f, ensure_ascii=False, indent=2)
    arts = []
    for art_id, info in bodies.items():
        if isinstance(info, str):
            body, role, title, extra = info, art_id.split("_")[-1], art_id, {}
        else:
            body = info["body"]
            role = info.get("role", art_id.split("_")[-1])
            title = info.get("title", art_id)
            extra = {k: v for k, v in info.items() if k not in ("body", "role", "title")}
        art_dir = os.path.join(store.CAMPAIGNS_DIR, cid)
        os.makedirs(art_dir, exist_ok=True)
        fname = f"{art_id}.md"
        fpath = os.path.join(art_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(body)
        arts.append({
            "id": art_id,
            "role": role,
            "title": title,
            "kind": "markdown",
            "file": fname,
            "path": fpath,
            "created_at": _now(1),
            "chars": len(body),
            **extra,
        })
    store.update_campaign(cid, artifacts=arts)
    store.bump_metric("campaigns_started", 1)
    store.bump_metric("campaigns_completed", 1)
    store.bump_metric("tasks_done", len(sample["tasks"]))
    store.bump_metric("artifacts_count", len(arts))
    store.bump_metric("est_hours_saved", float(sample["plan"].get("hours_saved_est", 6)))
    print(f"[ok] campaign {cid}")
    return True


def _follow_table():
    rows = "\n".join(
        f"| C{i:02d} | 政企数字化意向{i} | {'社群' if i % 2 else '公域'} | 成军台可一周拉起内容+跟进 | P{(i - 1) // 4 + 1} | D+{i} |"
        for i in range(1, 11)
    )
    return (
        "# 运营跟进方案 · 一周演示\n\n"
        "## 本周节奏\n- D1 发布种草\n- D2–D5 跟进 P1/P2\n- D6 导出 Word 周报\n\n"
        "## 意向客户跟进表\n"
        "| ID | 客户画像 | 触达渠道 | 首触话术摘要 | 优先级 | 下次跟进日 |\n"
        "|---|---|---|---|---|---|\n"
        + rows
        + "\n\n## 渠道投放计划\n| 渠道 | 动作 | 验收标准 |\n|---|---|---|\n"
        "| 公域内容 | 发 3 条种草 | 留资≥5 |\n| 社群 | 日报答疑 | 意向≥8 |\n| 私域 | P1 一对一 | 演示≥3 |\n"
    )


CAMPAIGNS = [
    {
        "id": "CMP_DEMO_WEEK_LEAD",
        "goal": "【一周演示】用 AI 产品获客并跟进 10 个意向客户：渠道清单、话术、跟进表与复盘",
        "template": "lead_gen",
        "status": "completed",
        "created_by": "admin",
        "created_at": _now(6, 9),
        "llm_provider": "demo-week",
        "gate_note": "渠道计划完整，跟进表≥10 行，放行终审",
        "plan": {
            "summary": "一周演示 · AI获客跟进（富产物）",
            "hours_saved_est": 6.5,
            "gate_message": "演示包已完成",
            "fallback": False,
        },
        "tasks": [
            {"id": "T1", "role": "research", "title": "目标客群与渠道调研", "status": "done",
             "brief": "ICP+渠道", "depends_on": [], "result_artifact_id": "ART_WEEK_LEAD_research", "error": None},
            {"id": "T2", "role": "content", "title": "种草内容与跟进话术包", "status": "done",
             "brief": "文案+话术", "depends_on": ["T1"], "result_artifact_id": "ART_WEEK_LEAD_content",
             "factory_article_id": "ART_DEMO_WEEK_02", "error": None},
            {"id": "T3", "role": "data", "title": "市场情报问数佐证", "status": "done",
             "brief": "问数", "depends_on": ["T1"], "result_artifact_id": "ART_WEEK_LEAD_data", "error": None},
            {"id": "T4", "role": "ops", "title": "意向客户跟进表与渠道计划", "status": "done",
             "brief": "10人跟进", "depends_on": ["T2"], "result_artifact_id": "ART_WEEK_LEAD_ops", "error": None},
            {"id": "T5", "role": "review", "title": "战役复盘周报要点", "status": "done",
             "brief": "复盘", "depends_on": ["T3", "T4"], "result_artifact_id": "ART_WEEK_LEAD_review", "error": None},
        ],
        "artifacts_body": {
            "ART_WEEK_LEAD_research": {
                "role": "research",
                "title": "调研报告 · 一周演示",
                "body": (
                    "# 调研报告 · 一周演示\n\n## 目标客群 ICP\n"
                    "- 独立开发者 / 小微经营者 / 一人公司\n\n"
                    "## 主渠道\n1. 内容种草（公域）\n2. 社群答疑\n3. 私域一对一\n\n"
                    "## 本周试点\n发 3 条种草 + 建 10 人跟进表\n"
                ),
            },
            "ART_WEEK_LEAD_content": {
                "role": "content",
                "title": "种草内容与跟进话术包",
                "factory_article_id": "ART_DEMO_WEEK_02",
                "factory_title": "种草内容包与转化话术（一周演示）",
                "factory_review_pass": True,
                "quality_gate": {"pass": True, "word_count": 900},
                "body": (
                    "> 内容工厂稿件：`ART_DEMO_WEEK_02` · 初审:True · 质检门控:True\n\n"
                    "# 种草内容与跟进话术包 · 一周演示\n\n"
                    "## 短文案×3\n1. 一人公司也能成军\n2. 别再只聊天\n3. 息壤上的 OPC OS\n\n"
                    "## 话术\n- 首触 / 跟进 / 逼单（见工厂稿 ART_DEMO_WEEK_02）\n"
                ),
            },
            "ART_WEEK_LEAD_data": {
                "role": "data",
                "title": "数据参谋 · 问数摘要",
                "body": (
                    "# 数据参谋 · 一周演示问数\n\n"
                    "| 行业 | 项目数量 |\n|---|---|\n| 政企信息化 | 28 |\n| 云服务 | 16 |\n| 网络安全 | 12 |\n"
                ),
            },
            "ART_WEEK_LEAD_ops": {
                "role": "ops",
                "title": "运营跟进 · 渠道计划",
                "body": _follow_table(),
            },
            "ART_WEEK_LEAD_review": {
                "role": "review",
                "title": "战役复盘 · 一周演示",
                "body": (
                    "# 战役复盘 · 一周演示\n\n## 完成情况\n调研/内容/问数/运营/复盘均已产出\n\n"
                    "## 关联内容工厂\n- ART_DEMO_WEEK_01 · 一人成军实战\n- ART_DEMO_WEEK_02 · 种草话术包\n\n"
                    "## 下周 TOP3\n1. 固化高意向话术\n2. 复用渠道计划\n3. 导出 Word 周报归档\n"
                ),
            },
        },
    },
    {
        "id": "CMP_DEMO_WEEK_BRIEF",
        "goal": "【一周演示】撰写「息壤+一人公司」行业综述：机会点、风险与知识库要点",
        "template": "industry_brief",
        "status": "completed",
        "created_by": "admin",
        "created_at": _now(3, 10),
        "llm_provider": "demo-week",
        "gate_note": "三段结构完整，可入库",
        "plan": {
            "summary": "一周演示 · 行业综述沉淀",
            "hours_saved_est": 5.0,
            "gate_message": "演示包已完成",
            "fallback": False,
        },
        "tasks": [
            {"id": "T1", "role": "research", "title": "行业趋势与机会速研", "status": "done",
             "brief": "速研", "depends_on": [], "result_artifact_id": "ART_WEEK_BRIEF_research", "error": None},
            {"id": "T2", "role": "data", "title": "中标/市场数据佐证", "status": "done",
             "brief": "问数", "depends_on": ["T1"], "result_artifact_id": "ART_WEEK_BRIEF_data", "error": None},
            {"id": "T3", "role": "content", "title": "撰写行业综述长文（可入库）", "status": "done",
             "brief": "综述", "depends_on": ["T1", "T2"], "result_artifact_id": "ART_WEEK_BRIEF_content",
             "factory_article_id": "ART_DEMO_WEEK_03", "error": None},
            {"id": "T4", "role": "review", "title": "知识沉淀与下周行动清单", "status": "done",
             "brief": "沉淀", "depends_on": ["T3"], "result_artifact_id": "ART_WEEK_BRIEF_review", "error": None},
        ],
        "artifacts_body": {
            "ART_WEEK_BRIEF_research": {
                "role": "research",
                "title": "行业速研",
                "body": "# 行业速研 · 一周演示\n\n## 机会点\nOPC 需要目标→小队→验收\n\n## 风险\n幻觉与空话产物\n",
            },
            "ART_WEEK_BRIEF_data": {
                "role": "data",
                "title": "数据佐证",
                "body": "# 数据佐证\n\n| 地区 | 信息化相关项目数 |\n|---|---|\n| 杭州 | 22 |\n| 宁波 | 14 |\n| 温州 | 9 |\n",
            },
            "ART_WEEK_BRIEF_content": {
                "role": "content",
                "title": "行业综述长文",
                "factory_article_id": "ART_DEMO_WEEK_03",
                "factory_title": "息壤+一人公司行业综述（演示入库稿）",
                "factory_review_pass": True,
                "quality_gate": {"pass": True, "word_count": 850},
                "body": (
                    "> 内容工厂稿件：`ART_DEMO_WEEK_03`\n\n"
                    "# 息壤+一人公司行业综述 · 一周演示\n\n"
                    "## 机会点 / 风险 / 知识库要点\n见工厂稿 ART_DEMO_WEEK_03\n"
                ),
            },
            "ART_WEEK_BRIEF_review": {
                "role": "review",
                "title": "知识沉淀清单",
                "body": "# 知识沉淀清单\n\n- 入库：机会点/风险/要点\n- 下周：补真实问数截图 + 导出 Word\n",
            },
        },
    },
]


def seed():
    print("=== seed_demo_week ===")
    topics = _seed_topics()
    articles = _seed_articles()
    camps = []
    for c in CAMPAIGNS:
        # deep-ish copy via json to avoid mutating templates on re-run path
        sample = json.loads(json.dumps(c, ensure_ascii=False))
        if _write_camp(sample):
            camps.append(sample["id"])
    # optional tiny metrics bump already done per camp
    result = {
        "topics": topics or [t["id"] for t in WEEK_TOPICS],
        "articles": articles or [a["id"] for a in WEEK_ARTICLES],
        "campaigns": camps or [c["id"] for c in CAMPAIGNS],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    seed()
