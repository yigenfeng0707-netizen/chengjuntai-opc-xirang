# -*- coding: utf-8 -*-
"""
第四层：数据回流闭环层
1. 每篇文章绑定唯一ID、标签、创建时间（已在 articles.py 实现）
2. 预留外部数据导入入口（阅读量、转发数据）
3. 基于历史数据统计优质选题特征，反向优化选题打分策略
   —— 调用本仓库根目录的 NL2SQL MCP 服务，查询投标项目历史中标数据，
      结合内容工厂自身选题表现，输出选题优化建议
4. 提供 get_bid_insights() 供 topic_collector 选题打分加用
"""
import os
import json
import time
import datetime
import requests
from config_loader import DATA_DIR, ARTICLES_DIR, load_config
import op_logger

FEEDBACK_FILE = os.path.join(DATA_DIR, "feedback.json")
EXTERNAL_DATA_FILE = os.path.join(DATA_DIR, "external_metrics.json")
INSIGHTS_CACHE_FILE = os.path.join(DATA_DIR, "bid_insights_cache.json")
_INSIGHTS_CACHE = None
_INSIGHTS_CACHE_TS = 0
_CACHE_TTL = 600  # 10分钟缓存


def import_external_metrics(metrics: list):
    """
    预留外部数据导入入口
    metrics: [{"article_id": "ART...", "reads": 1234, "shares": 56, "likes": 78}]
    """
    data = []
    if os.path.exists(EXTERNAL_DATA_FILE):
        with open(EXTERNAL_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.extend(metrics)
    with open(EXTERNAL_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    op_logger.log("data_feedback", f"导入外部指标{len(metrics)}条")


def _call_nl2sql(question: str, user_id: str = "") -> dict:
    """
    调用 NL2SQL MCP 服务查询投标项目历史数据
    返回后端API完整响应: {columns, rows, row_count, sql, nl2sql_mode}
    """
    cfg = load_config()
    url = cfg.get("nl2sql_mcp_url", "http://127.0.0.1:8765/mcp")
    body = {"type": "call_tool", "name": "intelligent_query",
            "parameters": {"question": question, "user_id": user_id}}
    r = requests.post(url, json=body, timeout=60)
    resp = r.json()
    # MCP响应格式: {"type": "tool_result", "result": {...}}
    return resp.get("result", resp)


def _call_nl2sql_safe(question: str, tag: str = "") -> list:
    """
    安全调用NL2SQL，失败返回空列表，不抛异常
    tag: 日志标识
    """
    try:
        result = _call_nl2sql(question)
        if "error" in result:
            op_logger.log("data_feedback", f"NL2SQL[{tag}]返回错误: {result['error']}", level="WARN")
            return []
        rows = result.get("rows", [])
        op_logger.log("data_feedback", f"NL2SQL[{tag}]返回{len(rows)}行")
        return rows
    except Exception as ex:
        op_logger.log("data_feedback", f"NL2SQL[{tag}]查询失败: {ex}", level="WARN")
        return []


def get_bid_insights(force_refresh: bool = False) -> dict:
    """
    获取投标项目多维洞察数据（带缓存）
    供 topic_collector 和 analyze_topic_data_with_nl2sql 共用

    返回:
    {
        "hot_industries": [{"industry": "政企信息化", "amount": 10905.3, "count": 15}, ...],
        "hot_regions": [{"region": "杭州", "count": 8, "amount": 2000}, ...],
        "status_dist": {"中标": 23, "进行中": 27},
        "top_projects": [{"name": "xxx", "amount": 7200}, ...],
        "avg_amount": 450.5,
        "total_count": 50,
        "ts": "2026-07-27T..."
    }
    """
    global _INSIGHTS_CACHE, _INSIGHTS_CACHE_TS

    now = time.time()
    if not force_refresh and _INSIGHTS_CACHE and (now - _INSIGHTS_CACHE_TS) < _CACHE_TTL:
        return _INSIGHTS_CACHE

    # 尝试从磁盘缓存加载
    if not force_refresh and os.path.exists(INSIGHTS_CACHE_FILE):
        try:
            with open(INSIGHTS_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if cached and (now - cached.get("_ts", 0)) < _CACHE_TTL:
                    _INSIGHTS_CACHE = cached
                    _INSIGHTS_CACHE_TS = cached["_ts"]
                    return cached
        except Exception:
            pass

    op_logger.log("data_feedback", "开始采集投标多维洞察数据...")

    insights = {
        "hot_industries": [],
        "hot_regions": [],
        "status_dist": {},
        "top_projects": [],
        "avg_amount": 0,
        "total_count": 0,
        "ts": datetime.datetime.now().isoformat(),
    }

    # ① 行业×金额（哪些行业中标金额最高）
    rows = _call_nl2sql_safe("各行业的总金额是多少", "行业金额")
    for r in rows:
        if len(r) >= 2:
            insights["hot_industries"].append({
                "industry": str(r[0]),
                "amount": float(r[1]) if r[1] else 0,
            })
    insights["hot_industries"].sort(key=lambda x: x["amount"], reverse=True)

    # ② 行业×项目数（哪些行业项目最多）
    rows = _call_nl2sql_safe("各行业有多少个项目", "行业数量")
    industry_counts = {}
    for r in rows:
        if len(r) >= 2:
            industry_counts[str(r[0])] = int(r[1]) if r[1] else 0

    # 合并到 hot_industries
    for item in insights["hot_industries"]:
        item["count"] = industry_counts.get(item["industry"], 0)

    # ③ 地区×项目数（哪些地区项目集中）
    rows = _call_nl2sql_safe("各城市有多少个项目", "地区数量")
    for r in rows:
        if len(r) >= 2:
            insights["hot_regions"].append({
                "region": str(r[0]),
                "count": int(r[1]) if r[1] else 0,
            })
    insights["hot_regions"].sort(key=lambda x: x["count"], reverse=True)

    # ④ 状态分布（中标/进行中比例）
    rows = _call_nl2sql_safe("中标和进行中的项目各有多少", "状态分布")
    for r in rows:
        if len(r) >= 2:
            insights["status_dist"][str(r[0])] = int(r[1]) if r[1] else 0

    # ⑤ 金额TOP5项目
    rows = _call_nl2sql_safe("金额最大的5个项目", "TOP5")
    for r in rows:
        if len(r) >= 2:
            insights["top_projects"].append({
                "name": str(r[0]),
                "amount": float(r[1]) if r[1] else 0,
            })

    # ⑥ 汇总统计
    total_count = sum(insights["status_dist"].values())
    total_amount = sum(i["amount"] for i in insights["hot_industries"])
    insights["total_count"] = total_count
    insights["avg_amount"] = round(total_amount / total_count, 2) if total_count else 0

    # 写入缓存
    insights["_ts"] = now
    _INSIGHTS_CACHE = insights
    _INSIGHTS_CACHE_TS = now
    try:
        with open(INSIGHTS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(insights, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    op_logger.log("data_feedback", f"洞察采集完成: {total_count}个项目, "
                   f"{len(insights['hot_industries'])}个行业, "
                   f"{len(insights['hot_regions'])}个地区")
    return insights


def suggest_topic_boost(topic: str, summary: str = "") -> float:
    """
    根据投标历史数据，为选题返回加成系数(0.0~3.0)
    topic_collector 调用此函数，在 base_score 上叠加市场热度分

    逻辑：
    - 遍历 hot_industries，选题标题/摘要命中热门行业关键词 → 加分
    - 热门行业金额越高、项目越多 → 加分越大
    - 缓存命中、NL2SQL离线时返回0（不影响正常打分）
    """
    # 行业名 -> 匹配关键词（与 fetch_real_data.py 的分类对应）
    INDUSTRY_MATCH = {
        "通信工程": ["通信", "光纤", "光缆", "宽带", "基站", "5g", "电信", "弱电", "综合布线"],
        "政企信息化": ["信息化", "信息系统", "数字化", "电子政务", "数字政府", "政务云",
                   "管理平台", "业务系统", "应用系统", "软件开发", "系统集成", "大数据",
                   "智能化", "运维", "维保", "oa", "erp", "审批"],
        "云服务": ["云平台", "云计算", "云服务", "云资源", "云主机", "云存储", "云迁移"],
        "网络安全": ["网络安全", "信息安全", "安全设备", "防火墙", "等级保护", "等保",
                  "密评", "安全审计", "数据安全", "密码"],
        "物联网": ["物联网", "传感器", "rfid", "智能感知", "nb-iot"],
        "IDC数据中心": ["数据中心", "idc", "机房", "服务器", "存储", "机柜", "ups", "微模块",
                    "动环", "算力", "智算"],
        "智慧城市": ["智慧", "视频监控", "安防", "监控", "智能交通", "智慧停车",
                   "城市大脑", "智慧城管", "智慧社区", "数字孪生"],
        "视频会议": ["视频会议", "融合通信", "指挥调度", "会议系统", "录播", "大屏",
                   "音视频", "led"],
        "智慧教育": ["智慧校园", "教育信息化", "在线教育", "智慧课堂", "教育云", "教育"],
        "智慧医疗": ["智慧医疗", "远程医疗", "医院信息化", "电子病历", "智慧医院",
                   "互联网医院", "医疗"],
        "数字乡村": ["数字乡村", "农村信息化", "智慧农业", "乡村振兴"],
        "融媒体": ["融媒体", "广电", "数字电视", "广播电视", "应急广播"],
        "人工智能": ["人工智能", "ai", "机器学习", "深度学习", "大模型", "智能算法",
                   "知识图谱", "nlp", "aigc", "智能体"],
        "区块链": ["区块链", "电子证照", "电子印章", "电子合同"],
    }

    try:
        insights = get_bid_insights()
    except Exception:
        return 0.0

    if not insights.get("hot_industries"):
        return 0.0

    text = (topic + " " + summary).lower()
    boost = 0.0

    for item in insights["hot_industries"][:5]:
        industry = item["industry"]
        # 用行业关键词做匹配
        keywords = INDUSTRY_MATCH.get(industry, [industry.lower()])
        matched = any(kw in text for kw in keywords)
        if matched:
            # 金额越大加分越高（1000万→1分, 5000万→2分, 10000万→3分，封顶3分）
            amount = item.get("amount", 0)
            count = item.get("count", 0)
            amount_boost = min(amount / 1000, 3.0)
            count_boost = min(count / 10, 1.0)
            boost = max(boost, amount_boost * 0.7 + count_boost * 0.3)

    return round(boost, 2)


def analyze_topic_data_with_nl2sql() -> dict:
    """
    基于历史数据统计优质选题特征，反向优化选题打分策略
    融合两个数据源：
      ① 内容工厂自身文章表现（标题/标签/外部指标）
      ② NL2SQL 查询投标项目历史中标数据（哪些行业/赛道中标金额高）
    输出选题优化建议
    """
    op_logger.log("data_feedback", "启动数据回流分析（联动NL2SQL投标历史）")
    result = {"article_stats": {}, "bid_stats": {}, "optimization": []}

    # ① 内容工厂文章统计
    import agents as _agents
    articles = _agents.list_articles()
    tag_count = {}
    for a in articles:
        for t in a.get("tags", []):
            tag_count[t] = tag_count.get(t, 0) + 1
    result["article_stats"] = {"total": len(articles), "tag_distribution": tag_count}

    # ② NL2SQL 多维洞察
    insights = get_bid_insights()
    bid_stats = {
        "hot_industries": [{"industry": i["industry"], "amount": i["amount"],
                            "count": i.get("count", 0)}
                           for i in insights.get("hot_industries", [])],
        "hot_regions": insights.get("hot_regions", []),
        "status_dist": insights.get("status_dist", {}),
        "top_projects": insights.get("top_projects", []),
        "avg_amount": insights.get("avg_amount", 0),
        "total_count": insights.get("total_count", 0),
        "source": "NL2SQL(bid_projects)",
    }
    result["bid_stats"] = bid_stats

    # ③ 反向优化建议
    suggestions = []
    if bid_stats.get("hot_industries"):
        top3 = bid_stats["hot_industries"][:3]
        for ind in top3:
            suggestions.append(
                f"行业[{ind['industry']}]中标金额{ind['amount']}万、"
                f"项目{ind.get('count', 0)}个，建议增加该方向选题权重"
            )
    if bid_stats.get("hot_regions"):
        top_region = bid_stats["hot_regions"][0]
        suggestions.append(
            f"地区[{top_region['region']}]项目数{top_region['count']}个，"
            f"建议增加该地区市场选题覆盖"
        )
    if bid_stats.get("avg_amount", 0) > 0:
        suggestions.append(
            f"平均项目金额{bid_stats['avg_amount']}万，"
            f"高金额项目选题可吸引高价值读者群体"
        )
    if tag_count:
        hot_tag = max(tag_count, key=tag_count.get)
        suggestions.append(f"内容工厂产出最多的标签[{hot_tag}]，可深化系列化选题")
    suggestions.append("建议将NL2SQL返回的热门行业纳入选题打分'流量潜力'维度加权")
    result["optimization"] = suggestions

    # 持久化
    fb = []
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            fb = json.load(f)
    fb.append({"ts": datetime.datetime.now().isoformat(), "result": result})
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(fb, f, ensure_ascii=False, indent=2)

    op_logger.log("data_feedback", f"数据回流分析完成，生成{len(suggestions)}条优化建议")
    return result


def get_feedback_history():
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


if __name__ == "__main__":
    print("=== 投标多维洞察 ===")
    r = get_bid_insights()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print("\n=== 选题加成测试 ===")
    for t in ["5G基站建设技术方案", "政务云迁移实践", "幼儿园装修", "智慧医疗远程问诊"]:
        b = suggest_topic_boost(t)
        print(f"  {t}: +{b}")
