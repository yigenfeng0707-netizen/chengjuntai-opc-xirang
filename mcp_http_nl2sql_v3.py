import json
import requests
import time
import os
import sys
from aiohttp import web
from typing import Dict, Any
from cachetools import TTLCache
from logger_config import logger

# ========== 从 content_factory/config.yaml 读取配置（避免硬编码）==========
_CF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_factory")
if _CF_DIR not in sys.path:
    sys.path.insert(0, _CF_DIR)

def _load_nl2sql_config():
    """读取 config.yaml 中 nl2sql_backend 段；读不到则用安全默认值"""
    try:
        import yaml
        cfg_path = os.path.join(_CF_DIR, "config.yaml")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("nl2sql_backend", {})
    except Exception:
        return {}

_nl2sql_cfg = _load_nl2sql_config()

ZNWS_QUERY_URL = _nl2sql_cfg.get("znws_query_url", "http://127.0.0.1:8082/api/v1")
API_TOKEN = _nl2sql_cfg.get("api_token", "demo-token-2026")
SERVER_HOST = _nl2sql_cfg.get("mcp_host", "127.0.0.1")
SERVER_PORT = int(_nl2sql_cfg.get("mcp_port", 8765))
CACHE_TTL = int(_nl2sql_cfg.get("cache_ttl", 300))
MAX_CACHE_SIZE = 200
# ==========================================

HEADERS_BASE = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

query_cache = TTLCache(maxsize=MAX_CACHE_SIZE, ttl=CACHE_TTL)

tools_def = [
    {
        "name": "list_datasets",
        "description": "获取全部业务数据集列表",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_dataset_schema",
        "description": "查询指定数据集语义结构、字段、指标、业务说明",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_name": {"type": "string", "description": "数据集名称"}
            },
            "required": ["dataset_name"]
        }
    },
    {
        "name": "intelligent_query",
        "description": "自然语言智能问数主入口，返回表格数据、图表配置，支持行级权限",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "用户自然语言查询语句"},
                "dataset_name": {"type": "string", "description": "指定数据集，可选"},
                "chart_type": {"type": "string", "description": "可选：table/bar/line/pie"},
                "user_id": {"type": "string", "description": "操作人员ID，用于行级权限过滤"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "get_query_logs",
        "description": "查询历史审计日志，支持按操作人员权限隔离",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "user_id": {"type": "string", "description": "操作人员ID，权限隔离"}
            }
        }
    }
]

def get_cache_key(tool_name: str, params: dict) -> str:
    raw = f"{tool_name}_{json.dumps(params, sort_keys=True)}"
    return raw

async def handle_message(request: web.Request):
    try:
        body = await request.json()
        logger.info(f"收到MCP请求：{body}")
        msg_type = body.get("type")

        if msg_type == "list_tools":
            return web.json_response({
                "type": "tools",
                "tools": tools_def
            })

        elif msg_type == "call_tool":
            tool_name = body.get("name")
            params = body.get("parameters", {})
            cache_key = get_cache_key(tool_name, params)

            if tool_name == "intelligent_query" and cache_key in query_cache:
                logger.info(f"缓存命中：{cache_key}")
                return web.json_response({
                    "type": "tool_result",
                    "result": query_cache[cache_key],
                    "cache": "hit"
                })

            result = await call_znws_api(tool_name, params)
            if tool_name == "intelligent_query" and "error" not in result:
                query_cache[cache_key] = result
                logger.info(f"缓存写入成功：{cache_key}")

            logger.info(f"工具调用完成：{tool_name}")
            return web.json_response({
                "type": "tool_result",
                "result": result
            })
        else:
            return web.json_response({"error": "未知消息类型"}, status=400)
    except Exception as e:
        logger.error(f"请求异常：{str(e)}")
        return web.json_response({"error": str(e)}, status=500)

async def call_znws_api(name: str, params: Dict[str, Any]):
    headers = HEADERS_BASE.copy()
    if "user_id" in params and params["user_id"]:
        headers["X-User-ID"] = params["user_id"]
        logger.info(f"权限透传 user_id：{params['user_id']}")

    try:
        if name == "list_datasets":
            resp = requests.get(f"{ZNWS_QUERY_URL}/dataset/list", headers=headers, timeout=30)
            return resp.json()
        elif name == "get_dataset_schema":
            ds = params["dataset_name"]
            resp = requests.get(f"{ZNWS_QUERY_URL}/dataset/schema?dataset_name={ds}", headers=headers, timeout=30)
            return resp.json()
        elif name == "intelligent_query":
            payload = {
                "question": params["question"],
                "dataset_name": params.get("dataset_name", ""),
                "chart_type": params.get("chart_type", "table"),
                "user_id": params.get("user_id", "")
            }
            resp = requests.post(f"{ZNWS_QUERY_URL}/query/nl2sql", json=payload, headers=headers, timeout=60)
            return resp.json()
        elif name == "get_query_logs":
            limit = params.get("limit", 20)
            user_id = params.get("user_id","")
            url = f"{ZNWS_QUERY_URL}/query/log?limit={limit}"
            if user_id:
                url += f"&user_id={user_id}"
            resp = requests.get(url, headers=headers, timeout=30)
            return resp.json()
        else:
            return {"error": "不存在该工具"}
    except Exception as e:
        logger.error(f"后端接口调用失败：{str(e)}")
        return {"error": f"后端接口调用失败：{str(e)}"}

async def main():
    import asyncio
    app = web.Application()
    app.add_routes([web.post("/mcp", handle_message)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, SERVER_HOST, SERVER_PORT)
    await site.start()
    logger.info(f"【生产版MCP服务启动成功】 http://{SERVER_HOST}:{SERVER_PORT}/mcp")
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
