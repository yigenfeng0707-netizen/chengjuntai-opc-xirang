# -*- coding: utf-8 -*-
"""
成军台 MCP 服务（stdio）
工具：start_campaign / list_campaigns / list_tasks / approve_gate / export_report
可供 TeleAgent / 智云生态挂载
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from campaign import runner as camp_runner
from campaign import store as camp_store
from config_loader import load_config


TOOLS = [
    {
        "name": "start_campaign",
        "description": "发起成军台战役：输入目标与模板，生成任务树（默认等待人审）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "template": {"type": "string", "enum": ["lead_gen", "industry_brief"]},
                "auto_approve": {"type": "boolean"},
            },
            "required": ["goal"],
        },
    },
    {
        "name": "list_campaigns",
        "description": "列出最近战役",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
    },
    {
        "name": "list_tasks",
        "description": "查看指定战役任务树与状态",
        "inputSchema": {
            "type": "object",
            "properties": {"campaign_id": {"type": "string"}},
            "required": ["campaign_id"],
        },
    },
    {
        "name": "approve_gate",
        "description": "人审通过：planned→执行；awaiting_review→完成",
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["campaign_id"],
        },
    },
    {
        "name": "export_report",
        "description": "导出成军周报（Markdown/PDF）",
        "inputSchema": {
            "type": "object",
            "properties": {"campaign_id": {"type": "string"}},
            "required": ["campaign_id"],
        },
    },
]


def _handle(name: str, args: dict) -> dict:
    allow_mock = bool(load_config().get("demo_mode", {}).get("allow_mock_llm", False))
    if name == "start_campaign":
        return camp_runner.start_campaign(
            args["goal"],
            template=args.get("template", "lead_gen"),
            allow_mock=allow_mock,
            auto_approve=bool(args.get("auto_approve", False)),
        )
    if name == "list_campaigns":
        return {"campaigns": camp_store.list_campaigns(int(args.get("limit", 20)))}
    if name == "list_tasks":
        c = camp_store.get_campaign(args["campaign_id"])
        if not c:
            return {"error": "not found"}
        return {"id": c["id"], "status": c["status"], "tasks": c.get("tasks", []), "artifacts": c.get("artifacts", [])}
    if name == "approve_gate":
        return camp_runner.approve_gate(args["campaign_id"], note=args.get("note", ""))
    if name == "export_report":
        path = camp_runner.export_weekly_report(args["campaign_id"])
        return {"path": path, "campaign": camp_store.get_campaign(args["campaign_id"])}
    return {"error": f"unknown tool {name}"}


def _send(msg: dict):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    """极简 JSON-RPC 行协议，便于本地联调；也可被 MCP 宿主包装。"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as ex:
            _send({"error": str(ex)})
            continue
        method = req.get("method")
        rid = req.get("id")
        if method == "tools/list":
            _send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
            continue
        if method == "tools/call":
            params = req.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            try:
                result = _handle(name, args)
                _send({"jsonrpc": "2.0", "id": rid, "result": result})
            except Exception as ex:
                _send({"jsonrpc": "2.0", "id": rid, "error": {"message": str(ex)}})
            continue
        _send({"jsonrpc": "2.0", "id": rid, "error": {"message": f"unsupported method {method}"}})


if __name__ == "__main__":
    main()
