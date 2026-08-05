# -*- coding: utf-8 -*-
"""
BidAutoPipeline 标书系统双向联动（成军台内嵌版）

正向：过审稿件 / 战役产物 → 知识库（本地 knowledge/ 或 bid_pipeline_root）
反向：投标项目赛道 → 选题建议 → 可写入选题池 / 一键发起获客·综述战役
路径优先级：
  1) bid_telecom.db 有行 → SQL 真实/缓存标讯（优先 owner_user_id=real）
  2) bid_pipeline_root/projects/project_list.json 或本地 bid_projects.json
  3) 冷启动 seed 演示 JSON（醒目标注本地回退）
"""

from __future__ import annotations

import os
import re
import json
import shutil
import hashlib
import datetime
import sys
from typing import Optional, List

from config_loader import KNOWLEDGE_DIR, DATA_DIR, ROOT, load_config
import op_logger
import agents

REPO_ROOT = os.path.dirname(ROOT)
TELECOM_DB = os.path.join(REPO_ROOT, "bid_telecom.db")

# Unified DB layer
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
import db as _db

DEMO_BID_PROJECTS = [
    {
        "id": "BID_ZJ_001",
        "name": "杭州电信政企云网融合专线扩容项目",
        "industry": "云网融合",
        "赛道": "云网融合",
        "region": "杭州",
        "owner": "浙江电信政企",
        "budget_wan": 1280,
        "status": "招标中",
        "deadline": "2026-08-20",
        "keywords": ["专线", "SD-WAN", "云网", "政企"],
        "summary": "面向杭州重点政企客户的云网融合专线扩容与统一运维能力建设。",
    },
    {
        "id": "BID_ZJ_002",
        "name": "宁波市智慧城市5G专网建设采购",
        "industry": "5G专网",
        "赛道": "5G专网",
        "region": "宁波",
        "owner": "宁波智慧城市运营中心",
        "budget_wan": 2100,
        "status": "资格预审",
        "deadline": "2026-09-05",
        "keywords": ["5G", "专网", "智慧城市", "切片"],
        "summary": "宁波智慧城市场景下 5G 专网覆盖、切片与行业应用对接。",
    },
    {
        "id": "BID_ZJ_003",
        "name": "温州数字政府一体化平台运维服务",
        "industry": "数字政府",
        "赛道": "数字政府",
        "region": "温州",
        "owner": "温州市大数据局",
        "budget_wan": 680,
        "status": "招标中",
        "deadline": "2026-08-28",
        "keywords": ["数字政府", "一网通办", "运维", "等保"],
        "summary": "数字政府一体化平台运维、安全加固与持续迭代服务。",
    },
    {
        "id": "BID_ZJ_004",
        "name": "嘉兴物联网感知平台二期工程",
        "industry": "物联网",
        "赛道": "物联网",
        "region": "嘉兴",
        "owner": "嘉兴市经信局",
        "budget_wan": 420,
        "status": "公告发布",
        "deadline": "2026-09-15",
        "keywords": ["物联网", "感知", "平台", "边缘计算"],
        "summary": "城市级物联网感知平台扩容，含边缘节点与数据汇聚能力。",
    },
    {
        "id": "BID_ZJ_005",
        "name": "金华IDC算力调度中心设备与软件采购",
        "industry": "IDC算力",
        "赛道": "IDC算力",
        "region": "金华",
        "owner": "金华电信云网中心",
        "budget_wan": 1560,
        "status": "招标中",
        "deadline": "2026-10-01",
        "keywords": ["IDC", "算力", "调度", "息壤"],
        "summary": "IDC 算力资源池扩容与统一调度平台软件采购，对接息壤算力能力。",
    },
]


def _bid_root() -> str:
    cfg = load_config()
    return (cfg.get("bid_pipeline_root") or "").strip()


def telecom_db_path() -> str:
    return TELECOM_DB


