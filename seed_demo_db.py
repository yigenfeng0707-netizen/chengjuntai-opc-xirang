# -*- coding: utf-8 -*-
"""演示库：若 bid_telecom.db 缺失或空表，写入最小可问数样本。"""

import os
import sys
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import db as _db

DB_PATH = _db.DB_PATH

DEMO_ROWS = [
    (
        "杭州智慧政务云平台扩容采购",
        "云服务",
        "杭州",
        "2025-11-12",
        1280.5,
        "中标",
        "demo",
    ),
    (
        "宁波市教育城域网升级工程",
        "通信工程",
        "宁波",
        "2025-12-03",
        860.0,
        "中标",
        "demo",
    ),
    (
        "温州政务网络安全等保加固",
        "网络安全",
        "温州",
        "2026-01-18",
        420.3,
        "中标",
        "demo",
    ),
    ("嘉兴物联网感知平台二期", "物联网", "嘉兴", "2026-02-09", 310.0, "进行中", "demo"),
    (
        "金华市数据中心机房改造",
        "IDC数据中心",
        "金华",
        "2026-03-01",
        1560.0,
        "中标",
        "demo",
    ),
    (
        "台州视频会议指挥调度系统",
        "视频会议",
        "台州",
        "2026-03-22",
        198.6,
        "未中标",
        "demo",
    ),
    (
        "绍兴数字政府一网通办优化",
        "政企信息化",
        "绍兴",
        "2026-04-15",
        675.2,
        "中标",
        "demo",
    ),
    (
        "杭州5G专网政企试点项目",
        "通信工程",
        "杭州",
        "2026-05-06",
        920.0,
        "进行中",
        "demo",
    ),
    (
        "宁波智慧城市大脑算力扩容",
        "智慧城市",
        "宁波",
        "2026-05-28",
        2100.0,
        "中标",
        "demo",
    ),
    ("温州电子政务云迁移服务", "云服务", "温州", "2026-06-10", 455.8, "中标", "demo"),
    (
        "嘉兴网络安全态势感知平台",
        "网络安全",
        "嘉兴",
        "2026-06-25",
        388.0,
        "进行中",
        "demo",
    ),
    ("金华智慧校园信息化采购", "智慧教育", "金华", "2026-07-02", 266.4, "中标", "demo"),
]


def ensure_demo_db(db_path: str = None, force: bool = False) -> dict:
    """Create / fill demo database. Returns {path, created, row_count, seeded}."""
    path = db_path or DB_PATH
    created = not os.path.exists(path) if _db.is_sqlite() else False
    if _db.is_sqlite():
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = _db.get_conn()
    conn.execute(_db.get_schema_ddl())
    cur = conn.execute("SELECT COUNT(*) FROM bid_projects")
    count = cur.fetchone()[0]
    seeded = False
    if force or count == 0:
        if force:
            conn.execute("DELETE FROM bid_projects")
        conn.executemany(
            "INSERT INTO bid_projects (project_name, industry, region, bid_date, win_amount, status, owner_user_id) "
            "VALUES (?,?,?,?,?,?,?)",
            DEMO_ROWS,
        )
        conn.commit()
        seeded = True
        cur = conn.execute("SELECT COUNT(*) FROM bid_projects")
        count = cur.fetchone()[0]
    conn.close()
    return {
        "path": path,
        "created": created,
        "seeded": seeded,
        "row_count": count,
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    info = ensure_demo_db(force="--force" in sys.argv)
    print(info)
