# -*- coding: utf-8 -*-
"""数据参谋：联动 NL2SQL MCP / 直连 znws / 降级为 LLM 市场洞察（显式标注）"""
import json
import socket
import requests
import llm_client
import op_logger
from config_loader import load_config


def nl2sql_online() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", 8765))
        s.close()
        return True
    except OSError:
        return False


def znws_online() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", 8082))
        s.close()
        return True
    except OSError:
        return False


def query_nl2sql(question: str, dataset_name: str = "", chart_type: str = "table") -> dict:
    """
    真实问数入口。优先 MCP(8765)，其次直连 znws(8082)。
    成功返回 {ok, source, columns, rows, sql, nl2sql_mode, raw}
    失败返回 {ok: False, error, offline: bool}
    """
    cfg = load_config()
    ds = dataset_name or cfg.get("nl2sql_default_dataset", "bid_projects")
    backend = cfg.get("nl2sql_backend") or {}
    token = backend.get("api_token", "demo-token-2026")
    znws_base = backend.get("znws_query_url", "http://127.0.0.1:8082/api/v1").rstrip("/")
    mcp_url = cfg.get("nl2sql_mcp_url", "http://127.0.0.1:8765/mcp")

    # 1) MCP HTTP（成军台自有协议 type/call_tool）
    if nl2sql_online():
        try:
            payload = {
                "type": "call_tool",
                "name": "intelligent_query",
                "parameters": {
                    "question": question,
                    "dataset_name": ds,
                    "chart_type": chart_type or "table",
                    "user_id": cfg.get("nl2sql_default_user_id") or "",
                },
            }
            r = requests.post(mcp_url, json=payload, timeout=45)
            if r.status_code == 200:
                data = r.json()
                result = data.get("result") if isinstance(data, dict) else data
                if isinstance(result, dict) and "error" not in result and (
                    result.get("rows") is not None or result.get("sql")
                ):
                    return {
                        "ok": True,
                        "source": "mcp",
                        "columns": result.get("columns") or [],
                        "rows": result.get("rows") or [],
                        "sql": result.get("sql") or "",
                        "nl2sql_mode": result.get("nl2sql_mode") or "mcp",
                        "row_count": result.get("row_count", len(result.get("rows") or [])),
                        "raw": result,
                    }
                if isinstance(result, dict) and result.get("error"):
                    op_logger.log("agent_data", f"MCP 问数错误: {result.get('error')}", level="WARN")
        except Exception as ex:
            op_logger.log("agent_data", f"MCP 调用失败: {ex}", level="WARN")

    # 2) 直连 znws 后端
    if znws_online():
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "question": question,
                "dataset_name": ds,
                "chart_type": chart_type or "table",
                "user_id": cfg.get("nl2sql_default_user_id") or "",
            }
            r = requests.post(f"{znws_base}/query/nl2sql", json=payload, headers=headers, timeout=45)
            if r.status_code == 200:
                result = r.json()
                if isinstance(result, dict) and "error" not in result:
                    return {
                        "ok": True,
                        "source": "znws",
                        "columns": result.get("columns") or [],
                        "rows": result.get("rows") or [],
                        "sql": result.get("sql") or "",
                        "nl2sql_mode": result.get("nl2sql_mode") or "znws",
                        "row_count": result.get("row_count", len(result.get("rows") or [])),
                        "raw": result,
                    }
                return {"ok": False, "error": (result or {}).get("error") or r.text, "offline": False}
            return {"ok": False, "error": f"znws HTTP {r.status_code}: {r.text[:200]}", "offline": False}
        except Exception as ex:
            op_logger.log("agent_data", f"znws 直连失败: {ex}", level="WARN")
            return {"ok": False, "error": str(ex), "offline": False}

    return {
        "ok": False,
        "error": "NL2SQL 离线（8765 MCP / 8082 znws 均不可达）。请运行 scripts/start_nl2sql_demo.bat",
        "offline": True,
    }


def _try_nl2sql(question: str) -> str:
    res = query_nl2sql(question)
    if not res.get("ok"):
        return ""
    cols = res.get("columns") or []
    rows = res.get("rows") or []
    lines = [
        "## 数据参谋 · NL2SQL 真实库查询",
        "",
        f"问题：{question}",
        f"来源：{res.get('source')} · 模式：{res.get('nl2sql_mode')} · 行数：{res.get('row_count', 0)}",
        "",
        f"```sql\n{res.get('sql') or ''}\n```",
        "",
        "| " + " | ".join(str(c) for c in cols) + " |" if cols else "",
        "| " + " | ".join(["---"] * len(cols)) + " |" if cols else "",
    ]
    for row in rows[:40]:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    if not cols:
        lines.append("```json")
        lines.append(json.dumps(res.get("raw"), ensure_ascii=False, indent=2)[:4000])
        lines.append("```")
    return "\n".join([x for x in lines if x is not None])


def run_data(goal: str, brief: str) -> str:
    question = (
        f"围绕「{goal}」相关的通信/信息化/AI 项目，按行业统计项目数量与中标金额合计"
    )
    # 更适合规则引擎的默认问句（演示更稳）
    demo_q = "各行业中标项目数量和金额合计"
    nl = _try_nl2sql(demo_q)
    if not nl:
        nl = _try_nl2sql(question)
    if nl:
        op_logger.log("agent_data", "NL2SQL 问数成功")
        return nl + f"\n\n> 任务指令：{brief}\n> 战役目标：{goal}\n"

    allow_mock = bool(load_config().get("demo_mode", {}).get("allow_mock_llm", False))
    status = llm_client.provider_status()
    if not status.get("providers"):
        if allow_mock:
            return (
                f"> ⚠️ NL2SQL 离线且无 LLM，以下为【结构演示】非真实库查询\n\n"
                f"# 市场洞察\n\n目标：{goal}\n\n- 政企数字化预算仍集中在信息化与智能应用\n"
                f"- 建议补数：运行 scripts/start_nl2sql_demo.bat 启动演示库\n\n指令：{brief}\n"
            )
        raise RuntimeError(
            "数据参谋：NL2SQL 离线且无 LLM provider。请运行 scripts/start_nl2sql_demo.bat 或配置 LLM。"
        )
    system = (
        "你是成军台「数据参谋」。NL2SQL 暂不可用时，给出【模拟市场洞察】并醒目标注非真实库查询。"
        "输出 Markdown：机会判断、可验证指标、建议补充的数据源。开头必须写「⚠️ 非真实库查询」。"
    )
    prompt = f"战役目标：{goal}\n任务：{brief}\n请输出标注了「非真实库查询」的市场洞察。"
    out = llm_client.call_llm(prompt, fallback="", system_prompt=system, temperature=0.4, thinking=False)
    if not out:
        llm_client.bump_fail()
        if allow_mock:
            return f"> ⚠️ 非真实库查询（mock）\n\n目标：{goal}\n"
        raise RuntimeError("数据参谋：LLM 调用失败")
    llm_client.bump_ok()
    op_logger.log("agent_data", "NL2SQL 离线，已用 LLM 洞察（已标注）", level="WARN")
    return f"> ⚠️ NL2SQL 离线，以下为模型生成的【非真实库查询】洞察\n\n{out}"
