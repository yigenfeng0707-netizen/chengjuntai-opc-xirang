# -*- coding: utf-8 -*-
"""写入 2~3 个已完成样例战役快照，避免评委空看板。幂等：已存在同 ID 则跳过。"""
import os
import sys
import json
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "content_factory")
sys.path.insert(0, CF)

from campaign import store  # noqa: E402


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


SAMPLES = [
    {
        "id": "CMP_DEMO_LEAD_01",
        "goal": "本周用 AI 产品获客并跟进 10 个意向客户：产出渠道清单、跟进话术与本周复盘要点",
        "template": "lead_gen",
        "status": "completed",
        "created_by": "admin",
        "llm_provider": "demo-snapshot",
        "plan": {
            "summary": "AI获客跟进｜样例快照（演示用）",
            "hours_saved_est": 6.0,
            "gate_message": "样例已完成",
            "fallback": False,
        },
        "tasks": [
            {"id": "T1", "role": "research", "title": "目标客群与渠道调研", "status": "done",
             "brief": "ICP+渠道", "depends_on": [], "result_artifact_id": "ART_DEMO_LEAD_research", "error": None},
            {"id": "T2", "role": "content", "title": "种草内容与跟进话术包", "status": "done",
             "brief": "文案+话术", "depends_on": ["T1"], "result_artifact_id": "ART_DEMO_LEAD_content", "error": None},
            {"id": "T3", "role": "data", "title": "市场情报问数佐证", "status": "done",
             "brief": "问数", "depends_on": ["T1"], "result_artifact_id": "ART_DEMO_LEAD_data", "error": None},
            {"id": "T4", "role": "ops", "title": "意向客户跟进表与渠道计划", "status": "done",
             "brief": "10人跟进", "depends_on": ["T2"], "result_artifact_id": "ART_DEMO_LEAD_ops", "error": None},
            {"id": "T5", "role": "review", "title": "战役复盘周报要点", "status": "done",
             "brief": "复盘", "depends_on": ["T3", "T4"], "result_artifact_id": "ART_DEMO_LEAD_review", "error": None},
        ],
        "artifacts_body": {
            "ART_DEMO_LEAD_research": (
                "# 调研报告 · 样例\n\n## 目标客群 ICP\n- 独立开发者 / 小微经营者 / 一人公司\n\n"
                "## 主渠道\n1. 内容种草（公域）\n2. 社群答疑\n3. 私域一对一跟进\n\n"
                "## 机会点\n一人成军降低「招不起运营」门槛\n\n## 本周可试点\n发 3 条种草 + 建 10 人跟进表\n"
            ),
            "ART_DEMO_LEAD_content": (
                "# 种草内容与跟进话术包 · 样例\n\n## 短文案×3\n1. **一人公司也能成军**：输入目标，拉起调研/内容/问数/运营。\n"
                "2. **别再只聊天**：成军台给可验收周报与 Word。\n"
                "3. **息壤上的 OPC OS**：目标驱动 AI 员工矩阵。\n\n"
                "## 话题标签\n#一人成军 #息壤杯 #AI获客 #OPC\n\n"
                "## 话术\n- 首触：您好，看到您在关注 AI 获客…\n- 跟进：本周已为您准备渠道清单+跟进表…\n"
                "- 逼单：导出成军周报 Word，方便对内同步…\n"
            ),
            "ART_DEMO_LEAD_data": (
                "# 数据参谋 · 样例问数摘要\n\n> 演示快照；线上请开「智能问数」连真实库\n\n"
                "| 行业 | 项目数量 |\n|---|---|\n| 政企信息化 | 28 |\n| 云服务 | 16 |\n| 网络安全 | 12 |\n"
            ),
            "ART_DEMO_LEAD_ops": (
                "# 运营跟进方案 · 样例\n\n## 本周节奏\n- D1 发布种草\n- D2-D5 跟进 P1/P2\n- D6 导出 Word 周报\n\n"
                "## 意向客户跟进表\n| ID | 客户画像 | 触达渠道 | 首触话术摘要 | 优先级 | 下次跟进日 |\n"
                "|---|---|---|---|---|---|\n"
                + "\n".join(
                    [f"| C{i:02d} | 政企数字化意向{i} | 社群 | 成军台可一周拉起内容+跟进 | P{(i-1)//4+1} | D+{i} |"
                     for i in range(1, 11)]
                )
                + "\n\n## 渠道投放计划\n| 渠道 | 动作 | 验收标准 |\n|---|---|---|\n"
                "| 公域内容 | 发 3 条 | 留资≥5 |\n| 社群 | 日报答疑 | 意向≥8 |\n| 私域 | P1 跟进 | 演示≥3 |\n"
            ),
            "ART_DEMO_LEAD_review": (
                "# 战役复盘 · 样例\n\n## 完成情况\n调研/内容/问数/运营/复盘均已产出\n\n"
                "## 关键产出\n- 10 人跟进表\n- 话术包\n- 渠道计划\n\n"
                "## 下周 TOP3\n1. 固化高意向话术\n2. 复用渠道计划\n3. 导出 Word 周报归档\n\n"
                "## 效率估算\n预估节省 6 人时\n"
            ),
        },
    },
    {
        "id": "CMP_DEMO_BRIEF_01",
        "goal": "撰写一篇「息壤+一人公司」行业综述：机会点、风险与可落地知识库要点",
        "template": "industry_brief",
        "status": "completed",
        "created_by": "admin",
        "llm_provider": "demo-snapshot",
        "plan": {
            "summary": "行业综述沉淀｜样例快照",
            "hours_saved_est": 5.0,
            "gate_message": "样例已完成",
            "fallback": False,
        },
        "tasks": [
            {"id": "T1", "role": "research", "title": "行业趋势与机会速研", "status": "done",
             "brief": "速研", "depends_on": [], "result_artifact_id": "ART_DEMO_BRIEF_research", "error": None},
            {"id": "T2", "role": "data", "title": "中标/市场数据佐证", "status": "done",
             "brief": "问数", "depends_on": ["T1"], "result_artifact_id": "ART_DEMO_BRIEF_data", "error": None},
            {"id": "T3", "role": "content", "title": "撰写行业综述长文（可入库）", "status": "done",
             "brief": "综述", "depends_on": ["T1", "T2"], "result_artifact_id": "ART_DEMO_BRIEF_content", "error": None},
            {"id": "T4", "role": "review", "title": "知识沉淀与下周行动清单", "status": "done",
             "brief": "沉淀", "depends_on": ["T3"], "result_artifact_id": "ART_DEMO_BRIEF_review", "error": None},
        ],
        "artifacts_body": {
            "ART_DEMO_BRIEF_research": (
                "# 行业速研 · 样例\n\n## 机会点\n1. OPC 需要「目标→小队→验收」而非纯聊天\n"
                "2. 息壤/星辰底座降低模型接入成本\n3. 政企数字化内容与问数可复用\n\n"
                "## 风险\n幻觉、空话产物、无验收物\n"
            ),
            "ART_DEMO_BRIEF_data": (
                "# 数据佐证 · 样例\n\n| 地区 | 信息化相关项目数 |\n|---|---|\n| 杭州 | 22 |\n| 宁波 | 14 |\n| 温州 | 9 |\n"
            ),
            "ART_DEMO_BRIEF_content": (
                "# 息壤+一人公司行业综述 · 样例\n\n## 机会点\n一人公司用 AI 员工矩阵补齐调研/内容/问数/运营。\n\n"
                "## 风险\n无战役状态机则不可验收；无 Word/周报则难对内同步。\n\n"
                "## 可落地知识库要点\n- 战役模板：AI获客跟进 / 行业综述\n- 人审卡点\n- 产物中心 + 导出 Word\n"
            ),
            "ART_DEMO_BRIEF_review": (
                "# 知识沉淀清单 · 样例\n\n- 入库：机会点/风险/要点三段\n- 下周：补真实问数截图 + 导出 Word\n"
            ),
        },
    },
    {
        "id": "CMP_DEMO_LEAD_02",
        "goal": "为「智云 Store 上架叙事」准备一周获客跟进包：渠道、话术、10 人清单",
        "template": "lead_gen",
        "status": "completed",
        "created_by": "admin",
        "llm_provider": "demo-snapshot",
        "plan": {
            "summary": "AI获客跟进｜Store 叙事样例",
            "hours_saved_est": 5.5,
            "gate_message": "样例已完成",
            "fallback": False,
        },
        "tasks": [
            {"id": "T1", "role": "research", "title": "Store 受众与渠道", "status": "done",
             "brief": "调研", "depends_on": [], "result_artifact_id": "ART_DEMO_S2_research", "error": None},
            {"id": "T2", "role": "content", "title": "上架叙事文案包", "status": "done",
             "brief": "文案", "depends_on": ["T1"], "result_artifact_id": "ART_DEMO_S2_content", "error": None},
            {"id": "T3", "role": "ops", "title": "10 人跟进清单", "status": "done",
             "brief": "跟进", "depends_on": ["T2"], "result_artifact_id": "ART_DEMO_S2_ops", "error": None},
            {"id": "T4", "role": "review", "title": "本周验收清单", "status": "done",
             "brief": "复盘", "depends_on": ["T3"], "result_artifact_id": "ART_DEMO_S2_review", "error": None},
        ],
        "artifacts_body": {
            "ART_DEMO_S2_research": "# Store 受众调研 · 样例\n\n开发者、小微、电信生态伙伴。\n",
            "ART_DEMO_S2_content": "# 上架叙事文案 · 样例\n\n**一人成军**：目标进，周报/Word 出。\n",
            "ART_DEMO_S2_ops": (
                "# 跟进清单 · 样例\n\n| ID | 画像 | 渠道 | 话术 | 优先级 |\n|---|---|---|---|---|\n"
                + "\n".join([f"| S{i:02d} | Store 意向{i} | 社群 | 欢迎体验成军台 Demo | P{1 if i<=3 else 2} |" for i in range(1, 11)])
                + "\n"
            ),
            "ART_DEMO_S2_review": "# 验收清单 · 样例\n\n文案包 ✓ · 10 人清单 ✓ · 可导出 Word ✓\n",
        },
    },
]


