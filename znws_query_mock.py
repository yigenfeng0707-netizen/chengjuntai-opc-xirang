# -*- coding: utf-8 -*-
"""
znws-query 业务数据后端
- 电信投标项目数据查询（PostgreSQL 或 SQLite，真实政采网数据）
- 提供 list / schema / nl2sql / log 四个接口
- 监听 8082 端口，对接 mcp_http_nl2sql_v3.py
- 鉴权 Token 从 config.yaml 读取（nl2sql_backend.api_token）
"""

import os
import re
import json
import hmac
import datetime
import sys
from flask import Flask, request, jsonify

# Unified DB layer
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import db as _db

# 复用内容工厂的统一 LLM 客户端（三 provider 级联 fallback）
_CF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_factory")
if _CF_DIR not in sys.path:
    sys.path.insert(0, _CF_DIR)
try:
    import llm_client

    _LLM_OK = True
except Exception:
    _LLM_OK = False

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = _db.DB_PATH
LOG_PATH = os.path.join(BASE_DIR, "logs", "backend.log")


# 从 config.yaml 读取 Token（与 MCP 服务共用同一配置），读不到则用默认值
def _load_token():
    try:
        import yaml

        cfg_path = os.path.join(_CF_DIR, "config.yaml")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("nl2sql_backend", {}).get("api_token") or os.environ.get(
            "NL2SQL_API_TOKEN", ""
        )
    except Exception:
        return os.environ.get("NL2SQL_API_TOKEN", "")


DEMO_TOKEN = _load_token()
DATASET_NAME = "bid_projects"

os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)


# ========== 鉴权中间件 ==========
@app.before_request
def auth_check():
    # 健康检查放行
    if request.path == "/health":
        return None
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    if not hmac.compare_digest(token, DEMO_TOKEN):
        return jsonify({"error": "鉴权失败：token 无效", "code": 401}), 401


def get_conn():
    """Get a DB connection. Use set_dict_mode(True) for named column access."""
    return _db.get_conn()


# ========== 数据库初始化 ==========
def init_db():
    conn = get_conn()
    conn.execute(_db.get_schema_ddl())
    cur = conn.execute("SELECT COUNT(*) FROM bid_projects")
    count = cur.fetchone()[0]
    conn.close()
    if count == 0:
        try:
            from seed_demo_db import ensure_demo_db

            info = ensure_demo_db(DB_PATH)
            print(
                f"[ok] 演示库已写入 {info.get('row_count')} 条样本（亦可 python fetch_real_data.py --full-rebuild）"
            )
        except Exception as ex:
            print(
                f"[警告] 数据库为空且自动种子失败: {ex}；请运行: python seed_demo_db.py"
            )


def write_backend_log(action, payload, result_summary):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {action} | input={json.dumps(payload, ensure_ascii=False)} | {result_summary}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# ========== NL2SQL 智能解析（真AI + 规则兜底）==========
# 表结构（CREATE TABLE 格式，对 NL2SQL 模型最友好）
SCHEMA_DDL = _db.SCHEMA_DDL_FOR_PROMPT


def _build_nl2sql_system_prompt():
    """构建 NL2SQL system prompt（含动态日期），通过 system 消息发送给 LLM"""
    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    half_year_ago = (today - datetime.timedelta(days=183)).strftime("%Y-%m-%d")
    last_year = str(today.year - 1)
    return f"""你是专业的 NL2SQL 引擎。根据用户的自然语言问题，生成 {_db.nl2sql_dialect_name()} 查询 SQL。

数据库表结构：
{SCHEMA_DDL}

今天日期：{today_str}

注意事项：
- "合同金额/成交金额/报价" 都指 win_amount 字段
- "采购方式/业务类型" 当作 industry 处理
- 问"哪些项目"是查明细行（不要 GROUP BY），问"各XX统计/对比"才用 GROUP BY
- "平均/avg" 用 AVG()，"总/合计/sum" 用 SUM()，"数量/多少/count" 用 COUNT()
- "最近半年" 指 bid_date >= '{half_year_ago}'
- "去年" 指 {_db.sql_extract_year("bid_date")} = '{last_year}'
- 金额单位万元，列别名用英文下划线

只生成 SELECT 语句，禁止 INSERT/UPDATE/DELETE/DROP。
直接返回 JSON（不要 markdown 代码块）：
{{"sql": "SELECT ...", "columns": ["中文列名1", "中文列名2"], "chart_type": "table|bar|line|pie"}}"""


