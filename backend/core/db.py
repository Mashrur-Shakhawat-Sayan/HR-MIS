"""SQLite access layer.

One connection per request (see core/http.py). Rows are returned as plain
dicts. `insert`/`update` only accept identifier-safe column names; values
are always bound as parameters, never formatted into SQL.
"""
import os
import re
import sqlite3

from .. import config

SCHEMA_VERSION = 1
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _dict_factory(cursor, row):
    return {d[0]: row[i] for i, d in enumerate(cursor.description)}


def connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def ident(name):
    if not _IDENT.match(name):
        raise ValueError(f"Unsafe identifier: {name}")
    return name


def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return None if row is None else next(iter(row.values()))


def insert(conn, table, data):
    cols = [ident(c) for c in data]
    sql = f"INSERT INTO {ident(table)} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    return conn.execute(sql, list(data.values())).lastrowid


def update(conn, table, row_id, data, key="id"):
    if not data:
        return
    sets = ", ".join(f"{ident(c)} = ?" for c in data)
    conn.execute(f"UPDATE {ident(table)} SET {sets} WHERE {ident(key)} = ?", [*data.values(), row_id])


def init_database():
    """Create folders and tables; returns True when the database was newly created."""
    for d in (config.DATA_DIR, config.UPLOAD_DIR, config.BACKUP_DIR):
        os.makedirs(d, exist_ok=True)
    fresh = not os.path.exists(config.DB_PATH)
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        with open(config.SCHEMA_FILE, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.commit()
        empty = scalar(conn, "SELECT COUNT(*) FROM users") == 0
    finally:
        conn.close()
    return fresh or empty