def _db_stats() -> dict:
    """读取 bid_telecom.db 统计；优先复用 fetch_real_data.db_stats。"""
    try:
        import sys

        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from fetch_real_data import db_stats

        return db_stats(TELECOM_DB)
    except Exception:
        out = {
            "db_path": TELECOM_DB,
            "db_exists": os.path.exists(TELECOM_DB),
            "row_count": 0,
            "real_count": 0,
            "demo_count": 0,
            "mtime": None,
            "last_refresh": None,
            "last_ok": None,
            "last_error": None,
        }
        if not out["db_exists"]:
            return out
        try:
            conn = _db.get_conn()
            out["row_count"] = conn.execute(
                "SELECT COUNT(*) FROM bid_projects"
            ).fetchone()[0]
            out["real_count"] = conn.execute(
                "SELECT COUNT(*) FROM bid_projects WHERE owner_user_id=?", ("real",)
            ).fetchone()[0]
            out["demo_count"] = conn.execute(
                "SELECT COUNT(*) FROM bid_projects WHERE owner_user_id=?", ("demo",)
            ).fetchone()[0]
            conn.close()
            out["mtime"] = datetime.datetime.fromtimestamp(
                os.path.getmtime(TELECOM_DB)
            ).isoformat(timespec="seconds")
        except Exception as ex:
            out["last_error"] = str(ex)
        return out


def _row_to_project(row) -> dict:
    rid = row["id"]
    industry = row["industry"] or "未分类"
    region = row["region"] or ""
    name = row["project_name"] or f"项目{rid}"
    owner_tag = row["owner_user_id"] or ""
    return {
        "id": f"REAL_{rid}",
        "name": name,
        "industry": industry,
        "赛道": industry,
        "region": region,
        "owner": "浙江政采网"
        if owner_tag == "real"
        else ("演示库" if owner_tag == "demo" else owner_tag or "标讯库"),
        "budget_wan": row["win_amount"],
        "status": row["status"] or "",
        "deadline": row["bid_date"] or "",
        "keywords": [k for k in [industry, region] if k],
        "summary": f"{region} · {industry} · {row['bid_date'] or ''} · {row['status'] or ''}".strip(
            " ·"
        ),
        "source": "bid_telecom.db",
        "owner_user_id": owner_tag,
        "db_id": rid,
    }


def load_projects_from_db(limit: int = 80, prefer_real: bool = True) -> dict:
    """从 bid_telecom.db 加载项目；无行返回 empty。"""
    stats = _db_stats()
    if not stats.get("row_count"):
        return {
            "projects": [],
            "source": "empty_db",
            "count": 0,
            "db_stats": stats,
            "using_json_fallback": True,
        }
    try:
        conn = _db.get_conn()
        conn.set_dict_mode(True)
        if prefer_real and stats.get("real_count", 0) > 0:
            rows = conn.execute(
                "SELECT * FROM bid_projects WHERE owner_user_id=? "
                "ORDER BY bid_date DESC, id DESC LIMIT ?",
                ("real", limit),
            ).fetchall()
            source = "bid_telecom.db:real"
        else:
            rows = conn.execute(
                "SELECT * FROM bid_projects ORDER BY bid_date DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            source = "bid_telecom.db" + (
                ":demo" if stats.get("real_count", 0) == 0 else ""
            )
        conn.close()
        projects = [_row_to_project(r) for r in rows]
        return {
            "projects": projects,
            "source": source,
            "count": len(projects),
            "db_stats": stats,
            "using_json_fallback": False,
            "path": TELECOM_DB,
        }
    except Exception as ex:
        op_logger.log("bid_list", f"DB 读取失败: {ex}", level="WARN")
        return {
            "projects": [],
            "source": "db_error",
            "count": 0,
            "db_stats": stats,
            "error": str(ex),
            "using_json_fallback": True,
        }


def resolve_knowledge_root() -> str:
    """正向同步目标目录：配置路径可用则用之，否则本地 knowledge/。"""
    cfg = load_config()
    configured = (cfg.get("knowledge_sync_folder") or "").strip()
    if configured:
        parent = os.path.dirname(configured)
        if parent and os.path.isdir(parent):
            return configured
        if os.path.isdir(configured):
            return configured
    return KNOWLEDGE_DIR


def resolve_projects_path() -> str:
    """投标项目清单路径：bid_pipeline_root/projects/project_list.json 或本地 demo。"""
    root = _bid_root()
    if root:
        p = os.path.join(root, "projects", "project_list.json")
        if os.path.exists(p) or os.path.isdir(root):
            return p
    return os.path.join(DATA_DIR, "bid_projects.json")