def _llm_nl2sql(question: str, chart_type: str, user_id: str):
    """用真实 LLM 把自然语言转成 SQL；失败返回 None，由调用方走规则降级。
    核心策略：system/user 消息分离 + CREATE TABLE schema + 最强模型优先 + 开启推理思考"""
    if not _LLM_OK or not llm_client.is_llm_enabled():
        return None
    system_prompt = _build_nl2sql_system_prompt()
    user_msg = question
    if user_id:
        user_msg += f"\n（当前用户 {user_id}，只查该用户归属的数据：WHERE owner_user_id='{user_id}'）"
    if chart_type and chart_type != "table":
        user_msg += f"\n（用户指定图表：{chart_type}）"
    try:
        raw = llm_client.call_llm(
            user_msg,
            fallback="",
            max_tokens=8192,
            temperature=0.0,
            timeout=90,
            reverse_order=True,
            thinking=True,
            system_prompt=system_prompt,
        )
        if not raw:
            return None
        # 去掉可能的 markdown 包裹
        raw = raw.strip().strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        obj = json.loads(m.group())
        sql = obj.get("sql", "").strip()
        columns = obj.get("columns", [])
        ct = obj.get("chart_type", chart_type or "table")
        # 安全校验
        sql_lower = sql.lower()
        if any(
            kw in sql_lower
            for kw in [
                "insert",
                "update",
                "delete",
                "drop",
                "alter",
                "create",
                "attach",
                "pragma",
            ]
        ):
            write_backend_log(
                "llm_nl2sql_reject",
                {"question": question, "sql": sql},
                "SQL含危险关键词，拒绝",
            )
            return None
        if not sql_lower.startswith("select"):
            return None
        write_backend_log("llm_nl2sql_ok", {"question": question}, f"SQL={sql[:80]}")
        return {"sql": sql, "columns": columns, "chart_type": ct}
    except Exception as ex:
        write_backend_log("llm_nl2sql_fail", {"question": question}, str(ex)[:120])
        return None


# ========== 规则解析（LLM 失败时的降级兜底）==========
def parse_question_to_sql(question: str, chart_type: str = "table", user_id: str = ""):
    q = question.strip()
    ql = q.lower()

    # 选择聚合维度
    if any(k in q for k in ["金额", "中标金额", "总金额", "金额合计"]):
        metric_sql = "SUM(win_amount)"
        metric_name = "中标金额合计(万元)"
    elif any(k in q for k in ["数量", "多少", "几个", "总数", "项目数", "条数"]):
        metric_sql = "COUNT(*)"
        metric_name = "项目数量"
    elif any(k in q for k in ["平均", "均值"]):
        metric_sql = "AVG(win_amount)"
        metric_name = "中标金额均值(万元)"
    else:
        metric_sql = "COUNT(*)"
        metric_name = "项目数量"

    # 分组维度
    group_sql = ""
    group_col = ""
    if "按行业" in q or "各行业" in q or "行业分组" in q:
        group_sql = "industry"
        group_col = "行业"
    elif "按地区" in q or "各区域" in q or "各城市" in q or "地区" in q:
        group_sql = "region"
        group_col = "地区"
    elif "按月" in q or "月度" in q or "每个月" in q:
        group_sql = _db.sql_extract_year_month("bid_date")
        group_col = "月份"
    elif "按状态" in q or "各状态" in q:
        group_sql = "status"
        group_col = "状态"
    elif "按年份" in q or "各年" in q:
        group_sql = _db.sql_extract_year("bid_date")
        group_col = "年份"

    # 时间过滤
    where_time = ""
    today = datetime.date.today()
    if "本月" in q:
        where_time = (
            f"{_db.sql_extract_year_month('bid_date')}='{today.strftime('%Y-%m')}'"
        )
    elif "上月" in q or "上个月" in q:
        first = today.replace(day=1)
        last_month = (first - datetime.timedelta(days=1)).strftime("%Y-%m")
        where_time = f"{_db.sql_extract_year_month('bid_date')}='{last_month}'"
    elif "2026上半年" in q or "2026年上半年" in q:
        where_time = "bid_date>='2026-01-01' AND bid_date<='2026-06-30'"
    elif "2026下半年" in q or "2026年下半年" in q:
        where_time = "bid_date>='2026-07-01' AND bid_date<='2026-12-31'"
    elif "2025全年" in q or "2025年全年" in q:
        where_time = "bid_date>='2025-01-01' AND bid_date<='2025-12-31'"
    elif "2026全年" in q or "2026年全年" in q:
        where_time = "bid_date>='2026-01-01' AND bid_date<='2026-12-31'"
    elif re.search(r"20\d\d年", q):
        m = re.search(r"(20\d\d)年", q)
        where_time = f"{_db.sql_extract_year('bid_date')}='{m.group(1)}'"
    elif "去年同期" in q:
        where_time = f"bid_date>='{today.year - 1}-{today.month:02d}-01' AND bid_date<='{today.year - 1}-{today.month:02d}-28'"

    # 中标过滤
    where_win = ""
    if "中标" in q and ("未中标" not in q):
        where_win = "status='中标'"

    # 用户行级权限
    where_user = ""
    if user_id:
        where_user = f"owner_user_id='{user_id}'"

    where_parts = [p for p in [where_time, where_win, where_user] if p]
    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    if group_sql:
        sql = f"SELECT {group_sql} AS dim, {metric_sql} AS metric FROM bid_projects{where_clause} GROUP BY {group_sql} ORDER BY metric DESC"
        columns = [group_col, metric_name]
    else:
        sql = f"SELECT {metric_sql} AS metric FROM bid_projects{where_clause}"
        columns = [metric_name]

    return sql, columns, chart_type


