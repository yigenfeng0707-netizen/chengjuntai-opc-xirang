# -*- coding: utf-8 -*-
"""API robustness matrix: auth, empty inputs, missing ids, docx, factory, nl2sql, bid."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("CJT_BASE", "http://127.0.0.1:8090")


def req(path, method="GET", data=None, token=None, timeout=60):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"raw": raw[:300]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            d = {"raw": raw[:300]}
        return e.code, d
    except Exception as e:
        return 0, {"error": str(e)}


class M:
    def __init__(self):
        self.rows = []

    def add(self, name, ok, detail=""):
        self.rows.append({"name": name, "pass": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    @property
    def ok(self):
        return all(r["pass"] for r in self.rows)


def main():
    m = M()
    st, health = req("/api/health")
    m.add("health", st == 200 and health.get("ok"), str(health.get("demo_ready")))

    # unauthenticated protected
    st, d = req("/api/campaigns")
    m.add("unauth_campaigns_401", st in (401, 403), f"status={st}")

    st, login = req("/api/login", "POST", {"u": "admin", "p": "chengjun2026"})
    tok = (login or {}).get("token")
    m.add("login_admin", bool(tok), (login or {}).get("role", ""))
    if not tok:
        print(json.dumps({"ok": False, "checks": m.rows}, ensure_ascii=False, indent=2))
        return 1

    # empty login
    st, d = req("/api/login", "POST", {"u": "", "p": ""})
    m.add("login_empty_rejected", st >= 400 or not d.get("token"), f"status={st}")

    # core GETs
    for path in [
        "/api/status",
        "/api/metrics",
        "/api/templates",
        "/api/campaigns",
        "/api/articles",
        "/api/topics",
        "/api/logs",
        "/api/queue",
        "/api/schedule",
        "/api/users",
        "/api/artifacts/center",
        "/api/nl2sql/status",
        "/api/bid/status",
        "/api/bid/projects",
        "/api/bid/themes",
        "/api/bid/refresh_status",
    ]:
        st, d = req(path, token=tok)
        m.add(f"get {path}", st == 200, f"status={st} type={type(d).__name__}")

    # shape checks
    st, logs = req("/api/logs", token=tok)
    m.add("logs_is_list", isinstance(logs, list), type(logs).__name__)
    st, users = req("/api/users", token=tok)
    m.add("users_is_list", isinstance(users, list), type(users).__name__)
    st, camps = req("/api/campaigns", token=tok)
    m.add("campaigns_is_list", isinstance(camps, list), type(camps).__name__)

    # missing campaign
    st, d = req("/api/campaign/NO_SUCH_CAMP", token=tok)
    m.add("missing_campaign_404", st in (404, 400), f"status={st} detail={str(d)[:80]}")

    # missing artifact
    if camps:
        cid = camps[0]["id"]
        st, d = req(f"/api/campaign/{cid}/artifact/NO_ART", token=tok)
        m.add("missing_artifact", st >= 400, f"status={st}")
        # report docx for a real campaign if any completed/awaiting
        target = next((c for c in camps if c.get("status") in ("completed", "awaiting_review")), camps[0])
        st, d = req(f"/api/campaign/{target['id']}/report_docx", "POST", {}, token=tok, timeout=90)
        m.add("report_docx", st == 200 and (d.get("ok") or d.get("docx")), f"status={st} keys={list((d or {}).keys())[:6]}")
        if st == 200:
            st2, d2 = req(f"/api/campaign/{target['id']}/report_docx/file", token=tok, timeout=60)
            # file endpoint may return binary; our json parse may fail -> raw
            m.add("report_docx_file", st2 == 200, f"status={st2}")

    # article preview missing
    st, d = req("/api/article/preview?file=" + urllib.parse.quote("NO_FILE.md"), token=tok)
    m.add("preview_missing_file", st >= 400 or d.get("error") or d.get("detail"), f"status={st}")

    # article docx missing
    st, d = req("/api/article/NO_ARTICLE/docx", token=tok)
    m.add("article_docx_missing", st >= 400, f"status={st}")

    # vector empty query
    st, d = req("/api/vector/search?q=", token=tok)
    m.add("vector_empty_q", st in (200, 400), f"status={st}")

    # nl2sql empty question
    st, d = req("/api/nl2sql/query", "POST", {"question": "   "}, token=tok)
    m.add("nl2sql_empty_q", st >= 400, f"status={st}")

    # nl2sql normal (may be offline — still must not 500)
    st, d = req("/api/nl2sql/query", "POST", {"question": "各行业中标项目数量"}, token=tok, timeout=90)
    m.add("nl2sql_query_no_500", st == 200 and "ok" in (d or {}), f"status={st} offline={d.get('offline') if isinstance(d, dict) else None}")

    # bid workspace empty text
    st, d = req("/api/bid/workspace/parse", "POST", {"text": ""}, token=tok)
    m.add("bid_parse_empty", st >= 400 or not (d or {}).get("requirements"), f"status={st}")

    # bid matrix without reqs
    st, d = req("/api/bid/workspace/matrix", "POST", {"requirements": []}, token=tok)
    m.add("bid_matrix_empty", st in (200, 400), f"status={st}")

    # topic mark missing
    st, d = req("/api/topic/mark", "POST", {"id": "NO", "status": "selected"}, token=tok)
    m.add("topic_mark_missing", st == 404, f"status={st}")

    # judge ACL
    st, jlogin = req("/api/login", "POST", {"u": "judge", "p": "judge2026"})
    jtok = (jlogin or {}).get("token")
    m.add("login_judge", bool(jtok), (jlogin or {}).get("role", ""))
    if jtok:
        st, d = req("/api/campaign/start", "POST", {"goal": "x", "template": "lead_gen"}, token=jtok)
        m.add("judge_blocked_start", st in (401, 403), f"status={st}")

    print(json.dumps({"ok": m.ok, "checks": m.rows}, ensure_ascii=False, indent=2))
    return 0 if m.ok else 1


if __name__ == "__main__":
    sys.exit(main())