def ensure_demo_projects(force: bool = False) -> dict:
    """写入演示投标项目（3–5 条浙江电信风格），离线可演示。"""
    path = resolve_projects_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existed = os.path.exists(path)
    if existed and not force:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cur = json.load(f)
            if isinstance(cur, list) and len(cur) > 0:
                return {
                    "path": path,
                    "seeded": False,
                    "count": len(cur),
                    "ids": [p.get("id") for p in cur if isinstance(p, dict)],
                }
        except Exception:
            pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(DEMO_BID_PROJECTS, f, ensure_ascii=False, indent=2)
    op_logger.log("bid_seed", f"写入演示投标项目 {len(DEMO_BID_PROJECTS)} 条 → {path}")
    return {
        "path": path,
        "seeded": True,
        "count": len(DEMO_BID_PROJECTS),
        "ids": [p["id"] for p in DEMO_BID_PROJECTS],
        "replaced": existed,
    }


def list_bid_projects(limit: int = 80) -> dict:
    """项目清单：优先 bid_telecom.db；空库/失败再回落 JSON / demo seed。"""
    db_loaded = load_projects_from_db(limit=limit, prefer_real=True)
    if db_loaded.get("projects"):
        stats = db_loaded.get("db_stats") or {}
        is_real = (stats.get("real_count") or 0) > 0
        banner = None
        if not is_real:
            banner = "当前库内为演示种子（owner=demo），请点击「刷新真实标讯」拉取浙江政采网数据"
        return {
            "path": TELECOM_DB,
            "source": db_loaded.get("source"),
            "count": db_loaded.get("count"),
            "projects": db_loaded["projects"],
            "bid_pipeline_root": _bid_root() or None,
            "using_local_fallback": False,
            "using_json_fallback": False,
            "data_mode": "real" if is_real else "db_demo",
            "db_stats": stats,
            "banner": banner,
            "last_refresh": stats.get("last_refresh") or stats.get("mtime"),
        }

    path = resolve_projects_path()
    projects = []
    source = "file"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                projects = json.load(f) or []
        except Exception as ex:
            op_logger.log("bid_list", f"读取失败: {ex}", level="WARN")
            projects = []
    if not projects:
        info = ensure_demo_projects(force=False)
        path = info["path"]
        with open(path, "r", encoding="utf-8") as f:
            projects = json.load(f)
        source = "demo_seed"
    stats = _db_stats()
    return {
        "path": path,
        "source": source,
        "count": len(projects),
        "projects": projects,
        "bid_pipeline_root": _bid_root() or None,
        "using_local_fallback": True,
        "using_json_fallback": True,
        "data_mode": "json_fallback",
        "db_stats": stats,
        "banner": "当前为本地回退，正在/请刷新真实标讯",
        "last_refresh": stats.get("last_refresh") or stats.get("mtime"),
    }


def bid_status() -> dict:
    cfg = load_config()
    knowledge = resolve_knowledge_root()
    projects_path = resolve_projects_path()
    bid_root = _bid_root()
    configured_knowledge = (cfg.get("knowledge_sync_folder") or "").strip()
    stats = _db_stats()
    hints = []
    if stats.get("real_count", 0) > 0:
        hints.append(
            f"bid_telecom.db 真实标讯 {stats['real_count']} 条"
            + (
                f"（最近刷新 {stats.get('last_refresh')}）"
                if stats.get("last_refresh")
                else ""
            )
        )
    elif stats.get("row_count", 0) > 0:
        hints.append(
            f"bid_telecom.db 有 {stats['row_count']} 条（多为演示种子），请「刷新真实标讯」"
        )
    else:
        hints.append("bid_telecom.db 为空；项目清单将回落 JSON / 演示种子")
    if not bid_root:
        hints.append("未配置 bid_pipeline_root，知识库用本地 knowledge/")
    elif not os.path.isdir(bid_root):
        hints.append(f"bid_pipeline_root 不存在: {bid_root}，读写将回落本地 demo")
    if configured_knowledge and knowledge == KNOWLEDGE_DIR:
        hints.append(
            "knowledge_sync_folder 父目录不可用，正向同步降级到本地 knowledge/"
        )
    if not os.path.exists(projects_path) and not stats.get("row_count"):
        hints.append("项目清单缺失，首次拉取将自动写入演示项目")
    lib_count = 0
    if os.path.isdir(knowledge):
        for _root, _dirs, files in os.walk(knowledge):
            lib_count += sum(1 for fn in files if fn.endswith((".md", ".txt", ".docx")))
    listed = list_bid_projects(limit=5)
    return {
        "bid_pipeline_root": bid_root or "",
        "knowledge_sync_folder": knowledge,
        "projects_path": projects_path,
        "telecom_db": TELECOM_DB,
        "bid_list_exists": os.path.exists(projects_path)
        or bool(stats.get("row_count")),
        "knowledge_doc_count": lib_count,
        "can_sync": True,
        "can_fetch_themes": True,
        "using_local_fallback": listed.get("using_json_fallback", not bool(bid_root)),
        "using_json_fallback": listed.get("using_json_fallback", True),
        "data_mode": listed.get("data_mode"),
        "data_source": listed.get("source"),
        "db_stats": stats,
        "banner": listed.get("banner"),
        "last_refresh": stats.get("last_refresh") or stats.get("mtime"),
        "disabled_reason": None,
        "hints": hints,
        "demo_project_ids": [p["id"] for p in DEMO_BID_PROJECTS],
    }


