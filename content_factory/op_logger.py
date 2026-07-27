# -*- coding: utf-8 -*-
"""
模块12：操作日志导出
1. 记录全部人员操作、任务启动、文件修改、同步事件
2. 支持按时间范围筛选日志
3. 一键导出日志为 CSV 文件，用于审计追溯
4. 日志按天滚动分割，防止单个日志文件过大
"""
import os
import csv
import json
import datetime
from config_loader import LOGS_DIR, load_config

OP_LOG_FILE = os.path.join(LOGS_DIR, "operations.log")


def log(action: str, message: str, level: str = "INFO", task_id: str = None, user: str = ""):
    """记录操作日志（按天滚动文件名）"""
    roll_days = int(load_config().get("log_roll_days", 30))
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cur_file = os.path.join(LOGS_DIR, f"operations-{today}.log")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {level} | {action} | {user or '-'} | {task_id or '-'} | {message}"
    with open(cur_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    # 同步写主日志（兼容旧引用）
    with open(OP_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    # 清理过期日志
    try:
        _cleanup_old(roll_days)
    except Exception:
        pass


def _cleanup_old(keep_days: int):
    now = datetime.datetime.now()
    for fn in os.listdir(LOGS_DIR):
        m = os.path.splitext(fn)[0].rsplit("-", 3)
        if len(m) == 4 and m[0] == "operations":
            try:
                fd = datetime.date(int(m[1]), int(m[2]), int(m[3]))
                if (now.date() - fd).days > keep_days:
                    os.remove(os.path.join(LOGS_DIR, fn))
            except Exception:
                pass


def read_logs(days: int = 7) -> list:
    """读取近 N 天日志"""
    out = []
    for i in range(days):
        d = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        f = os.path.join(LOGS_DIR, f"operations-{d}.log")
        if os.path.exists(f):
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    out.append(line.strip())
    return out[::-1]  # 最新在前


def export_logs_csv(start_date: str, end_date: str, out_dir: str = None) -> str:
    """按时间范围导出 CSV，返回文件路径"""
    out_dir = out_dir or LOGS_DIR
    out_file = os.path.join(out_dir, f"audit_{start_date}_{end_date}.csv")
    rows = [["时间", "级别", "操作", "用户", "任务ID", "信息"]]
    try:
        sd = datetime.date.fromisoformat(start_date)
        ed = datetime.date.fromisoformat(end_date)
    except Exception:
        sd = ed = datetime.date.today()
    cur = sd
    while cur <= ed:
        f = os.path.join(LOGS_DIR, f"operations-{cur.isoformat()}.log")
        if os.path.exists(f):
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.strip().split(" | ")
                    if len(parts) == 6:
                        rows.append(parts)
        cur += datetime.timedelta(days=1)
    with open(out_file, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)
    log("log_export", f"导出审计CSV: {out_file} 共{len(rows)-1}条")
    return out_file


def tail(lines: int = 100) -> list:
    """实时日志末尾 N 行"""
    all_lines = read_logs(days=1)
    return all_lines[-lines:] if lines < len(all_lines) else all_lines
