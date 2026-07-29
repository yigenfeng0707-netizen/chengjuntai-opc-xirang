# -*- coding: utf-8 -*-
"""标准样例战役回归：关闭 LLM，显式 mock，验证状态机（无外网）"""
import os
import sys
import json

CF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content_factory")
sys.path.insert(0, CF)
os.chdir(CF)


def main():
    from config_loader import load_config
    import config_loader
    cfg = load_config()
    cfg.setdefault("demo_mode", {})["allow_mock_llm"] = True
    cfg.setdefault("llm", {})["require_real_llm"] = False
    cfg["llm"]["enabled"] = False
    cfg["max_retry"] = 1
    cfg["retry_interval"] = 0
    config_loader._CFG_CACHE = cfg

    from campaign import runner, store

    goal = "本周用 AI 产品获客并跟进 10 个意向客户"
    camp = runner.start_campaign(goal, template="lead_gen", allow_mock=True, auto_approve=False)
    assert camp["status"] == "planned", camp["status"]
    assert len(camp.get("tasks") or []) >= 4, camp.get("tasks")

    camp = runner.approve_gate(camp["id"], note="demo")
    camp = store.get_campaign(camp["id"])
    assert camp["status"] in ("awaiting_review", "completed", "failed", "running"), camp["status"]

    if camp["status"] in ("awaiting_review", "completed"):
        path = runner.export_weekly_report(camp["id"])
        assert path, "report path empty"
        if camp["status"] == "awaiting_review":
            camp = runner.approve_gate(camp["id"], note="final")
        assert store.get_campaign(camp["id"])["status"] == "completed"

    camp2 = runner.start_campaign(
        "撰写一篇息壤+一人公司行业综述并沉淀知识库要点",
        template="industry_brief",
        allow_mock=True,
        auto_approve=True,
    )
    camp2 = store.get_campaign(camp2["id"])
    if camp2["status"] == "awaiting_review":
        camp2 = runner.approve_gate(camp2["id"], note="final")
        runner.export_weekly_report(camp2["id"])
        camp2 = store.get_campaign(camp2["id"])
    print(json.dumps({
        "lead_gen": store.get_campaign(camp["id"])["status"],
        "industry_brief": camp2["status"],
        "metrics": store.metrics_snapshot(),
        "ok": True,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
