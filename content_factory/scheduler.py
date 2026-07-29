# -*- coding: utf-8 -*-
"""
模块4：定时任务调度系统
1. 支持配置定时采集资讯、定时生成文稿、定时同步知识库
2. 本地定时方案，适配 Windows，无需额外系统服务
3. 任务持久化保存 schedule_config.json
4. 支持启动/暂停/查看任务列表
5. 定时任务执行日志独立记录
"""
import os
import json
import time
import threading
import datetime
from config_loader import ROOT
import op_logger

SCHEDULE_FILE = os.path.join(ROOT, "schedule_config.json")
SCHED_LOG = os.path.join(ROOT, "logs", "scheduler.log")

_cron_parse_cache = {}
_running = False
_started_at = None
_thread = None
_lock = threading.Lock()
_EMBEDDED = False  # True = Web 进程内嵌线程；False = start_scheduler.bat 独立进程


def _log_sched(msg: str, level: str = "INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {level} | {msg}"
    with open(SCHED_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    op_logger.log("scheduler", msg, level=level)


def parse_cron(cron: str):
    """简易 cron 解析: '分 时 日 月 周'，支持 * 和数字"""
    parts = cron.split()
    if len(parts) != 5:
        return None
    def f(p, lo, hi):
        if p == "*":
            return None
        return int(p)
    return (f(parts[0], 0, 59), f(parts[1], 0, 23), f(parts[2], 1, 31), f(parts[3], 1, 12), f(parts[4], 0, 6))


def _should_run(cron_field, now_val):
    return cron_field is None or cron_field == now_val


def _execute_task(action: str, params: dict):
    """执行调度任务"""
    _log_sched(f"执行任务: {action}, 参数: {params}")
    try:
        if action == "collect_topics":
            import topic_collector
            r = topic_collector.collect_topics(topk=params.get("topk", 6))
            _log_sched(f"选题采集完成: {r['count']}条")
        elif action == "generate_article":
            import topic_collector, agents
            topics = topic_collector.load_topics()
            sel = [t for t in topics if t["status"] == "candidate"]
            if sel:
                t = sel[0]
                agents.generate_article(t["title"], t.get("summary", ""))
                _log_sched(f"文稿生成完成: {t['title']}")
        elif action == "sync_knowledge_to_bid":
            import bid_pipeline_link
            r = bid_pipeline_link.sync_knowledge_to_bid()
            _log_sched(f"知识库同步完成: {r['synced_count']}篇")
        else:
            _log_sched(f"未知 action: {action}", level="WARN")
    except Exception as ex:
        _log_sched(f"任务执行异常: {action} - {ex}", level="ERROR")


def tick():
    """检查一次是否到点执行（由 main 循环调用）"""
    now = datetime.datetime.now()
    cfg = load_schedule()
    for t in cfg.get("tasks", []):
        if not t.get("enabled", True):
            continue
        cron = parse_cron(t["cron"])
        if not cron:
            continue
        m, h, d, mo, w = cron
        if all([_should_run(m, now.minute), _should_run(h, now.hour),
                _should_run(d, now.day), _should_run(mo, now.month), _should_run(w, now.weekday())]):
            # 防重复：同分钟内不重复执行
            key = f"{t['id']}_{now.strftime('%Y%m%d%H%M')}"
            if key in _cron_parse_cache:
                continue
            _cron_parse_cache[key] = True
            _execute_task(t["action"], t.get("params", {}))


def load_schedule() -> dict:
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tasks": []}


def save_schedule(cfg: dict):
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def toggle_task(task_id: str, enabled: bool) -> bool:
    cfg = load_schedule()
    for t in cfg["tasks"]:
        if t["id"] == task_id:
            t["enabled"] = enabled
            save_schedule(cfg)
            _log_sched(f"任务[{task_id}] {'启用' if enabled else '暂停'}")
            return True
    return False


def add_task(task_id: str, name: str, cron: str, action: str, params: dict = None) -> bool:
    cfg = load_schedule()
    cfg["tasks"].append({"id": task_id, "name": name, "enabled": True, "cron": cron,
                         "action": action, "params": params or {}})
    save_schedule(cfg)
    _log_sched(f"新增定时任务[{task_id}] {cron} -> {action}")
    return True


def is_running() -> bool:
    with _lock:
        return bool(_running)


def status() -> dict:
    """供 UI / health：调度器是否在跑、嵌入还是独立进程。"""
    with _lock:
        running = bool(_running)
        started = _started_at
        embedded = _EMBEDDED
        thread_alive = bool(_thread and _thread.is_alive())
    cfg = load_schedule()
    tasks = cfg.get("tasks") or []
    enabled = sum(1 for t in tasks if t.get("enabled", True))
    return {
        "running": running or thread_alive,
        "embedded": embedded,
        "started_at": started,
        "task_count": len(tasks),
        "enabled_count": enabled,
        "hint": (
            "调度器运行中（Web 内嵌线程）" if (running or thread_alive) and embedded
            else "调度器运行中" if (running or thread_alive)
            else "未启动 — 可点「启动调度器」或运行 content_factory/start_scheduler.bat"
        ),
        "start_script": "content_factory/start_scheduler.bat",
    }


def start_background(embedded: bool = True) -> dict:
    """轻量后台线程跑 tick 循环（Windows 友好，不做系统 cron）。"""
    global _running, _started_at, _thread, _EMBEDDED
    with _lock:
        if _running or (_thread and _thread.is_alive()):
            return {"ok": True, "already": True, **status()}
        _EMBEDDED = bool(embedded)
        _started_at = datetime.datetime.now().isoformat(timespec="seconds")

        def _worker():
            global _running
            with _lock:
                _running = True
            _log_sched("定时调度服务启动（background thread）")
            try:
                while True:
                    with _lock:
                        if not _running:
                            break
                    try:
                        tick()
                    except Exception as ex:
                        _log_sched(f"调度tick异常: {ex}", level="ERROR")
                    time.sleep(30)
            finally:
                with _lock:
                    _running = False
                _log_sched("定时调度服务已停止")

        t = threading.Thread(target=_worker, name="chengjuntai-scheduler", daemon=True)
        _thread = t
        t.start()
    return {"ok": True, "already": False, **status()}


def stop_background() -> dict:
    """仅停止本进程内嵌线程；独立 bat 进程请自行关闭窗口。"""
    global _running
    with _lock:
        if not _EMBEDDED:
            return {"ok": False, "error": "当前非内嵌线程，请关闭 start_scheduler.bat 窗口", **status()}
        _running = False
    return {"ok": True, **status()}


def run_loop():
    """定时调度主循环（每 30 秒检查一次）— 供独立进程 / bat 调用。"""
    global _running, _started_at, _EMBEDDED
    with _lock:
        if _running:
            return
        _running = True
        _EMBEDDED = False
        _started_at = datetime.datetime.now().isoformat(timespec="seconds")
    _log_sched("定时调度服务启动")
    try:
        while True:
            try:
                tick()
            except Exception as ex:
                _log_sched(f"调度tick异常: {ex}", level="ERROR")
            time.sleep(30)
    finally:
        with _lock:
            _running = False


if __name__ == "__main__":
    os.makedirs(os.path.dirname(SCHED_LOG), exist_ok=True)
    run_loop()
