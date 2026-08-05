# -*- coding: utf-8 -*-
"""
Migrate data from SQLite (bid_telecom.db) to PostgreSQL.

Usage:
    python migrate_sqlite_to_pg.py                    # migrate from local bid_telecom.db
    python migrate_sqlite_to_pg.py --source /path/to/bid_telecom.db
    python migrate_sqlite_to_pg.py --dry-run           # preview without writing

Prerequisites:
    - PostgreSQL running and accessible (DATABASE_URL or PG_HOST env vars)
    - psycopg2 installed: pip install psycopg2-binary
    - Source SQLite file exists with bid_projects table
"""

import os
import sys
import argparse
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import db as _db

DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, "bid_telecom.db")


def migrate(sqlite_path: str, dry_run: bool = False) -> dict:
    if _db.is_sqlite():
        return {
            "error": "Target engine is SQLite, not PostgreSQL. Set DATABASE_URL or config database.engine=postgresql first."
        }

    if not os.path.exists(sqlite_path):
        return {"error": f"SQLite file not found: {sqlite_path}"}

    # Read all rows from SQLite
    sq_conn = sqlite3.connect(sqlite_path)
    sq_conn.row_factory = sqlite3.Row
    try:
        sq_rows = sq_conn.execute(
            "SELECT project_name, industry, region, bid_date, win_amount, status, owner_user_id FROM bid_projects"
        ).fetchall()
    except Exception as e:
        sq_conn.close()
        return {"error": f"Failed to read SQLite: {e}"}
    sq_conn.close()

    total = len(sq_rows)
    print(f"[INFO] Source SQLite: {sqlite_path}")
    print(f"[INFO] Rows to migrate: {total}")

    if dry_run:
        print("[DRY-RUN] Skipping write to PostgreSQL.")
        return {"dry_run": True, "rows_found": total}

    if total == 0:
        print("[WARN] No rows in source SQLite. Nothing to migrate.")
        return {"migrated": 0, "total": 0}

    # Write to PostgreSQL
    pg_conn = _db.get_conn()

    # Ensure schema exists
    pg_conn.execute(_db.get_schema_ddl())
    pg_conn.commit()

    # Clear existing data (fresh migration)
    pg_conn.execute("DELETE FROM bid_projects")
    pg_conn.commit()
    print("[INFO] Cleared existing PostgreSQL bid_projects table.")

    # Batch insert
    rows_data = [
        (
            r["project_name"],
            r["industry"],
            r["region"],
            r["bid_date"],
            r["win_amount"],
            r["status"],
            r["owner_user_id"],
        )
        for r in sq_rows
    ]
    pg_conn.executemany(
        "INSERT INTO bid_projects (project_name, industry, region, bid_date, win_amount, status, owner_user_id) "
        "VALUES (?,?,?,?,?,?,?)",
        rows_data,
    )
    pg_conn.commit()

    # Verify
    cur = pg_conn.execute("SELECT COUNT(*) FROM bid_projects")
    pg_count = cur.fetchone()[0]
    cur2 = pg_conn.execute(
        "SELECT COUNT(*) FROM bid_projects WHERE owner_user_id=?", ("real",)
    )
    real_count = cur2.fetchone()[0]
    cur3 = pg_conn.execute(
        "SELECT COUNT(*) FROM bid_projects WHERE owner_user_id=?", ("demo",)
    )
    demo_count = cur3.fetchone()[0]
    pg_conn.close()

    print(
        f"[OK] Migration complete: {pg_count} rows in PostgreSQL (real={real_count}, demo={demo_count})"
    )
    return {
        "migrated": pg_count,
        "source_rows": total,
        "real_count": real_count,
        "demo_count": demo_count,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate SQLite bid_telecom.db to PostgreSQL"
    )
    parser.add_argument(
        "--source", default=DEFAULT_SQLITE_PATH, help="Path to source SQLite file"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without writing"
    )
    args = parser.parse_args()

    result = migrate(args.source, dry_run=args.dry_run)
    print(result)
