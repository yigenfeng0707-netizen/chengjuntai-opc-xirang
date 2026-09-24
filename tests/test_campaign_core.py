# -*- coding: utf-8 -*-
import atexit
import os
import shutil
import sys
import json
import tempfile
import threading
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
    """轮询到终态：planning/planned/running 都是后台任务的合法中间态。"""
    deadline = time.time() + timeout
    camp = None
    while time.time() < deadline:
        camp = store.get_campaign(cid)
        if camp and camp["status"] not in ("planning", "planned", "running"):
            return camp["status"]
        time.sleep(1)
    return (camp or {}).get("status")


def test_store_atomic_write():
    """写盘失败必须显式暴露；并发读者永远读不到半截 JSON。"""
    from unittest import mock
    from campaign import store

    camp = store.create_campaign("原子写测试", template="lead_gen")
    with mock.patch.object(store, "_dump_atomic", side_effect=OSError("模拟磁盘占用")):
        got = store.update_campaign(camp["id"], status="running")
        assert got is None, f"写盘失败时 update_campaign 必须返回 None，实际 {got!r}"
        try:
            store.create_campaign("不应创建成功", template="lead_gen")
            raise AssertionError("create_campaign 写盘失败时应抛 OSError")
        except OSError as ex:
            assert "无法创建" in str(ex), ex
    after = store.get_campaign(camp["id"])
    assert after is not None, "失败写不应让战役文件消失"
    assert after["status"] == "draft", f"未落盘的更新不能生效，实际状态 {after['status']}"  # 未落盘的更新不能生效
    leftovers = [n for n in os.listdir(store.CAMPAIGNS_DIR) if n.endswith(".tmp")]
    assert leftovers == [], f"mock 失败路径留下临时文件：{leftovers}"

    payload = "x" * 50000
    corrupt = []
    reads = []

    def _writer():
        for i in range(30):
            store.update_campaign(camp["id"], goal=f"{i}-{payload}")

    t = threading.Thread(target=_writer)
    t.start()
    while t.is_alive():
        if store.get_campaign(camp["id"]) is None:
            corrupt.append("并发窗口内读到 None（写未原子或读未重试）")
            break
        reads.append(1)
        time.sleep(0.002)
    t.join()
    assert not corrupt, corrupt
    assert len(reads) >= 5, f"读者与写者没有真正并发，测不到原子性：{len(reads)} 次读"
    leftovers = [n for n in os.listdir(store.CAMPAIGNS_DIR) if n.endswith(".tmp")]
    assert leftovers == [], f"真实写入后残留临时文件：{leftovers}"

    # 产物登记与驳回同样是"写失败不能当成功"：一个抛错，一个不得把 null 交给前端
    # 计数用 spy 断，不能读 metrics 文件：同一个 mock 下 bump_metric 自己也写不进去，读了也是假绿
    with mock.patch.object(store, "_dump_atomic", side_effect=OSError("模拟磁盘占用")), \
            mock.patch.object(store, "bump_metric") as bump_spy:
        try:
            store.save_artifact(camp["id"], "ops", "标题", "正文")
            raise AssertionError("save_artifact 登记写盘失败时应抛 OSError")
        except OSError as ex:
            assert "未能落盘" in str(ex), ex
        assert not bump_spy.called, f"登记失败不得计数，实际调用 {bump_spy.call_args_list}"
    from campaign import runner
    with mock.patch.object(runner.store, "update_campaign", return_value=None):
        try:
            runner.reject_gate(camp["id"], note="测试")
            raise AssertionError("reject_gate 写盘失败时应抛 RuntimeError")
        except RuntimeError as ex:
            assert "未能落盘" in str(ex), ex


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
    test_store_atomic_write()
    test_campaign_state_machine()
    test_provider_status_hides_placeholder()
    print("ALL_TESTS_PASSED")
