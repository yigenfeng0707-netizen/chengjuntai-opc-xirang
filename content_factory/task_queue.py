# -*- coding: utf-8 -*-
"""
模块9：任务优先级队列
- 任务分级：高/普通/低
- 高优先级优先抢占资源
- 动态修改优先级、取消排队任务
- 持久化队列状态，程序重启不丢失
- 队列负载监控，避免并发过载
"""
import os
import json
import time
import threading
import datetime
from config_loader import DATA_DIR

QUEUE_FILE = os.path.join(DATA_DIR, "task_queue.json")
_lock = threading.Lock()

PRIORITY_HIGH = 1      # 标书紧急素材
PRIORITY_NORMAL = 5    # 普通任务
PRIORITY_LOW = 9       # 常规资讯采集

PRIORITY_LABEL = {1: "高", 5: "普通", 9: "低"}

MAX_CONCURRENT = 2  # 最大并发数，避免过载


def _load() -> dict:
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"tasks": [], "running": []}


def _save(q: dict):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)


def add_task(task_name: str, action: str, params: dict = None, priority: int = PRIORITY_NORMAL, task_id: str = None) -> str:
    """入队，返回 task_id"""
    with _lock:
        q = _load()
        tid = task_id or f"T{int(time.time()*1000)}"
        q["tasks"].append({
            "task_id": tid,
            "task_name": task_name,
            "action": action,
            "params": params or {},
            "priority": priority,
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat()
        })
        # 按优先级排序（数值小优先）
        q["tasks"].sort(key=lambda t: t["priority"])
        _save(q)
    return tid


def pop_next():
    """取出下一个最高优先级任务（从队列移入running）"""
    with _lock:
        q = _load()
        if len(q["running"]) >= MAX_CONCURRENT:
            return None
        if not q["tasks"]:
            return None
        t = q["tasks"].pop(0)
        t["status"] = "running"
        t["started_at"] = datetime.datetime.now().isoformat()
        q["running"].append(t)
        _save(q)
        return t


def finish_task(task_id: str, result: str = ""):
    with _lock:
        q = _load()
        q["running"] = [t for t in q["running"] if t["task_id"] != task_id]
        _save(q)


def cancel_task(task_id: str) -> bool:
    with _lock:
        q = _load()
        before = len(q["tasks"])
        q["tasks"] = [t for t in q["tasks"] if t["task_id"] != task_id]
        _save(q)
        return len(q["tasks"]) < before


def set_priority(task_id: str, priority: int):
    with _lock:
        q = _load()
        for t in q["tasks"]:
            if t["task_id"] == task_id:
                t["priority"] = priority
        q["tasks"].sort(key=lambda t: t["priority"])
        _save(q)


def list_queue():
    q = _load()
    return {
        "pending": [{"task_id": t["task_id"], "task_name": t["task_name"],
                     "priority": PRIORITY_LABEL.get(t["priority"], t["priority"]),
                     "status": t["status"]} for t in q["tasks"]],
        "running": [{"task_id": t["task_id"], "task_name": t["task_name"]} for t in q["running"]],
        "load": f"{len(q['running'])}/{MAX_CONCURRENT}"
    }


def is_overload():
    q = _load()
    return len(q["running"]) >= MAX_CONCURRENT
