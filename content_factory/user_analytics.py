# -*- coding: utf-8 -*-
"""
用户洞察：轨迹埋点 + 简单画像规则
append-only JSONL：content_factory/data/user_events.jsonl
"""
import os
import json
import datetime
import threading
from typing import Optional
from config_loader import DATA_DIR
import auth_users

EVENTS_FILE = os.path.join(DATA_DIR, "user_events.jsonl")
_lock = threading.RLock()
os.makedirs(DATA_DIR, exist_ok=True)


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def log_event(user: str, action: str, meta: Optional[dict] = None) -> None:
    """追加一条用户行为事件。"""
    row = {
        "ts": _now(),
        "user": user or "anonymous",
        "action": action,
        "meta": meta or {},
    }
    with _lock:
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_events(username: Optional[str] = None, limit: int = 200) -> list:
    if not os.path.exists(EVENTS_FILE):
        return []
    rows = []
    with _lock:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if username:
        key = username.lower()
        filtered = []
        for r in rows:
            u = str(r.get("user") or "")
            if u == username or u.lower() == key:
                filtered.append(r)
            else:
                # 也匹配邮箱登录标识
                pub = auth_users.get_user(username)
                if pub:
                    ids = {pub.get("username"), (pub.get("email") or "").lower()}
                    if u in ids or u.lower() in ids:
                        filtered.append(r)
        rows = filtered
    return rows[-limit:]


def _count_actions(events: list) -> dict:
    counts = {}
    for e in events:
        a = e.get("action") or "unknown"
        counts[a] = counts.get(a, 0) + 1
    return counts


def infer_persona(identity: str) -> dict:
    """
    简单规则画像：
    - new: 登录少、无战役
    - heavy: 战役/任务多
    - content-focused: generate_article 多
    - campaign-focused: campaign_* 多
    - dormant: 有历史但近 7 天无事件
    """
    user = auth_users.get_user(identity)
    events = read_events(identity, limit=500)
    counts = _count_actions(events)
    usage = (user or {}).get("usage") or {}
    campaigns = int(usage.get("campaigns_started", 0)) + counts.get("campaign_start", 0)
    articles = int(usage.get("articles_generated", 0)) + counts.get("generate_article", 0)
    logins = int(usage.get("logins", 0)) + counts.get("login", 0)
    campaign_acts = (
        counts.get("campaign_start", 0)
        + counts.get("approve", 0)
        + counts.get("report", 0)
    )

    tags = []
    segment = "new"
    if logins <= 1 and campaigns == 0 and articles == 0:
        segment = "new"
        tags.append("新用户")
    elif campaigns >= 3 or campaign_acts >= 5:
        segment = "heavy"
        tags.append("重度用户")
    elif articles >= 2 and articles >= campaign_acts:
        segment = "content-focused"
        tags.append("内容向")
    elif campaign_acts >= 1 or campaigns >= 1:
        segment = "campaign-focused"
        tags.append("成军向")
    else:
        segment = "light"
        tags.append("轻度使用")

    # dormant：最近事件超过 7 天
    if events:
        try:
            last = events[-1].get("ts", "")
            last_dt = datetime.datetime.fromisoformat(last)
            if (datetime.datetime.now() - last_dt).days >= 7:
                tags.append("沉寂")
                if segment == "new":
                    segment = "dormant"
        except Exception:
            pass

    notes = ""
    if user and user.get("profile"):
        notes = user["profile"].get("notes") or ""
        # 合并人工 tags
        for t in user["profile"].get("tags") or []:
            if t and t not in tags:
                tags.append(t)
        # 若管理员手动设过 segment 且非空，优先展示人工值
        manual = user["profile"].get("segment")
        if manual and manual not in ("new", ""):
            # 保留规则推断，但标注人工覆盖
            if manual != segment:
                tags.append(f"人工:{manual}")

    return {
        "identity": identity,
        "username": (user or {}).get("username"),
        "email": (user or {}).get("email"),
        "segment": segment,
        "tags": tags,
        "notes": notes,
        "action_counts": counts,
        "usage": usage,
        "event_count": len(events),
        "last_event_at": events[-1]["ts"] if events else None,
    }


def usage_table() -> list:
    """超级管理员用量总览。"""
    rows = []
    for u in auth_users.list_users(include_usage=True):
        persona = infer_persona(u["username"])
        rows.append({
            "username": u["username"],
            "email": u.get("email") or "",
            "display_name": u.get("display_name") or u["username"],
            "role": u.get("role"),
            "enabled": u.get("enabled", True),
            "last_login_at": u.get("last_login_at"),
            "campaigns_started": (u.get("usage") or {}).get("campaigns_started", 0),
            "tasks_done": (u.get("usage") or {}).get("tasks_done", 0),
            "articles_generated": (u.get("usage") or {}).get("articles_generated", 0),
            "logins": (u.get("usage") or {}).get("logins", 0),
            "reports_exported": (u.get("usage") or {}).get("reports_exported", 0),
            "segment": persona.get("segment"),
            "tags": persona.get("tags") or [],
        })
    return rows
