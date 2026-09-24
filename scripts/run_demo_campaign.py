# -*- coding: utf-8 -*-
"""标准样例战役回归：关闭 LLM，显式 mock，验证状态机（无外网）"""
import atexit
import os
import sys
import json
import shutil
import tempfile
import time

CF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content_factory")
WRITE_ROOT = tempfile.mkdtemp(prefix="chengjuntai-regression-")
os.environ["CHENGJUNTAI_WRITE_ROOT"] = WRITE_ROOT
atexit.register(shutil.rmtree, WRITE_ROOT, True)
sys.path.insert(0, CF)
os.chdir(CF)

PENDING = ("planning", "planned", "running")


def _wait_status(store, cid, timeout=60):
    """轮询到终态：running 是后台任务的合法中间态，读到 None 说明文件正被写，继续等而非崩。"""
    deadline = time.time() + timeout
    camp = None
    while time.time() < deadline:
        camp = store.get_campaign(cid)
        if camp and camp["status"] not in PENDING:
            return camp["status"]
        time.sleep(1)
    return (camp or {}).get("status")


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

    lead_id = camp["id"]
    runner.approve_gate(lead_id, note="demo")
    lead_status = _wait_status(store, lead_id)
    assert lead_status in ("awaiting_review", "completed"), lead_status
    assert runner.export_weekly_report(lead_id), "report path empty"
    if lead_status == "awaiting_review":
        runner.approve_gate(lead_id, note="final")
        lead_status = _wait_status(store, lead_id, timeout=10)
    assert lead_status == "completed", lead_status

    brief_id = runner.start_campaign(
        "撰写一篇息壤+一人公司行业综述并沉淀知识库要点",
        template="industry_brief",
        allow_mock=True,
        auto_approve=True,
    )["id"]
    brief_status = _wait_status(store, brief_id)
    assert brief_status in ("awaiting_review", "completed"), brief_status
    if brief_status == "awaiting_review":
        runner.approve_gate(brief_id, note="final")
        runner.export_weekly_report(brief_id)
        brief_status = _wait_status(store, brief_id, timeout=10)
    assert brief_status == "completed", brief_status
    print(json.dumps({
        "lead_gen": lead_status,
        "industry_brief": brief_status,
        "metrics": store.metrics_snapshot(),
        "ok": True,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