def _bid_knowledge_root() -> str:
    return resolve_knowledge_root()


def _bid_project_list_path() -> str:
    return resolve_projects_path()


def _copy_article_to_knowledge(article: dict, root: str) -> Optional[dict]:
    src = os.path.join(os.path.dirname(__file__), "articles", article.get("file") or "")
    if not article.get("file") or not os.path.exists(src):
        return None
    tags = article.get("tags") or []
    tag = tags[0] if tags else "未分类"
    tag_safe = re.sub(r'[\\/:*?"<>|]', "_", str(tag))
    dst_dir = os.path.join(root, tag_safe)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    index_file = os.path.join(dst_dir, "index.json")
    idx = []
    if os.path.exists(index_file):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                idx = json.load(f)
        except Exception:
            idx = []
    entry = {
        "id": article.get("id"),
        "title": article.get("title"),
        "summary": article.get("summary", ""),
        "tags": tags,
        "source": "content_factory",
        "ts": datetime.datetime.now().isoformat(),
    }
    idx = [x for x in idx if x.get("id") != entry["id"]]
    idx.append(entry)
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    return {
        "id": article.get("id"),
        "title": article.get("title"),
        "category": tag_safe,
        "path": dst,
    }


def sync_knowledge_to_bid(only_reviewed: bool = True) -> dict:
    """正向推送：已质检稿件 → 标书知识库。"""
    root = resolve_knowledge_root()
    articles = agents.list_articles()
    reviewed = (
        [a for a in articles if a.get("review_pass")]
        if only_reviewed
        else list(articles)
    )
    if only_reviewed and not reviewed:
        # 演示友好：无过审稿时仍同步全部，并标注
        reviewed = list(articles)
        only_reviewed = False
    op_logger.log("bid_sync", f"开始正向推送，待同步稿件{len(reviewed)}篇 → {root}")
    os.makedirs(root, exist_ok=True)
    synced = []
    for a in reviewed:
        item = _copy_article_to_knowledge(a, root)
        if item:
            synced.append(item)

    try:
        vec_src = os.path.join(os.path.dirname(__file__), "vector_db")
        cfg = load_config()
        vec_dst = (cfg.get("vector_sync_path") or "").strip()
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
    return {
        "synced_count": len(synced),
        "target": root,
        "items": synced,
        "only_reviewed": only_reviewed,
        "using_local_fallback": root == KNOWLEDGE_DIR,
    }


def push_article_to_knowledge(article_id: str) -> dict:
    """单篇稿件推入标书知识库（战役/稿件台「推入标书知识库」）。"""
    articles = agents.list_articles()
    art = next((a for a in articles if a.get("id") == article_id), None)
    if not art:
        raise ValueError(f"文章不存在: {article_id}")
    root = resolve_knowledge_root()
    os.makedirs(root, exist_ok=True)
    item = _copy_article_to_knowledge(art, root)
    if not item:
        raise FileNotFoundError(f"文章文件缺失: {art.get('file')}")
    op_logger.log("bid_push", f"稿件 {article_id} → {item['path']}")
    return {"ok": True, "item": item, "target": root}


