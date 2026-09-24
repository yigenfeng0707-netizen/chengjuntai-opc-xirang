# -*- coding: utf-8 -*-
import atexit
import os
import shutil
import sys
import json
import tempfile
import time

CF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content_factory")
WRITE_ROOT = tempfile.mkdtemp(prefix="chengjuntai-regression-")
os.environ["CHENGJUNTAI_WRITE_ROOT"] = WRITE_ROOT
atexit.register(shutil.rmtree, WRITE_ROOT, True)
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


def _wait_terminal(store, cid, timeout=60):
    """轮询到终态：running 是后台任务的合法中间态，读到 None 说明文件正被写，继续等。"""
    deadline = time.time() + timeout
    camp = None
    while time.time() < deadline:
        camp = store.get_campaign(cid)
        if camp and camp["status"] not in ("planning", "planned", "running"):
            return camp["status"]
        time.sleep(1)
    return (camp or {}).get("status")


def test_campaign_state_machine():
    _mock_cfg()
    from campaign import runner, store
    c = runner.start_campaign("测试目标", allow_mock=True)
    assert c["status"] == "planned"
    runner.approve_gate(c["id"])
    status = _wait_terminal(store, c["id"])
    assert status in ("awaiting_review", "completed"), status
    assert runner.export_weekly_report(c["id"])


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
