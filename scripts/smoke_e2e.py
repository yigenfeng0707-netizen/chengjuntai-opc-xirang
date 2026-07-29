# -*- coding: utf-8 -*-
"""
成军台预发冒烟：health → login → campaign → artifacts → report → factory → judge ACL

用法:
  python scripts/smoke_e2e.py              # 优先真实 LLM（Web 须已起在 :8090）
  python scripts/smoke_e2e.py --mock       # 进程内 mock 状态机（无网、不依赖 Web）
  python scripts/smoke_e2e.py --base http://127.0.0.1:8090 --skip-llm-heavy

退出码 0=全部关键检查通过；1=失败。不打印 API Key。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "content_factory")


def _req(base: str, path: str, method: str = "GET", data=None, token: str | None = None, timeout: int = 300):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"raw": raw[:500]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            d = {"raw": raw[:500]}
        return e.code, d


class Matrix:
    def __init__(self):
        self.rows = []

    def add(self, name: str, ok: bool, detail: str = ""):
        self.rows.append({"name": name, "pass": bool(ok), "detail": detail})
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))

    @property
    def ok(self) -> bool:
        return all(r["pass"] for r in self.rows)


def run_mock(m: Matrix):
    sys.path.insert(0, CF)
    os.chdir(CF)
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

    camp = runner.start_campaign("冒烟获客", template="lead_gen", allow_mock=True, auto_approve=False)
    m.add("mock_start_planned", camp.get("status") == "planned", camp.get("status"))
    camp = runner.approve_gate(camp["id"], note="smoke")
    camp = store.get_campaign(camp["id"])
    m.add("mock_after_approve", camp["status"] in ("awaiting_review", "completed", "failed"), camp["status"])
    if camp["status"] in ("awaiting_review", "completed"):
        path = runner.export_weekly_report(camp["id"])
        m.add("mock_report", bool(path), path or "")
        if camp["status"] == "awaiting_review":
            camp = runner.approve_gate(camp["id"], note="final")
        m.add("mock_completed", store.get_campaign(camp["id"])["status"] == "completed")
    else:
        m.add("mock_report", False, "campaign failed before report")
        m.add("mock_completed", False, camp.get("status"))


def run_http(base: str, m: Matrix, skip_llm_heavy: bool):
    st, health = _req(base, "/api/health", timeout=10)
    llm = (health or {}).get("llm") or {}
    m.add(
        "health",
        st == 200 and bool((health or {}).get("ok")),
        f"demo_ready={health.get('demo_ready')} providers={len(llm.get('providers') or [])}",
    )
    m.add("health_llm_enabled", bool(llm.get("enabled")), llm.get("active_name") or llm.get("hint", "")[:80])

    st, login = _req(base, "/api/login", "POST", {"u": "admin", "p": "chengjun2026"}, timeout=10)
    token = (login or {}).get("token")
    m.add("login_admin", st == 200 and bool(token), f"role={(login or {}).get('role')}")

    st, jlogin = _req(base, "/api/login", "POST", {"u": "judge", "p": "judge2026"}, timeout=10)
    jtoken = (jlogin or {}).get("token")
    m.add("login_judge", st == 200 and bool(jtoken), f"role={(jlogin or {}).get('role')}")

    st, denied = _req(
        base,
        "/api/campaign/start",
        "POST",
        {"goal": "judge should fail", "template": "lead_gen"},
        token=jtoken,
        timeout=10,
    )
    m.add("judge_cannot_run_task", st == 403, f"status={st} detail={(denied or {}).get('detail')}")

    st, metrics = _req(base, "/api/metrics", token=token, timeout=10)
    m.add("metrics", st == 200 and isinstance(metrics, dict), str(list((metrics or {}).keys())[:5]))

    st, camps = _req(base, "/api/campaigns", token=token, timeout=10)
    m.add("campaigns_list", st == 200 and isinstance(camps, list), f"count={len(camps) if isinstance(camps, list) else '?'}")

    if skip_llm_heavy:
        m.add("campaign_e2e", True, "skipped (--skip-llm-heavy)")
        m.add("factory_generate", True, "skipped (--skip-llm-heavy)")
        return

    if not llm.get("enabled"):
        m.add("campaign_e2e", False, "LLM disabled — configure interim keys in gitignored config.yaml")
        m.add("factory_generate", False, "skipped (no LLM)")
        return

    goal = "本周用 AI 产品获客并跟进 10 个意向客户：产出渠道清单、跟进话术与本周复盘要点"
    t0 = time.time()
    st, camp = _req(
        base,
        "/api/campaign/start",
        "POST",
        {"goal": goal, "template": "lead_gen", "auto_approve": False},
        token=token,
        timeout=180,
    )
    cid = (camp or {}).get("id")
    m.add(
        "campaign_start",
        st == 200 and bool(cid) and (camp or {}).get("status") == "planned",
        f"status={st} id={cid} camp_status={(camp or {}).get('status')} {time.time()-t0:.1f}s",
    )
    if not cid:
        m.add("campaign_approve_run", False, "no campaign id")
        m.add("campaign_artifacts", False, "n/a")
        m.add("campaign_report", False, "n/a")
        m.add("factory_generate", False, "skipped after campaign fail")
        return

    t0 = time.time()
    st, after = _req(
        base,
        f"/api/campaign/{cid}/approve",
        "POST",
        {"note": "smoke e2e"},
        token=token,
        timeout=600,
    )
    after = after or {}
    # approve may return mid-run; poll until terminal-ish
    terminal = {"awaiting_review", "completed", "failed"}
    for _ in range(60):
        st2, detail = _req(base, f"/api/campaign/{cid}", token=token, timeout=30)
        if st2 == 200 and (detail or {}).get("status") in terminal:
            after = detail
            break
        if st2 == 200 and (detail or {}).get("status") == "running":
            time.sleep(3)
            continue
        break
    status = after.get("status")
    m.add(
        "campaign_approve_run",
        st == 200 and status in ("awaiting_review", "completed"),
        f"http={st} status={status} arts={len(after.get('artifacts') or [])} {time.time()-t0:.1f}s",
    )

    arts = after.get("artifacts") or []
    m.add("campaign_artifacts", len(arts) >= 1, f"count={len(arts)}")
    if arts:
        aid = arts[0]["id"]
        st, art = _req(base, f"/api/campaign/{cid}/artifact/{aid}", token=token, timeout=30)
        m.add("artifact_fetch", st == 200 and bool((art or {}).get("text")), f"id={aid} chars={len((art or {}).get('text') or '')}")
    else:
        m.add("artifact_fetch", False, "no artifacts")

    st, rep = _req(base, f"/api/campaign/{cid}/report", "POST", {}, token=token, timeout=120)
    m.add("campaign_report", st == 200 and bool((rep or {}).get("path")), f"path={(rep or {}).get('path')}")

    if status == "awaiting_review":
        st, fin = _req(base, f"/api/campaign/{cid}/approve", "POST", {"note": "final"}, token=token, timeout=60)
        m.add("campaign_final_approve", st == 200 and (fin or {}).get("status") == "completed", f"status={(fin or {}).get('status')}")
    else:
        m.add("campaign_final_approve", status == "completed", f"already {status}")

    t0 = time.time()
    st, art_gen = _req(
        base,
        "/api/run",
        "POST",
        {
            "action": "generate_article",
            "params": {
                "topic": "一人成军实战：用息壤拉起 AI 员工矩阵",
                "summary": "smoke e2e",
                "tags": ["成军台", "smoke"],
            },
        },
        token=token,
        timeout=300,
    )
    m.add(
        "factory_generate",
        st == 200 and bool((art_gen or {}).get("id")),
        f"http={st} id={(art_gen or {}).get('id')} review={(art_gen or {}).get('review_pass')} {time.time()-t0:.1f}s",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    ap.add_argument("--mock", action="store_true", help="进程内 mock，不打 HTTP")
    ap.add_argument("--skip-llm-heavy", action="store_true", help="只测 health/login/ACL/列表")
    args = ap.parse_args()
    m = Matrix()
    if args.mock:
        run_mock(m)
    else:
        run_http(args.base.rstrip("/"), m, args.skip_llm_heavy)
    print("\n" + json.dumps({"ok": m.ok, "checks": m.rows}, ensure_ascii=False, indent=2))
    sys.exit(0 if m.ok else 1)


if __name__ == "__main__":
    main()