def seed():
    created = []
    for sample in SAMPLES:
        cid = sample["id"]
        if store.get_campaign(cid):
            print(f"[skip] {cid} 已存在")
            continue
        bodies = sample.pop("artifacts_body")
        # 直接写 JSON（绕过 create_campaign 的自动 ID）
        camp = {
            "id": cid,
            "goal": sample["goal"],
            "template": sample["template"],
            "status": sample["status"],
            "created_by": sample["created_by"],
            "created_at": _now(),
            "updated_at": _now(),
            "plan": sample["plan"],
            "tasks": sample["tasks"],
            "artifacts": [],
            "gate": {"required": True, "approved": True, "note": "demo snapshot"},
            "llm_provider": sample["llm_provider"],
            "error": None,
            "metrics": {"hours_saved_est": sample["plan"].get("hours_saved_est", 5)},
            "report": {},
            "demo_snapshot": True,
        }
        os.makedirs(store.CAMPAIGNS_DIR, exist_ok=True)
        with open(store._path(cid), "w", encoding="utf-8") as f:
            json.dump(camp, f, ensure_ascii=False, indent=2)
        for art_id, body in bodies.items():
            role = art_id.split("_")[-1]
            title_map = {
                "research": "调研产物（样例）",
                "content": "内容产物（样例）",
                "data": "问数产物（样例）",
                "ops": "运营跟进（样例）",
                "review": "复盘产物（样例）",
            }
            # save_artifact 会生成新 ID；改为手写固定 ID
            art_dir = os.path.join(store.CAMPAIGNS_DIR, cid)
            os.makedirs(art_dir, exist_ok=True)
            fname = f"{art_id}.md"
            fpath = os.path.join(art_dir, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(body)
            camp = store.get_campaign(cid)
            arts = list(camp.get("artifacts") or [])
            arts.append({
                "id": art_id,
                "role": role,
                "title": title_map.get(role, art_id),
                "kind": "markdown",
                "file": fname,
                "path": fpath,
                "created_at": _now(),
                "chars": len(body),
            })
            store.update_campaign(cid, artifacts=arts)
        store.bump_metric("campaigns_started", 1)
        store.bump_metric("campaigns_completed", 1)
        store.bump_metric("tasks_done", len(sample["tasks"]))
        store.bump_metric("artifacts_count", len(bodies))
        store.bump_metric("est_hours_saved", float(sample["plan"].get("hours_saved_est", 5)))
        created.append(cid)
        print(f"[ok] seeded {cid}")
    return created


if __name__ == "__main__":
    print(seed())