def push_campaign_text_to_knowledge(
    campaign_id: str,
    title: str,
    text: str,
    tags: Optional[List[str]] = None,
    artifact_id: str = "",
) -> dict:
    """战役产物文本写入知识库（Markdown 落盘）。"""
    root = resolve_knowledge_root()
    tag = (tags or ["战役产物"])[0]
    tag_safe = re.sub(r'[\\/:*?"<>|]', "_", str(tag))
    dst_dir = os.path.join(root, tag_safe)
    os.makedirs(dst_dir, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", (title or campaign_id)[:40])
    fn = f"CAMP_{campaign_id}_{artifact_id or 'doc'}_{safe_title}.md".replace(" ", "_")
    path = os.path.join(dst_dir, fn)
    body = f"# {title or campaign_id}\n\n> campaign_id: {campaign_id}\n\n{text or ''}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    index_file = os.path.join(dst_dir, "index.json")
    idx = []
    if os.path.exists(index_file):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                idx = json.load(f)
        except Exception:
            idx = []
    entry = {
        "id": f"CAMP_{campaign_id}_{artifact_id or hashlib.md5(fn.encode()).hexdigest()[:8]}",
        "title": title,
        "campaign_id": campaign_id,
        "artifact_id": artifact_id,
        "summary": (text or "")[:160],
        "ts": datetime.datetime.now().isoformat(),
        "file": fn,
    }
    idx.append(entry)
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    op_logger.log("bid_push", f"战役产物 {campaign_id}/{artifact_id} → {path}")
    return {"ok": True, "path": path, "entry": entry, "target": root}


def _themes_from_projects(projects: list) -> list:
    ind_count = {}
    for p in projects:
        ind = p.get("industry") or p.get("赛道") or "未分类"
        ind_count[ind] = ind_count.get(ind, 0) + 1
    return sorted(ind_count.items(), key=lambda x: x[1], reverse=True)


def fetch_bid_project_themes() -> dict:
    """反向拉取：赛道主题 + 选题建议（优先真实库 industry/region）。"""
    listed = list_bid_projects(limit=500)
    projects = listed.get("projects") or []
    themes = _themes_from_projects(projects)
    source = listed.get("source", "file")

    # 额外：地区维度信号（真实库字段）
    region_count = {}
    for p in projects:
        reg = p.get("region") or "未知"
        region_count[reg] = region_count.get(reg, 0) + 1
    regions = sorted(region_count.items(), key=lambda x: x[1], reverse=True)

    if not themes:
        try:
            import data_feedback

            r = data_feedback.analyze_topic_data_with_nl2sql()
            hot = r.get("bid_stats", {}).get("hot_industries", [])
            themes = [(h["industry"], h["amount"]) for h in hot]
            source = "nl2sql"
            op_logger.log("bid_fetch", f"清单空，NL2SQL 热门行业 {len(themes)} 个")
        except Exception as ex:
            op_logger.log("bid_fetch", f"NL2SQL 联动失败: {ex}", level="WARN")

    suggestions = []
    for ind, cnt in themes[:8]:
        suggestions.append(
            {
                "industry": ind,
                "topic": f"{ind}领域投标项目技术方案与中标趋势分析",
                "topic_lead_gen": f"{ind}赛道政企获客内容包：案例故事+跟进话术",
                "topic_brief": f"{ind}行业综述：浙江电信市场机会与可沉淀知识要点",
                "signal": cnt,
                "campaign_templates": ["lead_gen", "industry_brief"],
            }
        )
    op_logger.log("bid_fetch", f"生成垂直领域选题 {len(suggestions)} 个")
    return {
        "themes": [{"industry": ind, "count": cnt} for ind, cnt in themes],
        "regions": [{"region": r, "count": c} for r, c in regions[:12]],
        "topic_suggestions": suggestions,
        "projects_count": len(projects),
        "source": source,
        "path": listed.get("path"),
        "data_mode": listed.get("data_mode"),
        "banner": listed.get("banner"),
        "db_stats": listed.get("db_stats"),
    }


def write_themes_to_topic_pool(
    suggestions: Optional[list] = None, limit: int = 6
) -> dict:
    """赛道选题建议 → 写入内容工厂选题池。"""
    import topic_collector

    if not suggestions:
        suggestions = fetch_bid_project_themes().get("topic_suggestions") or []
    suggestions = suggestions[:limit]
    history = topic_collector.load_topics()
    added = []
    for s in suggestions:
        title = s.get("topic") or s.get("title") or ""
        if not title:
            continue
        tid = "BID_" + hashlib.md5(title.encode("utf-8")).hexdigest()[:10]
        if any(t.get("id") == tid for t in history):
            continue
        entry = {
            "id": tid,
            "title": title,
            "summary": s.get("summary")
            or f"来自标书赛道「{s.get('industry', '')}」· 信号 {s.get('signal', '')}",
            "source": "bid_pipeline",
            "industry": s.get("industry", ""),
            "scores": {
                "受众价值": 8,
                "实操落地性": 7,
                "竞品稀缺度": 8,
                "流量潜力": 7,
                "市场热度": 8,
            },
            "total_score": 38,
            "status": "candidate",
            "created_at": datetime.datetime.now().isoformat(),
        }
        history.append(entry)
        added.append(entry)
    with open(topic_collector.TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    op_logger.log("bid_topics", f"写入选题池 {len(added)} 条")
    return {"ok": True, "added_count": len(added), "topics": added}


def theme_to_campaign(
    industry: str,
    template: str = "lead_gen",
    created_by: str = "admin",
    auto_approve: bool = False,
    project_name: str = "",
    project_id: str = "",
) -> dict:
    """真实标讯/赛道主题 → 发起获客/综述战役（桥接 Campaign OS）。"""
    from campaign import runner as camp_runner

    industry = (industry or "").strip() or "政企信息化"
    project_name = (project_name or "").strip()
    project_id = (project_id or "").strip()
    if template not in ("lead_gen", "industry_brief"):
        template = "lead_gen"
    if project_name:
        if template == "industry_brief":
            goal = (
                f"基于真实标讯「{project_name}」（赛道 {industry}"
                f"{(' · ' + project_id) if project_id else ''}）"
                f"输出行业综述与可入库知识要点，服务标书材料沉淀"
            )
        else:
            goal = (
                f"基于真实标讯「{project_name}」（赛道 {industry}"
                f"{(' · ' + project_id) if project_id else ''}）"
                f"制作政企获客内容包与跟进话术，支撑投标前后触达"
            )
    elif template == "industry_brief":
        goal = (
            f"围绕「{industry}」赛道输出行业综述长文与可入库知识要点，服务标书材料沉淀"
        )
    else:
        goal = f"围绕「{industry}」赛道制作政企获客内容包与跟进话术，支撑投标前后触达"
    camp = camp_runner.start_campaign(
        goal=goal,
        template=template,
        created_by=created_by,
        allow_mock=False,
        auto_approve=auto_approve,
    )
    op_logger.log(
        "bid_campaign",
        f"标讯/赛道 {industry} · {project_name or '-'} → 战役 {camp.get('id')} ({template})",
    )
    return {
        "ok": True,
        "industry": industry,
        "template": template,
        "project_name": project_name,
        "project_id": project_id,
        "campaign_id": camp.get("id"),
        "campaign": camp,
        "goal": goal,
    }


def list_knowledge_index(limit: int = 40) -> dict:
    """知识库 index.json 汇总，供证据矩阵匹配。"""
    root = resolve_knowledge_root()
    items = []
    if os.path.isdir(root):
        for dirpath, _dirs, files in os.walk(root):
            if "index.json" in files:
                try:
                    with open(
                        os.path.join(dirpath, "index.json"), "r", encoding="utf-8"
                    ) as f:
                        idx = json.load(f) or []
                    for it in idx:
                        it = dict(it)
                        it["category"] = os.path.basename(dirpath)
                        items.append(it)
                except Exception:
                    pass
            for fn in files:
                if fn.endswith(".md") and fn != "README.md":
                    rel = os.path.relpath(os.path.join(dirpath, fn), root)
                    if not any(
                        i.get("file") == fn or i.get("title") in fn for i in items
                    ):
                        items.append(
                            {
                                "id": hashlib.md5(rel.encode()).hexdigest()[:10],
                                "title": fn,
                                "file": fn,
                                "category": os.path.basename(dirpath),
                                "summary": "",
                            }
                        )
    items = items[-limit:]
    return {"root": root, "count": len(items), "items": items}
