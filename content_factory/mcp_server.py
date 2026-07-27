# -*- coding: utf-8 -*-
"""
模块2：MCP Stdio 标准封装
标准 stdio JSON-RPC MCP 协议，可供 OpenCode / OpenClaw / Hermes-WebUI / TeleAgent 调用
对外暴露 9 个工具：
  1. collect_topics        采集并生成候选选题
  2. generate_article      根据指定选题生成完整文稿
  3. quality_check         执行稿件质量校验
  4. analysis_topic_data   历史选题数据分析
  5. export_knowledge_doc  导出结构化知识库文档
  6. sync_vector_store     文档向量化入库
  7. run_scheduled_task    手动触发定时任务
  8. export_article_pdf    将 Markdown 文章导出 PDF
  9. task_queue_control    任务队列管理
配置文件：mcp.json
"""
import sys
import os
import json
import traceback

# 确保能 import 同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import topic_collector
import agents
import quality_gate
import data_feedback
import bid_pipeline_link
import scheduler
import vector_store
import pdf_exporter
import task_queue
import op_logger

# MCP 协议版本
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "content-factory"
SERVER_VERSION = "1.0.0"

TOOLS = [
    {"name": "collect_topics", "description": "采集并生成候选选题，输出 topics.json",
     "inputSchema": {"type": "object", "properties": {"topk": {"type": "integer", "default": 6}}}},
    {"name": "generate_article", "description": "根据指定选题生成完整 Markdown 文稿（大纲→写作→初审三Agent）",
     "inputSchema": {"type": "object", "properties": {
        "topic": {"type": "string"}, "summary": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}},
        "required": ["topic"]}},
    {"name": "quality_check", "description": "执行稿件质量校验（篇幅/代码/链接/空段落）",
     "inputSchema": {"type": "object", "properties": {"article_id": {"type": "string"}}, "required": ["article_id"]}},
    {"name": "analysis_topic_data", "description": "历史选题数据分析，联动 NL2SQL 查投标历史反向优化选题",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "export_knowledge_doc", "description": "导出结构化知识库文档（全部文章索引+摘要）",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "sync_vector_store", "description": "文档向量化入库（重新构建本地向量索引）",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "run_scheduled_task", "description": "手动触发定时任务（按 task_id 或 action）",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "export_article_pdf", "description": "将 Markdown 文章导出 PDF（单篇按ID，或批量导出全部）",
     "inputSchema": {"type": "object", "properties": {"article_id": {"type": "string"}, "batch": {"type": "boolean", "default": False}}}},
    {"name": "task_queue_control", "description": "任务队列管理（add/list/cancel/priority）",
     "inputSchema": {"type": "object", "properties": {
        "op": {"type": "string", "enum": ["add", "list", "cancel", "set_priority"]},
        "task_id": {"type": "string"}, "action": {"type": "string"},
        "priority": {"type": "integer"}}, "required": ["op"]}},
]


def _ok(req_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _err(req_id, code, message):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id,
                                 "error": {"code": code, "message": message}}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def call_tool(name: str, params: dict):
    """工具分发执行"""
    if name == "collect_topics":
        return topic_collector.collect_topics(topk=params.get("topk", 6))
    if name == "generate_article":
        return agents.generate_article(params["topic"], params.get("summary", ""), params.get("tags"))
    if name == "quality_check":
        return quality_gate.run_quality_check(article_id=params["article_id"])
    if name == "analysis_topic_data":
        return data_feedback.analyze_topic_data_with_nl2sql()
    if name == "export_knowledge_doc":
        arts = agents.list_articles()
        return {"count": len(arts), "articles": [{"id": a["id"], "title": a["title"],
                "summary": a.get("summary", ""), "tags": a.get("tags", []),
                "pass": a.get("review_pass")} for a in arts]}
    if name == "sync_vector_store":
        arts = agents.list_articles()
        n = 0
        for a in arts:
            fp = os.path.join(os.path.dirname(__file__), "articles", a["file"])
            if os.path.exists(fp):
                with open(fp, "r", encoding="utf-8") as f:
                    vector_store.index_document(a["id"], a["title"], f.read(), a.get("tags", []))
                n += 1
        return {"indexed": n, "total_in_store": len(vector_store.list_indexed())}
    if name == "run_scheduled_task":
        cfg = scheduler.load_schedule()
        t = next((x for x in cfg["tasks"] if x["id"] == params["task_id"]), None)
        if not t:
            return {"error": f"任务不存在: {params['task_id']}"}
        scheduler._execute_task(t["action"], t.get("params", {}))
        return {"status": "executed", "task_id": params["task_id"]}
    if name == "export_article_pdf":
        if params.get("batch"):
            return pdf_exporter.export_all()
        out = pdf_exporter.export_article_by_id(params["article_id"])
        return {"file": out} if out else {"error": "未找到稿件"}
    if name == "task_queue_control":
        op = params["op"]
        if op == "list":
            return task_queue.list_queue()
        if op == "add":
            tid = task_queue.add_task("MCP任务", params.get("action", "collect_topics"),
                                      {"topk": 6}, params.get("priority", 5))
            return {"task_id": tid, "status": "queued"}
        if op == "cancel":
            return {"cancelled": task_queue.cancel_task(params["task_id"])}
        if op == "set_priority":
            task_queue.set_priority(params["task_id"], params.get("priority", 5))
            return {"status": "ok"}
    return {"error": f"未知工具: {name}"}


def handle(msg: dict):
    req_id = msg.get("id")
    method = msg.get("method", "")
    try:
        if method == "initialize":
            _ok(req_id, {"protocolVersion": PROTOCOL_VERSION,
                         "capabilities": {"tools": {}},
                         "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}})
        elif method == "notifications/initialized":
            pass  # 通知无需响应
        elif method == "tools/list":
            _ok(req_id, {"tools": TOOLS})
        elif method == "tools/call":
            params = msg.get("params", {})
            tname = params.get("name")
            tparams = params.get("arguments", {})
            op_logger.log("mcp_call", f"工具调用: {tname} 参数: {tparams}")
            result = call_tool(tname, tparams)
            _ok(req_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]})
        elif method == "ping":
            _ok(req_id, {})
        else:
            _err(req_id, -32601, f"未知方法: {method}")
    except Exception as e:
        op_logger.log("mcp_error", f"{method} 异常: {e}\n{traceback.format_exc()}", level="ERROR")
        _err(req_id, -32603, str(e))


def main():
    op_logger.log("mcp_server", "MCP stdio 服务启动，等待调用...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        handle(msg)


if __name__ == "__main__":
    main()
