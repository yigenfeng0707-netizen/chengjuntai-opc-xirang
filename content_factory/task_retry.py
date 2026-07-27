# -*- coding: utf-8 -*-
"""
模块6：任务容错机制
- 网络异常、API调用失败、抓取超时自动重试
- 可配置最大重试次数、重试间隔
- 连续失败达阈值终止任务，记录异常日志
- 任务断点状态保存，支持后续恢复
"""
import os
import time
import json
import functools
import datetime
from config_loader import LOGS_DIR, DATA_DIR, load_config

RETRY_LOG = os.path.join(LOGS_DIR, "task_retry.log")
BREAKPOINT_FILE = os.path.join(DATA_DIR, "breakpoint.json")


def log_retry(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {msg}"
    with open(RETRY_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_breakpoints() -> dict:
    if os.path.exists(BREAKPOINT_FILE):
        try:
            with open(BREAKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_breakpoint(task_id: str, state: dict):
    bp = load_breakpoints()
    bp[task_id] = {"state": state, "ts": datetime.datetime.now().isoformat()}
    with open(BREAKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(bp, f, ensure_ascii=False, indent=2)


def clear_breakpoint(task_id: str):
    bp = load_breakpoints()
    if task_id in bp:
        del bp[task_id]
        with open(BREAKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(bp, f, ensure_ascii=False, indent=2)


def retry(task_id: str = None):
    """
    任务重试装饰器
    用法:
        @retry("collect_topics")
        def do_fetch(): ...
    连续失败达 max_retry 终止并抛出最后异常，同时记录断点
    """
    cfg = load_config()
    max_retry = int(cfg.get("max_retry", 3))
    interval = int(cfg.get("retry_interval", 10))

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_retry + 1):
                try:
                    result = fn(*args, **kwargs)
                    if task_id:
                        clear_breakpoint(task_id)
                    log_retry(f"任务[{task_id or fn.__name__}] 第{attempt}次成功")
                    return result
                except Exception as e:
                    last_err = e
                    log_retry(f"任务[{task_id or fn.__name__}] 第{attempt}/{max_retry}次失败: {e}")
                    if task_id:
                        save_breakpoint(task_id, {"attempt": attempt, "error": str(e)})
                    if attempt < max_retry:
                        time.sleep(interval)
            log_retry(f"任务[{task_id or fn.__name__}] 连续{max_retry}次失败，终止")
            raise RuntimeError(f"任务连续失败终止: {last_err}")
        return wrapper
    return deco


def resume_task(task_id: str, fn, *args, **kwargs):
    """从断点恢复执行任务"""
    bp = load_breakpoints()
    if task_id in bp:
        log_retry(f"任务[{task_id}] 从断点恢复，上次状态: {bp[task_id]['state']}")
    return retry(task_id)(fn)(*args, **kwargs)
