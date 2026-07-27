# -*- coding: utf-8 -*-
"""
第一层：选题采集层
1. 批量 RSS 资讯源抓取（配置为空时使用内置示例源，离线可跑通）
2. 资讯清洗、摘要提取、去重
3. LLM 多维度打分：受众价值、实操落地性、竞品稀缺度、流量潜力
4. 输出候选选题 topics.json，支持人工标记选用/废弃
"""
import os
import json
import hashlib
import datetime
from config_loader import DATA_DIR, load_config
from task_retry import retry
import vector_store
import op_logger
import llm_client
import data_feedback

TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")

# 内置示例资讯源（无外网或未配置 RSS 时使用，保证流水线可跑通）
DEMO_FEED = [
    {"title": "MCP协议将重塑企业AI智能体开发范式", "link": "demo://1",
     "summary": "模型上下文协议MCP正成为大模型连接外部工具的标准方案，降低集成成本。", "source": "示例源"},
    {"title": "RAG+向量检索在政企知识库的落地实践", "link": "demo://2",
     "summary": "检索增强生成结合本地向量库，解决企业知识问答幻觉问题，实操性强。", "source": "示例源"},
    {"title": "NL2SQL智能问数在电信投标业务的量化收益", "link": "demo://3",
     "summary": "自然语言转SQL将投标数据查询效率提升8倍，行业案例稀缺，流量潜力大。", "source": "示例源"},
    {"title": "AI内容工厂自动化生产流水线设计", "link": "demo://4",
     "summary": "四层架构实现选题到发布全自动化，多Agent协作，竞品少，实操性强。", "source": "示例源"},
    {"title": "Docker容器化部署AI应用的避坑指南", "link": "demo://5",
     "summary": "容器化部署AI应用的关键配置与常见故障排查，受众价值高落地性强。", "source": "示例源"},
    {"title": "定时任务调度在数据回流闭环中的应用", "link": "demo://6",
     "summary": "基于定时调度实现数据回流与选题优化闭环，流量稳定落地性强。", "source": "示例源"},
]


def _fetch_rss():
    """抓取 RSS 源，失败/为空时降级为内置示例源"""
    cfg = load_config()
    sources = cfg.get("rss_sources", []) or []
    items = []
    if sources:
        try:
            import feedparser
            for url in sources:
                try:
                    feed = feedparser.parse(url)
                    for e in feed.entries[:10]:
                        items.append({
                            "title": e.get("title", ""),
                            "link": e.get("link", ""),
                            "summary": (e.get("summary", "") or "")[:300],
                            "source": url
                        })
                except Exception as ex:
                    op_logger.log("topic_fetch", f"RSS源抓取失败 {url}: {ex}", level="WARN")
        except ImportError:
            op_logger.log("topic_fetch", "feedparser 未安装，使用内置示例源", level="WARN")
    if not items:
        op_logger.log("topic_fetch", f"使用内置示例源({len(DEMO_FEED)}条)", level="INFO")
        items = list(DEMO_FEED)
    return items


def _dedup(items):
    seen = set()
    out = []
    for it in items:
        h = hashlib.md5(it["title"].encode("utf-8")).hexdigest()
        if h not in seen:
            seen.add(h)
            out.append(it)
    return out


def _llm_score(topic: str, summary: str):
    """LLM 多维度打分；未配置 LLM 或调用失败时用规则评分降级
    4个LLM维度(受众价值/实操落地性/竞品稀缺度/流量潜力) + 1个数据维度(市场热度)
    市场热度来自NL2SQL投标历史数据，0~10分，反映该方向真实采购市场活跃度
    """
    scores = {"受众价值": 5, "实操落地性": 5, "竞品稀缺度": 5, "流量潜力": 5}

    if llm_client.is_llm_enabled():
        prompt = (f"对以下选题按4个维度打分(1-10):受众价值、实操落地性、竞品稀缺度、流量潜力。\n"
                  f"选题:{topic}\n摘要:{summary}\n只返回4个数字逗号分隔，不要其它文字。")
        try:
            raw = llm_client.call_llm(prompt, fallback="", max_tokens=600, temperature=0.2, timeout=60)
            import re
            nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", raw)][:4]
            if len(nums) >= 4:
                scores = {"受众价值": nums[0], "实操落地性": nums[1],
                          "竞品稀缺度": nums[2], "流量潜力": nums[3]}
            else:
                op_logger.log("topic_score",
                              f"LLM打分解析失败(返回非4个数字)，降级规则: {raw[:80]}",
                              level="WARN")
        except Exception as ex:
            op_logger.log("topic_score", f"LLM打分失败降级规则: {ex}", level="WARN")
    else:
        # 规则降级评分：基于关键词
        kw_value = ["实战", "落地", "收益", "效率", "指南"]
        kw_practice = ["代码", "步骤", "配置", "部署", "流程"]
        kw_rare = ["MCP", "NL2SQL", "内容工厂", "数据回流", "标书"]
        kw_traffic = ["AI", "智能体", "RAG", "向量", "Docker"]
        s = summary + topic
        scores = {
            "受众价值": sum(2 for k in kw_value if k in s) + 4,
            "实操落地性": sum(2 for k in kw_practice if k in s) + 3,
            "竞品稀缺度": sum(3 for k in kw_rare if k in s) + 3,
            "流量潜力": sum(2 for k in kw_traffic if k in s) + 4,
        }

    # 第5维：市场热度（来自NL2SQL投标历史数据）
    try:
        boost = data_feedback.suggest_topic_boost(topic, summary)
        # boost 范围0~3，映射到0~10分制
        scores["市场热度"] = round(boost * 10 / 3, 1)
    except Exception:
        scores["市场热度"] = 0.0

    return scores


def collect_topics(topk: int = 6) -> dict:
    """采集并生成候选选题，输出 topics.json"""
    @retry("collect_topics")
    def _do():
        raw = _fetch_rss()
        items = _dedup(raw)
        op_logger.log("topic_collect", f"采集去重后{len(items)}条资讯")
        ranked = []
        for it in items:
            scores = _llm_score(it["title"], it["summary"])
            total = sum(scores.values())
            ranked.append({
                "id": hashlib.md5(it["title"].encode()).hexdigest()[:10],
                "title": it["title"],
                "summary": it["summary"],
                "source": it["source"],
                "scores": scores,
                "total_score": round(total, 1),
                "status": "candidate",  # candidate / selected / discarded
                "created_at": datetime.datetime.now().isoformat()
            })
        ranked.sort(key=lambda x: x["total_score"], reverse=True)
        top = ranked[:topk]
        # 追加到历史
        history = []
        if os.path.exists(TOPICS_FILE):
            with open(TOPICS_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        history.extend(top)
        with open(TOPICS_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        op_logger.log("topic_collect", f"生成候选选题{len(top)}条，已写入 topics.json")
        return {"count": len(top), "topics": top}
    return _do()


def load_topics():
    if os.path.exists(TOPICS_FILE):
        with open(TOPICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def mark_topic(topic_id: str, status: str):
    """人工标记选题 选用/废弃"""
    topics = load_topics()
    for t in topics:
        if t["id"] == topic_id:
            t["status"] = status
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    r = collect_topics(topk=6)
    print(json.dumps(r, ensure_ascii=False, indent=2))
