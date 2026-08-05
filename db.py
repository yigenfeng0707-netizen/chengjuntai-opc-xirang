# -*- coding: utf-8 -*-
"""
Unified database connection module.
- PostgreSQL (primary, for production / ECS deployment)
- SQLite (fallback, for local development without PostgreSQL)

Configuration priority:
1. Environment variables: DATABASE_URL or PG_HOST/PG_PORT/PG_DB/PG_USER/PG_PASSWORD
2. config.yaml: database.engine == "postgresql"
3. Default: SQLite (bid_telecom.db)
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_config():
    # 1. Environment variables
    pg_url = os.environ.get("DATABASE_URL")
    if pg_url:
        return {"engine": "postgresql", "url": pg_url}

    pg_host = os.environ.get("PG_HOST") or os.environ.get("POSTGRES_HOST")
    if pg_host:
        return {
            "engine": "postgresql",
            "host": pg_host,
            "port": int(os.environ.get("PG_PORT", "5432")),
            "database": os.environ.get("PG_DB")
            or os.environ.get("POSTGRES_DB", "chengjuntai"),
            "user": os.environ.get("PG_USER")
            or os.environ.get("POSTGRES_USER", "chengjuntai"),
            "password": os.environ.get("PG_PASSWORD")
            or os.environ.get("POSTGRES_PASSWORD", ""),
        }

    # 2. config.yaml
    try:
        import yaml

        for cfg_path in [
            os.path.join(_HERE, "content_factory", "config.yaml"),
            os.path.join(_HERE, "config.yaml"),
        ]:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                db_cfg = cfg.get("database")
                if db_cfg and db_cfg.get("engine") == "postgresql":
                    return db_cfg
                break
    except Exception:
        pass

    # 3. Default: SQLite
    return {"engine": "sqlite"}


_CONFIG = _load_config()
_ENGINE = _CONFIG.get("engine", "sqlite")

DB_PATH = os.path.join(_HERE, "bid_telecom.db")

PH = "%s" if _ENGINE == "postgresql" else "?"


def is_pg():
    return _ENGINE == "postgresql"


def is_sqlite():
    return not is_pg()


def get_engine():
    return _ENGINE


def adapt_sql(sql):
    """Convert ? placeholders to %s for PostgreSQL."""
    if _ENGINE == "postgresql":
        return sql.replace("?", "%s")
    return sql


SCHEMA_SQLITE = """CREATE TABLE IF NOT EXISTS bid_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT,
    industry TEXT,
    region TEXT,
    bid_date TEXT,
    win_amount REAL,
    status TEXT,
    owner_user_id TEXT
)"""

SCHEMA_PG = """CREATE TABLE IF NOT EXISTS bid_projects (
    id SERIAL PRIMARY KEY,
    project_name TEXT,
    industry TEXT,
    region TEXT,
    bid_date TEXT,
    win_amount REAL,
    status TEXT,
    owner_user_id TEXT
)"""


def get_schema_ddl():
    return SCHEMA_PG if is_pg() else SCHEMA_SQLITE


# NL2SQL schema DDL (for LLM system prompt)
SCHEMA_DDL_FOR_PROMPT = (
    """CREATE TABLE bid_projects (
    id SERIAL PRIMARY KEY,
    project_name TEXT,
    industry TEXT,
    region TEXT,
    bid_date TEXT,
    win_amount REAL,
    status TEXT,
    owner_user_id TEXT
);"""
    if is_pg()
    else """CREATE TABLE bid_projects (
    id INTEGER PRIMARY KEY,
    project_name TEXT,
    industry TEXT,
    region TEXT,
    bid_date TEXT,
    win_amount REAL,
    status TEXT,
    owner_user_id TEXT
);"""
)


def sql_extract_year(col):
    """Extract year string from a date column."""
    if is_pg():
        return f"TO_CHAR({col}::date, 'YYYY')"
    return f"strftime('%Y', {col})"


def sql_extract_year_month(col):
    """Extract YYYY-MM from a date column."""
    if is_pg():
        return f"TO_CHAR({col}::date, 'YYYY-MM')"
    return f"strftime('%Y-%m', {col})"


def nl2sql_dialect_name():
    return "PostgreSQL" if is_pg() else "SQLite"


class WrappedConn:
    """Wraps sqlite3 or psycopg2 connection to provide a unified execute() interface.

    For SQLite: conn.execute(sql, params) works natively (returns cursor).
    For PostgreSQL: internally creates a cursor, executes, and returns it.
    """

    def __init__(self, raw_conn, engine):
        self._conn = raw_conn
        self._engine = engine
        self._dict_mode = False

    def execute(self, sql, params=None):
        sql = adapt_sql(sql)
        if self._engine == "postgresql":
            if self._dict_mode:
                from psycopg2.extras import RealDictCursor

                cur = self._conn.cursor(cursor_factory=RealDictCursor)
            else:
                cur = self._conn.cursor()
            cur.execute(sql, params or [])
            return cur
        return self._conn.execute(sql, params or [])

    def executemany(self, sql, params_seq):
        sql = adapt_sql(sql)
        if self._engine == "postgresql":
            cur = self._conn.cursor()
            cur.executemany(sql, params_seq)
            return cur
        return self._conn.executemany(sql, params_seq)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def set_dict_mode(self, enabled=True):
        """Enable dict-like row access (by column name)."""
        self._dict_mode = enabled
        if self._engine == "sqlite" and enabled:
            import sqlite3

            self._conn.row_factory = sqlite3.Row

    @property
    def row_factory(self):
        return getattr(self._conn, "row_factory", None)

    @row_factory.setter
    def row_factory(self, value):
        if self._engine == "sqlite":
            self._conn.row_factory = value
        elif value is not None:
            self._dict_mode = True

    @property
    def raw(self):
        return self._conn


def get_conn():
    """Get a wrapped database connection.

    Returns a WrappedConn with execute(), executemany(), commit(), close().
    For named row access, call conn.set_dict_mode(True).
    """
    if is_pg():
        import psycopg2

        if "url" in _CONFIG:
            raw = psycopg2.connect(_CONFIG["url"])
        else:
            raw = psycopg2.connect(
                host=_CONFIG.get("host", "127.0.0.1"),
                port=_CONFIG.get("port", 5432),
                dbname=_CONFIG.get("database", "chengjuntai"),
                user=_CONFIG.get("user", "chengjuntai"),
                password=_CONFIG.get("password", ""),
            )
        return WrappedConn(raw, "postgresql")
    else:
        import sqlite3

        raw = sqlite3.connect(DB_PATH)
        raw.row_factory = sqlite3.Row
        return WrappedConn(raw, "sqlite")


def ensure_schema(conn=None):
    """Ensure the bid_projects table exists."""
    own = conn is None
    if own:
        conn = get_conn()
    ddl = get_schema_ddl()
    conn.execute(ddl)
    conn.commit()
    if own:
        conn.close()


if __name__ == "__main__":
    print(f"Engine: {_ENGINE}")
    print(f"DB_PATH: {DB_PATH}")
    print(f"Placeholder: {PH}")
    if is_sqlite():
        print(f"SQLite DB exists: {os.path.exists(DB_PATH)}")
    conn = get_conn()
    ensure_schema(conn)
    cnt = conn.execute("SELECT COUNT(*) FROM bid_projects").fetchone()[0]
    conn.close()
    print(f"bid_projects rows: {cnt}")
