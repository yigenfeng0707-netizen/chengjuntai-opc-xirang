# -*- coding: utf-8 -*-
"""
模块12：操作日志导出（鲁棒增强版）
1. 记录全部人员操作、任务启动、文件修改、同步事件
2. 支持按时间范围筛选日志
3. 一键导出日志为 CSV 文件，用于审计追溯
4. 日志按天滚动分割，防止单个日志文件过大

鲁棒增强：
  · 线程锁：避免多线程并发写入交错/半行
  · 全链路 try/except：任何磁盘 IO 失败都不抛异常
  · 单条 message 超长截断：避免单条日志爆大
  · 懒清理：不是每次写都做清理，改为每 N 次做一次（降低 IO 抖动）
"""
import os
import csv
import threading
import datetime
from config_loader import LOGS_DIR, load_config

OP_LOG_FILE = os.path.join(LOGS_DIR, "operations.log")
_LOG_LOCK = threading.RLock()
_WRITE_COUNTER = {"n": 0}
_CLEANUP_EVERY = 50  # 每写入 50 条才触发一次过期清理
_MAX_MSG_LEN = 2000  # 单条 message 最大 2000 字符


def _ensure_log_dir() -> bool:
    try:
        if not os.path.isdir(LOGS_DIR):
            os.makedirs(LOGS_DIR, exist_ok=True)
        return True
    except Exception:
        return False


def log(action: str, message: str, level: str = "INFO", task_id: str = None, user: str = ""):
    """记录操作日志（按天滚动文件名）；该函数 **永远不抛出异常**。"""
    try:
        if not _ensure_log_dir():
            return
        # 参数安全化
        act = (str(action or "")[:80]).replace("\n", " ").replace("\r", " ")
        lvl = (str(level or "INFO")[:10]).upper()
        uid = (str(user or "-")[:64]).replace("\n", " ")
        tid = (str(task_id or "-")[:80]).replace("\n", " ").replace("\r", " ")
        msg = str(message or "")
        if len(msg) > _MAX_MSG_LEN:
            msg = msg[: _MAX_MSG_LEN - 3] + "..."
        msg = msg.replace("\n", "\\n").replace("\r", "\\r")

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        cur_file = os.path.join(LOGS_DIR, f"operations-{today}.log")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | {lvl} | {act} | {uid} | {tid} | {msg}\n"

        # 加锁写入，避免交叉
        with _LOG_LOCK:
            # 日文件
            try:
                with open(cur_file, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass
            # 同步写主日志（兼容旧引用）
            try:
                with open(OP_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass
            # 懒清理过期
            try:
                _WRITE_COUNTER["n"] = int(_WRITE_COUNTER.get("n") or 0) + 1
                if _WRITE_COUNTER["n"] % _CLEANUP_EVERY == 0:
                    try:
                        roll_days = int(load_config().get("log_roll_days", 30))
                    except Exception:
                        roll_days = 30
                    _cleanup_old(roll_days)
            except Exception:
                pass
    except Exception:
        # 最终兜底：任何日志写入错误都绝对不能影响主流程
        return


def _cleanup_old(keep_days: int):
    """过期日志清理；任何错误静默忽略。"""
    try:
        keep = int(keep_days or 30)
        if keep <= 0:
            keep = 30
    except Exception:
        keep = 30
    now = datetime.datetime.now()
    try:
        files = os.listdir(LOGS_DIR)
    except Exception:
        return
    for fn in files:
        try:
            base = os.path.splitext(fn)[0]
            m = base.rsplit("-", 3)
            if len(m) == 4 and m[0] == "operations":
                try:
                    y, mo, d = int(m[1]), int(m[2]), int(m[3])
                    if not (1970 <= y <= 9999 and 1 <= mo <= 12 and 1 <= d <= 31):
                        continue
                    fd = datetime.date(y, mo, d)
                    if (now.date() - fd).days > keep:
                        try:
                            os.remove(os.path.join(LOGS_DIR, fn))
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            continue


def read_logs(days: int = 7) -> list:
    """读取近 N 天日志；任何错误返回 []，不抛异常。"""
    out = []
    try:
        n = int(days or 7)
        if n <= 0:
            n = 7
        if n > 365:
            n = 365
    except Exception:
        n = 7
    for i in range(n):
        try:
            d = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            f = os.path.join(LOGS_DIR, f"operations-{d}.log")
            if not os.path.exists(f):
                continue
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        s = line.strip()
                        if s:
                            out.append(s)
            except Exception:
                continue
        except Exception:
            continue
    try:
        return out[::-1]  # 最新在前
    except Exception:
        return out


def export_logs_csv(start_date: str, end_date: str, out_dir: str = None) -> str:
    """按时间范围导出 CSV，返回文件路径；失败返回空串，不抛异常。"""
    try:
        out_dir = out_dir or LOGS_DIR
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception:
                out_dir = LOGS_DIR
        out_file = os.path.join(out_dir, f"audit_{start_date}_{end_date}.csv")
        rows = [["时间", "级别", "操作", "用户", "任务ID", "信息"]]
        try:
            sd = datetime.date.fromisoformat(str(start_date or ""))
            ed = datetime.date.fromisoformat(str(end_date or ""))
        except Exception:
            sd = ed = datetime.date.today()
        if sd > ed:
            sd, ed = ed, sd
        cur = sd
        max_iter_days = 3660
        iters = 0
        while cur <= ed and iters < max_iter_days:
            iters += 1
            try:
                f = os.path.join(LOGS_DIR, f"operations-{cur.isoformat()}.log")
                if os.path.exists(f):
                    try:
                        with open(f, "r", encoding="utf-8", errors="replace") as fh:
                            for line in fh:
                                parts = line.rstrip("\n").split(" | ")
                                if len(parts) >= 6:
                                    rows.append(parts[:6])
                    except Exception:
                        pass
            except Exception:
                pass
            cur += datetime.timedelta(days=1)
        try:
            with open(out_file, "w", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerows(rows)
        except Exception:
            return ""
        try:
            log("log_export", f"导出审计CSV: {out_file} 共{max(0, len(rows)-1)}条")
        except Exception:
            pass
        return out_file
    except Exception:
        return ""


def tail(lines: int = 100) -> list:
    """实时日志末尾 N 行；失败返回 []，不抛异常。
    read_logs 已是最新在前，取前 n 条即为最新 N 行。
    """
    try:
        n = int(lines or 100)
        if n <= 0:
            n = 100
        if n > 2000:
            n = 2000
    except Exception:
        n = 100
    try:
        all_lines = read_logs(days=1)
    except Exception:
        return []
    try:
        if n < len(all_lines):
            return all_lines[:n]  # 最新在前，取前 n 条
        return all_lines
    except Exception:
        return all_lines or []
