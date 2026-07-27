# -*- coding: utf-8 -*-
"""
模块3：BidAutoPipeline 标书系统双向联动
正向推送（内容工厂→标书系统）：行业标准导出，同步至 BidAutoPipeline 知识库目录，按行业标签分类
反向拉取（标书系统→内容工厂）：读取投标项目清单，识别赛道行业，自动生成垂直领域选题
核心函数：sync_knowledge_to_bid() / fetch_bid_project_themes()
"""
import os
import re
import json
import shutil
import datetime
from config_loader import KNOWLEDGE_DIR, load_config
import op_logger
import agents


def _bid_knowledge_root() -> str:
    cfg = load_config()
    return cfg.get("knowledge_sync_folder", "")


def _bid_project_list_path() -> str:
    """标书系统投标项目清单文件路径"""
    cfg = load_config()
    return os.path.join(cfg.get("bid_pipeline_root", ""), "projects", "project_list.json")


def sync_knowledge_to_bid() -> dict:
    """
    正向推送：将内容工厂已校验完成的调研报告/文稿同步至 BidAutoPipeline 知识库目录
    自动按行业标签分类
    """
    root = _bid_knowledge_root()
    articles = agents.list_articles()
    synced = []
    reviewed = [a for a in articles if a.get("review_pass")]

    op_logger.log("bid_sync", f"开始正向推送，待同步稿件{len(reviewed)}篇")

    if not root or not os.path.isdir(os.path.dirname(root)):
        # BidAutoPipeline 目录不存在，降级同步到本地 knowledge 目录
        root = KNOWLEDGE_DIR
        op_logger.log("bid_sync", "BidAutoPipeline 目录缺失，降级同步至本地 knowledge/", level="WARN")

    os.makedirs(root, exist_ok=True)

    for a in reviewed:
        src = os.path.join(os.path.dirname(__file__), "articles", a["file"])
        if not os.path.exists(src):
            continue
        # 按标签分类目录
        tag = a["tags"][0] if a.get("tags") else "未分类"
        tag_safe = re.sub(r"[\\/:*?\"<>|]", "_", tag)
        dst_dir = os.path.join(root, tag_safe)
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, a["file"])
        shutil.copy2(src, dst)
        # 生成摘要索引
        index_file = os.path.join(dst_dir, "index.json")
        idx = []
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    idx = json.load(f)
            except Exception:
                idx = []
        idx.append({"id": a["id"], "title": a["title"], "summary": a.get("summary", ""),
                    "ts": datetime.datetime.now().isoformat()})
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
        synced.append({"id": a["id"], "title": a["title"], "category": tag_safe})

    # 同步向量索引
    try:
        vec_src = os.path.join(os.path.dirname(__file__), "vector_db")
        cfg = load_config()
        vec_dst = cfg.get("vector_sync_path", "")
        if vec_dst and os.path.isdir(os.path.dirname(vec_dst)):
            os.makedirs(vec_dst, exist_ok=True)
            for fn in ["vectors.pkl", "meta.json"]:
                s = os.path.join(vec_src, fn)
                if os.path.exists(s):
                    shutil.copy2(s, os.path.join(vec_dst, fn))
            op_logger.log("bid_sync", "向量索引已同步至标书系统")
    except Exception as ex:
        op_logger.log("bid_sync", f"向量同步失败(可忽略): {ex}", level="WARN")

    op_logger.log("bid_sync", f"正向推送完成，同步{len(synced)}篇，目标:{root}")
    return {"synced_count": len(synced), "target": root, "items": synced}


def fetch_bid_project_themes() -> dict:
    """
    反向拉取：读取 BidAutoPipeline 投标项目清单，识别赛道行业，自动生成垂直领域选题
    缺失清单文件时，联动 NL2SQL 查询投标项目历史，提取热门行业作为选题方向
    """
    list_path = _bid_project_list_path()
    themes = []

    if os.path.exists(list_path):
        try:
            with open(list_path, "r", encoding="utf-8") as f:
                projects = json.load(f)
            ind_count = {}
            for p in projects:
                ind = p.get("industry") or p.get("赛道") or "未分类"
                ind_count[ind] = ind_count.get(ind, 0) + 1
            themes = sorted(ind_count.items(), key=lambda x: x[1], reverse=True)
            op_logger.log("bid_fetch", f"读取标书项目清单{len(projects)}个，识别赛道{len(themes)}个")
        except Exception as ex:
            op_logger.log("bid_fetch", f"读取项目清单失败: {ex}", level="WARN")

    if not themes:
        # 降级：联动 NL2SQL 查询投标历史热门行业
        try:
            import data_feedback
            r = data_feedback.analyze_topic_data_with_nl2sql()
            hot = r.get("bid_stats", {}).get("hot_industries", [])
            themes = [(h["industry"], h["amount"]) for h in hot]
            op_logger.log("bid_fetch", f"清单缺失，NL2SQL联动提取热门行业{len(themes)}个")
        except Exception as ex:
            op_logger.log("bid_fetch", f"NL2SQL联动失败: {ex}", level="WARN")

    # 生成垂直领域选题
    suggestions = []
    for ind, cnt in themes[:6]:
        suggestions.append({"industry": ind, "topic": f"{ind}领域投标项目技术方案与中标趋势分析",
                            "signal": cnt})
    op_logger.log("bid_fetch", f"生成垂直领域选题{len(suggestions)}个")
    return {"themes": [{"industry": ind, "count": cnt} for ind, cnt in themes],
            "topic_suggestions": suggestions}
