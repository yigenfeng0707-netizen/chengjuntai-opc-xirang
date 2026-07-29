# -*- coding: utf-8 -*-
"""Auth / ACL smoke for 成军台 (no LLM-heavy path required for start with auto_approve)."""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8090"


def req(path, method="GET", data=None, token=None, timeout=90):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = None if data is None else json.dumps(data).encode()
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            d = json.loads(raw)
        except Exception:
            d = {"error": raw}
        return e.code, d


def main():
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("PASS" if cond else "FAIL"), name, detail)

    st, h = req("/api/health")
    ok("health", st == 200 and h.get("ok") and h.get("auth", {}).get("email_login"), str(h.get("auth")))

    st, d = req("/api/login", "POST", {"u": "admin", "p": "chengjun2026"})
    ok("login_admin", st == 200 and d.get("token") and d.get("role") == "super_admin", d.get("role"))

    st, d = req("/api/login", "POST", {"u": "fengyigen@qq.com", "p": "CjTai#Fengyi2026!"})
    ok("login_super_email", st == 200 and d.get("token") and d.get("role") == "super_admin", d.get("email") or d.get("user"))
    super_tok = d.get("token")

    email = "smoke_%s@example.com" % (str(time.time_ns())[-8:])
    st, d = req("/api/register", "POST", {"email": email, "password": "demo1234", "display_name": "SmokeUser"})
    ok("register", st == 200 and d.get("ok"), str(d))

    st, d = req("/api/login", "POST", {"u": email, "p": "demo1234"})
    ok("login_email_user", st == 200 and d.get("role") == "user", d.get("role"))
    user_tok = d.get("token")
    user_name = d.get("user")

    # auto_approve may still call LLM — use short goal; if LLM slow, still verify ACL separately
    st, d = req(
        "/api/campaign/start",
        "POST",
        {"goal": "冒烟：邮箱用户发起战役", "template": "lead_gen", "auto_approve": False},
        token=user_tok,
        timeout=120,
    )
    ok("user_start_campaign", st == 200 and bool(d.get("id")), d.get("id") or str(d)[:160])
    cid = d.get("id")

    st, d = req("/api/campaigns", token=user_tok)
    ok("user_sees_own", st == 200 and isinstance(d, list) and any(c.get("id") == cid for c in d), "n=%s" % (len(d) if isinstance(d, list) else d))

    st, d = req("/api/admin/usage", token=user_tok)
    ok("user_blocked_admin", st == 403, str(st))

    st, d = req("/api/admin/usage", token=super_tok)
    ok("admin_usage", st == 200 and isinstance(d, list) and len(d) >= 1, "n=%s" % (len(d) if isinstance(d, list) else d))

    st, d = req("/api/admin/trail/" + user_name, token=super_tok)
    events = d.get("events") if isinstance(d, dict) else None
    persona = (d.get("persona") or {}) if isinstance(d, dict) else {}
    ok("admin_trail", st == 200 and isinstance(events, list), "events=%s segment=%s" % (len(events or []), persona.get("segment")))

    st, d = req("/api/login", "POST", {"u": "judge", "p": "judge2026"})
    ok("login_judge", st == 200 and d.get("role") == "guest", d.get("role"))
    jtok = d.get("token")
    st, d = req("/api/campaign/start", "POST", {"goal": "x", "template": "lead_gen"}, token=jtok)
    ok("judge_denied", st == 403, str(st))

    failed = [r for r in results if not r[1]]
    print("---")
    print("PASS", sum(1 for r in results if r[1]), "/", len(results))
    if failed:
        print("FAILED:", failed)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
