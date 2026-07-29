# -*- coding: utf-8 -*-
"""战役持久化：JSON 文件存储（预赛可交付，后续可换 MySQL）"""
import os
import json
import datetime
import threading
from typing import Optional
from config_loader import DATA_DIR

CAMPAIGNS_DIR = os.path.join(DATA_DIR, "campaigns")
METRICS_FILE = os.path.join(DATA_DIR, "campaign_metrics.json")
os.makedirs(CAMPAIGNS_DIR, exist_ok=True)

_lock = threading.RLock()

STATUSES = (
    "draft",
    "planned",          # 任务树已生成，待人审
    "running",
    "awaiting_review",  # 任务完成，待导出前终审
    "completed",
    "rejected",
    "failed",
)


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _path(cid: str) -> str:
    return os.path.join(CAMPAIGNS_DIR, f"{cid}.json")


def _load_metrics() -> dict:
    if not os.path.exists(METRICS_FILE):
        return {
            "campaigns_started": 0,
            "campaigns_completed": 0,
            "tasks_done": 0,
            "artifacts_count": 0,
            "est_hours_saved": 0.0,
            "llm_calls_ok": 0,
            "llm_calls_fail": 0,
        }
    with open(METRICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_metrics(m: dict):
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def bump_metric(key: str, delta=1):
    with _lock:
        m = _load_metrics()
        m[key] = m.get(key, 0) + delta
        _save_metrics(m)


def metrics_snapshot() -> dict:
    with _lock:
        m = dict(_load_metrics())
    # 按模板拆分（从战役文件实时统计，不改历史埋点）
    by_tpl = {"lead_gen": {"started": 0, "completed": 0}, "industry_brief": {"started": 0, "completed": 0}, "other": {"started": 0, "completed": 0}}
    demo_ids = set()
    completed_demos = []
    try:
        for name in os.listdir(CAMPAIGNS_DIR):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(CAMPAIGNS_DIR, name), "r", encoding="utf-8") as f:
                c = json.load(f)
            tpl = c.get("template") or "other"
            if tpl not in by_tpl:
                tpl = "other"
            by_tpl[tpl]["started"] += 1
            if c.get("status") == "completed":
                by_tpl[tpl]["completed"] += 1
            cid = c.get("id") or ""
            if cid.startswith("CMP_DEMO") or c.get("demo_snapshot"):
                demo_ids.add(cid)
                if c.get("status") == "completed":
                    completed_demos.append(cid)
    except Exception:
        pass
    bid_stats = _bid_counts()
    m["by_template"] = by_tpl
    m["bid_real_count"] = bid_stats.get("real_count") or 0
    m["bid_demo_count"] = bid_stats.get("demo_count") or 0
    m["bid_row_count"] = bid_stats.get("row_count") or 0
    m["demo_campaign_count"] = len(demo_ids)
    m["week_story"] = _week_story_line(m, by_tpl, demo_ids, completed_demos, bid_stats)
    return m


def _bid_counts() -> dict:
    """标讯库计数（真实 / 演示），供本周故事叙事；失败则静默 0。"""
    try:
        import bid_pipeline_link
        st = bid_pipeline_link.bid_status()
        ds = st.get("db_stats") or {}
        return {
            "real_count": int(ds.get("real_count") or 0),
            "demo_count": int(ds.get("demo_count") or 0),
            "row_count": int(ds.get("row_count") or 0),
            "data_mode": st.get("data_mode") or "",
        }
    except Exception:
        return {"real_count": 0, "demo_count": 0, "row_count": 0, "data_mode": ""}


def _week_story_line(
    m: dict, by_tpl: dict, demo_ids: set, completed_demos: list, bid_stats: Optional[dict] = None
) -> str:
    """答辩/首页用的一句「本周故事」：演示周包 + 标讯计数闭环。"""
    hrs = m.get("est_hours_saved") or 0
    try:
        hrs_txt = f"{float(hrs):.0f}"
    except (TypeError, ValueError):
        hrs_txt = str(hrs)
    lead_done = (by_tpl.get("lead_gen") or {}).get("completed") or 0
    brief_done = (by_tpl.get("industry_brief") or {}).get("completed") or 0
    bid = bid_stats or {}
    real_n = int(bid.get("real_count") or 0)
    demo_n = int(bid.get("demo_count") or 0)
    row_n = int(bid.get("row_count") or 0)
    if real_n > 0:
        bid_bit = f"真实标讯 {real_n} 条可一键成军"
    elif row_n > 0:
        bid_bit = f"标讯库 {row_n} 条（演示种子 {demo_n}）可刷真实后一键成军"
    else:
        bid_bit = "标讯库待刷新 · 可点标书工作台「刷新真实标讯」"
    has_week = "CMP_DEMO_WEEK_LEAD" in demo_ids or "CMP_DEMO_WEEK_BRIEF" in demo_ids
    if has_week:
        return (
            f"本周故事：缺编辑部的一人公司闭环已演示——"
            f"获客样例交付种草话术与跟进表，综述样例可入库；"
            f"约 {hrs_txt} 人时节省叙事 · 获客完成 {lead_done} / 综述完成 {brief_done} · "
            f"{bid_bit}。"
        )
    if completed_demos:
        return (
            f"本周故事：已有 {len(completed_demos)} 场样例战役完成，"
            f"预估节省约 {hrs_txt} 人时；{bid_bit}。"
        )
    return (
        f"本周故事：已发起 {m.get('campaigns_started') or 0} 场、完成 {m.get('campaigns_completed') or 0} 场；"
        f"{bid_bit}；运行 scripts/seed_demo_week.py 可载入评委演示周包。"
    )