# ========== API 接口 ==========
@app.route("/health")
def health():
    try:
        from fetch_real_data import db_stats

        stats = db_stats()
    except Exception:
        conn = get_conn()
        cnt = conn.execute("SELECT COUNT(*) FROM bid_projects").fetchone()[0]
        conn.close()
        stats = {
            "row_count": cnt,
            "real_count": None,
            "demo_count": None,
            "last_refresh": None,
        }
    return jsonify(
        {
            "status": "ok",
            "row_count": stats.get("row_count"),
            "real_count": stats.get("real_count"),
            "demo_count": stats.get("demo_count"),
            "last_refresh": stats.get("last_refresh") or stats.get("mtime"),
            "db_path": DB_PATH,
        }
    )


@app.route("/api/v1/dataset/list", methods=["GET"])
def dataset_list():
    conn = get_conn()
    cnt = conn.execute("SELECT COUNT(*) FROM bid_projects").fetchone()[0]
    conn.close()
    data = {
        "datasets": [
            {
                "name": DATASET_NAME,
                "description": "浙江政采网通信/信息化投标项目（优先真实；空库可演示种子）",
                "row_count": cnt,
                "owner": "real",
            }
        ]
    }
    write_backend_log("list_datasets", {}, f"返回{len(data['datasets'])}个数据集")
    return jsonify(data)


@app.route("/api/v1/dataset/schema", methods=["GET"])
def dataset_schema():
    ds = request.args.get("dataset_name", "")
    if ds != DATASET_NAME:
        return jsonify({"error": f"数据集不存在：{ds}"}), 404
    schema = {
        "dataset_name": DATASET_NAME,
        "description": "电信投标项目数据集",
        "fields": [
            {"name": "id", "type": "integer", "comment": "主键"},
            {"name": "project_name", "type": "string", "comment": "项目名称"},
            {
                "name": "industry",
                "type": "string",
                "comment": "行业（通信工程/政企信息化/云服务/网络安全/物联网/IDC数据中心）",
            },
            {
                "name": "region",
                "type": "string",
                "comment": "地区（杭州/宁波/温州等浙江地市）",
            },
            {"name": "bid_date", "type": "date", "comment": "投标日期 YYYY-MM-DD"},
            {"name": "win_amount", "type": "number", "comment": "中标金额（万元）"},
            {
                "name": "status",
                "type": "string",
                "comment": "状态（中标/未中标/进行中）",
            },
            {
                "name": "owner_user_id",
                "type": "string",
                "comment": "归属人员ID（行级权限）",
            },
        ],
        "metrics": [
            {"name": "中标金额合计", "expression": "SUM(win_amount)"},
            {"name": "项目数量", "expression": "COUNT(*)"},
            {"name": "平均金额", "expression": "AVG(win_amount)"},
        ],
        "dimensions": ["industry", "region", "status", "bid_date"],
    }
    write_backend_log("get_dataset_schema", {"dataset_name": ds}, "Schema正常")
    return jsonify(schema)


@app.route("/api/v1/query/nl2sql", methods=["POST"])
def query_nl2sql():
    body = request.get_json(force=True, silent=True) or {}
    question = body.get("question", "")
    chart_type = body.get("chart_type", "table")
    user_id = body.get("user_id", "")

    if not question:
        return jsonify({"error": "question 不能为空"}), 400

    # 先尝试真实 LLM 转 SQL（支持任意自然语言），失败走规则降级
    llm_result = _llm_nl2sql(question, chart_type, user_id)
    if llm_result:
        sql = llm_result["sql"]
        columns = llm_result["columns"]
        ct = llm_result["chart_type"]
        nl2sql_mode = "llm"
    else:
        sql, columns, ct = parse_question_to_sql(question, chart_type, user_id)
        nl2sql_mode = "rule"

    conn = _db.get_conn()
    try:
        rows_raw = conn.execute(sql).fetchall()
    except Exception as e:
        conn.close()
        return jsonify(
            {"error": f"SQL执行失败：{e}", "sql": sql, "nl2sql_mode": nl2sql_mode}
        ), 500
    conn.close()

    rows = [list(r) for r in rows_raw]
    result = {
        "sql": sql,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "chart_type": ct,
        "question": question,
        "user_id": user_id,
        "nl2sql_mode": nl2sql_mode,
    }
    write_backend_log(
        "intelligent_query",
        {"question": question, "user_id": user_id},
        f"返回{len(rows)}行, SQL={sql}",
    )
    return jsonify(result)


@app.route("/api/v1/query/log", methods=["GET"])
def query_log():
    limit = int(request.args.get("limit", 20))
    user_id = request.args.get("user_id", "")
    logs = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        # 逆序取最近 limit 条
        all_lines = all_lines[::-1][:limit]
        for i, line in enumerate(all_lines, 1):
            logs.append({"seq": i, "detail": line.strip()})
    if user_id:
        logs = [l for l in logs if user_id in l["detail"]]
    return jsonify({"logs": logs, "count": len(logs)})


if __name__ == "__main__":
    init_db()
    print(f"znws-query 后端启动中... 监听 127.0.0.1:8082，鉴权Token: {DEMO_TOKEN}")
    app.run(host="127.0.0.1", port=8082, debug=False)
