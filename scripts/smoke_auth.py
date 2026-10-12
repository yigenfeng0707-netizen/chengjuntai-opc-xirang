# -*- coding: utf-8 -*-
"""Auth / ACL smoke for 成军台（无需 LLM 重路径即可跑通）。

**自清理约定（务必保留）**：本脚本会临时注册一个 `smoke_*@example.com` 账号、
以该账号发起一个战役、并产生若干行为事件。这些都属于测试残留，必须在 finally 里删干净，
否则每跑一次就会往 `users.json` / `data/campaigns/` / `data/user_events.jsonl` 累积一份垃圾。

依赖服务端提供两个删除接口（见 web_server.py）：
  POST /api/campaign/{cid}/delete   属主或超管
  POST /api/admin/user/delete       仅超管（连带清理该账号的行为事件）

鉴权头约定：默认走 `X-Chengjun-Token`（生产/魔搭主路径）；额外用一次 `Authorization`
回归验证兼容回落路径，防止改头之后把老调用方（nginx / MCP / 老脚本）改坏。
"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("CHENGJUNTAI_SMOKE_BASE", "http://127.0.0.1:8090")
AUTH_HEADER = "X-Chengjun-Token"


def req(path, method="GET", data=None, token=None, timeout=90, header=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers[header or AUTH_HEADER] = token
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


def teardown(state, log):
    """删除本次产生的战役与账号。返回 True 表示已清理干净。"""
    clean = True

    cid = state.get("cid")
    if cid:
        # 优先用属主身份删（同时验证属主删除权限），失败再让超管兜底
        st, d = req("/api/campaign/%s/delete" % cid, "POST", token=state.get("user_tok"))
        if st != 200:
            st, d = req("/api/campaign/%s/delete" % cid, "POST", token=state.get("admin_tok"))
        if st == 200:
            log("CLEANUP campaign %s -> removed" % cid)
        else:
            log("CLEANUP-FAIL campaign %s -> HTTP %s %s" % (cid, st, d))
            clean = False

    uname = state.get("username")
    if uname:
        st, d = req(
            "/api/admin/user/delete", "POST", {"identity": uname}, token=state.get("admin_tok")
        )
        if st == 200:
            log(
                "CLEANUP user %s -> removed (events_purged=%s)"
                % (uname, d.get("events_purged"))
            )
        else:
            log("CLEANUP-FAIL user %s -> HTTP %s %s" % (uname, st, d))
            clean = False

    return clean


def main():
    results = []
    state = {}

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("PASS" if cond else "FAIL"), name, detail)

    def log(msg):
        print("    ", msg)

    try:
        st, h = req("/api/health")
        ok("health", st == 200 and h.get("ok") and h.get("auth", {}).get("email_login"), str(h.get("auth")))

        st, d = req("/api/login", "POST", {"u": "admin", "p": "chengjun2026"})
        ok("login_admin", st == 200 and d.get("token") and d.get("role") == "super_admin", d.get("role"))
        admin_tok = d.get("token")
        state["admin_tok"] = admin_tok

        # 兼容回归：老调用方仍用 Authorization: Bearer，必须依然可用
        st, d = req("/api/status", token=admin_tok, header="Authorization")
        ok("legacy_authorization_still_ok", st == 200, "HTTP %s" % st)

        st, d = req("/api/login", "POST", {"u": "fengyigen@qq.com", "p": "CjTai#Fengyi2026!"})
        ok("login_super_email", st == 200 and d.get("token") and d.get("role") == "super_admin", d.get("email") or d.get("user"))
        super_tok = d.get("token")

        email = "smoke_%s@example.com" % (str(time.time_ns())[-8:])
        st, d = req("/api/register", "POST", {"email": email, "password": "demo1234", "display_name": "SmokeUser"})
        ok("register", st == 200 and d.get("ok"), str(d))
        # register 的 user 字段可能是字符串（用户名）也可能是对象，两种都兼容
        reg_user = d.get("user")
        if isinstance(reg_user, dict):
            state["username"] = reg_user.get("username")
        elif isinstance(reg_user, str) and reg_user:
            state["username"] = reg_user

        st, d = req("/api/login", "POST", {"u": email, "p": "demo1234"})
        ok("login_email_user", st == 200 and d.get("role") == "user", d.get("role"))
        user_tok = d.get("token")
        state["user_tok"] = user_tok
        user_name = d.get("user")
        state["username"] = state.get("username") or user_name

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
        state["cid"] = cid

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
    finally:
        print("--- cleanup ---")
        clean = teardown(state, log)
        ok("no_residue", clean, "临时账号与战役已删除" if clean else "仍有残留，见上方 CLEANUP-FAIL")

    failed = [r for r in results if not r[1]]
    print("---")
    print("PASS", sum(1 for r in results if r[1]), "/", len(results))
    if failed:
        print("FAILED:", failed)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
