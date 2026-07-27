# -*- coding: utf-8 -*-
"""
NL2SQL 7题验证脚本 — 在真实数据上测试 LLM NL2SQL 质量
每道题：发送自然语言 → 后端 LLM 生成 SQL → 执行 SQL → 验证结果合理性
"""
import requests
import json
import time
import os
import sys
import yaml

# 从 config.yaml 读取 Token（与后端/MCP服务共用同一配置）
_CF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_factory")
if _CF_DIR not in sys.path:
    sys.path.insert(0, _CF_DIR)

def _load_token():
    try:
        cfg_path = os.path.join(_CF_DIR, "config.yaml")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("nl2sql_backend", {}).get("api_token", "demo-token-2026")
    except Exception:
        return "demo-token-2026"

BASE = "http://127.0.0.1:8082"
TOKEN = _load_token()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

TESTS = [
    {
        "q": "各城市有多少个项目",
        "desc": "GROUP BY region + COUNT",
        "check": lambda r: r["row_count"] >= 3 and any("杭州" in str(row) for row in r.get("rows", [])),
        "key_check": "返回≥3城市且行数据中有杭州",
    },
    {
        "q": "各行业的总金额是多少",
        "desc": "GROUP BY industry + SUM(win_amount)",
        "check": lambda r: r["row_count"] >= 3 and r["sql"].lower().count("sum") > 0,
        "key_check": "返回≥3行业且SQL含SUM",
    },
    {
        "q": "金额超过500万的项目有哪些",
        "desc": "WHERE win_amount > 500",
        "check": lambda r: r["row_count"] >= 0 and "500" in r["sql"],
        "key_check": "SQL含500条件",
    },
    {
        "q": "杭州的项目有哪些",
        "desc": "WHERE region = '杭州'",
        "check": lambda r: "杭州" in r["sql"] or "杭州" in str(r.get("rows", [])),
        "key_check": "结果含杭州",
    },
    {
        "q": "中标和进行中的项目各有多少",
        "desc": "GROUP BY status + COUNT",
        "check": lambda r: "status" in r["sql"].lower() and r["row_count"] >= 2,
        "key_check": "SQL含status且返回≥2行",
    },
    {
        "q": "金额最大的5个项目",
        "desc": "ORDER BY win_amount DESC LIMIT 5",
        "check": lambda r: r["row_count"] <= 5 and "win_amount" in r["sql"].lower() and "desc" in r["sql"].lower(),
        "key_check": "≤5行+SQL含ORDER BY win_amount DESC",
    },
    {
        "q": "最近半年的项目有哪些",
        "desc": "WHERE bid_date >= 半年前",
        "check": lambda r: r["row_count"] >= 0 and "bid_date" in r["sql"].lower(),
        "key_check": "SQL含bid_date条件",
    },
]

print("=" * 70)
print("NL2SQL 7题验证 — 真实数据 (60条, 54条真实金额)")
print("=" * 70)

passed = 0
for i, t in enumerate(TESTS, 1):
    print(f"\n[{i}/7] {t['q']}")
    print(f"     期望: {t['desc']}")
    try:
        resp = requests.post(
            f"{BASE}/api/v1/query/nl2sql",
            headers=HEADERS,
            json={"question": t["q"], "chart_type": "table", "user_id": ""},
            timeout=120,
        )
        if resp.status_code != 200:
            print(f"     ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            continue
        r = resp.json()
        mode = r.get("nl2sql_mode", "?")
        sql_preview = r.get("sql", "")[:120]
        print(f"     模式: {mode}")
        print(f"     SQL: {sql_preview}")
        print(f"     列: {r.get('columns', [])}")
        print(f"     行数: {r.get('row_count', 0)}")
        if r.get("rows"):
            for row in r["rows"][:3]:
                print(f"       {row}")
            if r["row_count"] > 3:
                print(f"       ... (共{r['row_count']}行)")

        ok = t["check"](r)
        if ok:
            passed += 1
            print(f"     ✅ PASS — {t['key_check']}")
        else:
            print(f"     ❌ FAIL — {t['key_check']}")
    except Exception as e:
        print(f"     ❌ ERROR: {e}")

print(f"\n{'=' * 70}")
print(f"结果: {passed}/7 通过")
print(f"{'=' * 70}")