def create_campaign(goal: str, template: str = "lead_gen", created_by: str = "admin") -> dict:
    cid = f"CMP{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    camp = {
        "id": cid,
        "goal": goal,
        "template": template,
        "status": "draft",
        "created_by": created_by,
        "created_at": _now(),
        "updated_at": _now(),
        "plan": None,
        "tasks": [],
        "artifacts": [],
        "gate": {"required": True, "approved": False, "note": ""},
        "llm_provider": None,
        "error": None,
        "metrics": {"hours_saved_est": 0},
    }
    with _lock:
        with open(_path(cid), "w", encoding="utf-8") as f:
            json.dump(camp, f, ensure_ascii=False, indent=2)
        bump_metric("campaigns_started", 1)
    return camp


def get_campaign(cid: str) -> Optional[dict]:
    fp = _path(cid)
    if not os.path.exists(fp):
        return None
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


def update_campaign(cid: str, **kwargs) -> Optional[dict]:
    with _lock:
        camp = get_campaign(cid)
        if not camp:
            return None
        camp.update(kwargs)
        camp["updated_at"] = _now()
        with open(_path(cid), "w", encoding="utf-8") as f:
            json.dump(camp, f, ensure_ascii=False, indent=2)
        return camp


def list_campaigns(limit: int = 50) -> list:
    files = sorted(
        [f for f in os.listdir(CAMPAIGNS_DIR) if f.endswith(".json")],
        reverse=True,
    )[:limit]
    out = []
    for name in files:
        with open(os.path.join(CAMPAIGNS_DIR, name), "r", encoding="utf-8") as f:
            c = json.load(f)
            out.append({
                "id": c["id"],
                "goal": c["goal"],
                "template": c.get("template"),
                "status": c["status"],
                "created_by": c.get("created_by") or "",
                "created_at": c["created_at"],
                "updated_at": c.get("updated_at"),
                "task_count": len(c.get("tasks", [])),
                "artifact_count": len(c.get("artifacts", [])),
                "llm_provider": c.get("llm_provider"),
                "demo_snapshot": bool(c.get("demo_snapshot")),
            })
    return out


def save_artifact(cid: str, role: str, title: str, content: str, kind: str = "markdown",
                  extra: dict = None) -> dict:
    camp = get_campaign(cid)
    if not camp:
        raise ValueError(f"campaign not found: {cid}")
    art_id = f"ART{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{role}"
    art_dir = os.path.join(CAMPAIGNS_DIR, cid)
    os.makedirs(art_dir, exist_ok=True)
    ext = "md" if kind == "markdown" else "txt"
    fname = f"{art_id}.{ext}"
    fpath = os.path.join(art_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    meta = {
        "id": art_id,
        "role": role,
        "title": title,
        "kind": kind,
        "file": fname,
        "path": fpath,
        "created_at": _now(),
        "chars": len(content),
    }
    if extra:
        meta.update(extra)
    arts = list(camp.get("artifacts", []))
    arts.append(meta)
    update_campaign(cid, artifacts=arts)
    bump_metric("artifacts_count", 1)
    return meta


def list_artifacts(cid: str) -> list:
    camp = get_campaign(cid)
    return camp.get("artifacts", []) if camp else []


def resolve_artifact_path(cid: str, meta: dict) -> str:
    """兼容绝对 path / 相对 file；优先战役目录下文件名。"""
    candidates = []
    p = meta.get("path") or ""
    fn = meta.get("file") or ""
    if p:
        candidates.append(p)
    if fn:
        candidates.append(os.path.join(CAMPAIGNS_DIR, cid, os.path.basename(fn)))
        if not os.path.isabs(fn):
            candidates.append(os.path.join(CAMPAIGNS_DIR, cid, fn))
    for fp in candidates:
        if fp and os.path.exists(fp):
            return fp
    return candidates[0] if candidates else ""


def read_artifact_content(cid: str, art_id: str) -> str:
    camp = get_campaign(cid)
    if not camp:
        return ""
    for a in camp.get("artifacts", []):
        if a["id"] == art_id:
            fp = resolve_artifact_path(cid, a)
            if not fp or not os.path.exists(fp):
                return ""
            with open(fp, "r", encoding="utf-8") as f:
                return f.read()
    return ""


def list_all_artifacts(limit: int = 80) -> list:
    """产物中心：跨战役产物摘要。"""
    camps = list_campaigns(limit=50)
    out = []
    for csum in camps:
        c = get_campaign(csum["id"])
        if not c:
            continue
        for a in c.get("artifacts") or []:
            out.append({
                "campaign_id": c["id"],
                "campaign_goal": c.get("goal", "")[:80],
                "campaign_status": c.get("status"),
                "artifact_id": a.get("id"),
                "role": a.get("role"),
                "title": a.get("title"),
                "created_at": a.get("created_at"),
                "chars": a.get("chars"),
            })
            if len(out) >= limit:
                return out
    return out
