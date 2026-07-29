# -*- coding: utf-8 -*-
import os
import sys
import json

CF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content_factory")
sys.path.insert(0, CF)
os.chdir(CF)


def _mock_cfg():
    from config_loader import load_config
    import config_loader
    cfg = load_config()
    cfg.setdefault("demo_mode", {})["allow_mock_llm"] = True
    cfg.setdefault("llm", {})["require_real_llm"] = False
    cfg["llm"]["enabled"] = False
    cfg["max_retry"] = 1
    cfg["retry_interval"] = 0
    config_loader._CFG_CACHE = cfg


def test_commander_fallback_json():
    _mock_cfg()
    import commander
    plan = commander.plan_campaign("测试获客", template="lead_gen", allow_mock=True)
    assert "tasks" in plan and len(plan["tasks"]) >= 4
    roles = {t["role"] for t in plan["tasks"]}
    assert "research" in roles and "ops" in roles


def test_campaign_state_machine():
    _mock_cfg()
    from campaign import runner, store
    c = runner.start_campaign("测试目标", allow_mock=True)
    assert c["status"] == "planned"
    c = runner.approve_gate(c["id"])
    c = store.get_campaign(c["id"])
    assert c["status"] in ("awaiting_review", "completed", "failed")
    if c["status"] in ("awaiting_review", "completed"):
        path = runner.export_weekly_report(c["id"])
        assert path


def test_provider_status_hides_placeholder():
    _mock_cfg()
    import llm_client
    st = llm_client.provider_status()
    assert st.get("enabled") is False
    for p in st.get("providers") or []:
        assert "YOUR_" not in json.dumps(p)


if __name__ == "__main__":
    test_commander_fallback_json()
    test_campaign_state_machine()
    test_provider_status_hides_placeholder()
    print("ALL_TESTS_PASSED")
