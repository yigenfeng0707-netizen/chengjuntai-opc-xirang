# -*- coding: utf-8 -*-
"""冒烟：stdio MCP 工具是否可注册（tools/list）

验证成军台战役 MCP + 内容工厂 MCP 的工具清单，不调用 LLM、不需要 Key。
退出码 0 = 两套服务均可 tools/list 且含预期工具名。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "content_factory")

EXPECTED = {
    "mcp_campaign_server.py": {
        "start_campaign",
        "list_campaigns",
        "list_tasks",
        "approve_gate",
        "export_report",
    },
    "mcp_server.py": {
        "collect_topics",
        "generate_article",
        "quality_check",
        "analysis_topic_data",
        "export_knowledge_doc",
        "sync_vector_store",
        "run_scheduled_task",
        "export_article_pdf",
        "task_queue_control",
    },
}


def _list_tools(script: str) -> list:
    path = os.path.join(CF, script)
    req = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        ensure_ascii=False,
    )
    proc = subprocess.run(
        [sys.executable, path],
        input=req + "\n",
        capture_output=True,
        text=True,
        cwd=CF,
        timeout=20,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode not in (0, None) and not proc.stdout.strip():
        raise RuntimeError(f"{script} exit={proc.returncode} stderr={proc.stderr[:400]}")
    # 取最后一行非空 JSON（部分实现可能打日志到 stdout；本实现仅回一行）
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError(f"{script} 无 stdout；stderr={proc.stderr[:400]}")
    msg = None
    for ln in reversed(lines):
        try:
            msg = json.loads(ln)
            break
        except json.JSONDecodeError:
            continue
    if not msg:
        raise RuntimeError(f"{script} 无法解析 JSON：{lines[-1][:200]}")
    if msg.get("error"):
        raise RuntimeError(f"{script} error={msg['error']}")
    tools = (msg.get("result") or {}).get("tools") or []
    return [t.get("name") for t in tools if t.get("name")]


def main() -> int:
    report = {"ok": True, "servers": {}}
    for script, expect in EXPECTED.items():
        try:
            names = _list_tools(script)
            missing = sorted(expect - set(names))
            entry = {
                "pass": not missing,
                "tools": names,
                "missing": missing,
                "count": len(names),
            }
            if missing:
                report["ok"] = False
        except Exception as ex:
            entry = {"pass": False, "error": str(ex)}
            report["ok"] = False
        report["servers"][script] = entry

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\n挂载方式：仓库根 mcp.json → Cursor / TeleAgent MCP 宿主")
    print("联调：python content_factory/mcp_campaign_server.py  ← stdin 发 tools/list")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
