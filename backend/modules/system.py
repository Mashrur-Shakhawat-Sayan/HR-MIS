"""System administration: settings, audit trail, backups, system information.

Endpoints
---------
GET  /api/settings              all settings (settings.manage) — public subset via /api/auth/me
PUT  /api/settings              {key: value, ...}
GET  /api/audit                 ?q, entity, username, from, to, limit
GET  /api/system/info           version, counts, database size
GET  /api/system/backup         download a consistent copy of the database
POST /api/system/backup         save a copy into data/backups on the server
"""
import os
import sqlite3
import tempfile
from datetime import datetime

from .. import config
from ..core import audit, db
from ..core.http import ApiError, Response, route
from ..core.utils import DEFAULT_SETTINGS, get_settings, save_settings

NUMERIC = {k for k, v in DEFAULT_SETTINGS.items() if isinstance(v, (int, float))}


@route("GET", "/api/settings", "settings.manage")
def read_settings(req):
    return get_settings(req.db)


@route("PUT", "/api/settings", "settings.manage")
def write_settings(req):
    values = {}
    for k, v in req.body.items():
        if k not in DEFAULT_SETTINGS:
            continue
        if k in NUMERIC:
            try:
                v = float(v)
                v = int(v) if v.is_integer() else v
            except (TypeError, ValueError):
                raise ApiError(400, f"{k.replace('_', ' ')} must be a number")
            if v < 0:
                raise ApiError(400, f"{k.replace('_', ' ')} cannot be negative")
        if k == "weekend_days":
            v = sorted({int(x) for x in v if 0 <= int(x) <= 6})
        values[k] = v
    merged = {**get_settings(req.db), **values}
    if merged["basic_pct"] + merged["house_rent_pct"] + merged["medical_pct"] > 100:
        raise ApiError(400, "Basic + house rent + medical cannot exceed 100% of gross.")
    for k in ("ot_divisor_hours", "lwp_divisor_days"):
        if not merged[k]:
            raise ApiError(400, f"{k.replace('_', ' ')} must be greater than zero")
    save_settings(req.db, values)
    audit.log(req, "update", "settings", None, "Updated settings", values)
    return get_settings(req.db)


@route("GET", "/api/audit", "audit.view")
def audit_log(req):
    where, params = [], []
    for key, col in (("entity", "entity"), ("username", "username"), ("action", "action")):
        if req.q(key):
            where.append(f"{col} = ?")
            params.append(req.q(key))
    if req.q("from"):
        where.append("ts >= ?")
        params.append(req.q("from"))
    if req.q("to"):
        where.append("ts <= ?")
        params.append(req.q("to") + "T23:59:59")
    if req.q("q"):
        where.append("(summary LIKE ? OR details LIKE ?)")
        params += [f"%{req.q('q')}%"] * 2
    sql = "SELECT id, ts, username, action, entity, entity_id, summary, details, ip FROM audit_log" + \
          (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ?"
    return {"items": db.q(req.db, sql, params + [min(int(req.q("limit", 300)), 2000)]),
            "entities": [r["entity"] for r in db.q(req.db, "SELECT DISTINCT entity FROM audit_log WHERE entity IS NOT NULL ORDER BY entity")]}


@route("GET", "/api/system/info", "settings.manage")
def info(req):
    counts = {t: db.scalar(req.db, f"SELECT COUNT(*) FROM {t}") for t in
              ("employees", "users", "attendance", "leave_requests", "payslips", "claims", "candidates", "assets", "audit_log", "emp_documents")}
    backups = sorted(os.listdir(config.BACKUP_DIR), reverse=True)[:10] if os.path.isdir(config.BACKUP_DIR) else []
    return {"version": config.VERSION, "database": config.DB_PATH, "db_size_kb": round(os.path.getsize(config.DB_PATH) / 1024),
            "counts": counts, "backups": backups, "python": __import__("sys").version.split()[0]}


def _snapshot(path):
    src = sqlite3.connect(config.DB_PATH)
    dst = sqlite3.connect(path)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()


@route("GET", "/api/system/backup", "settings.manage")
def download_backup(req):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _snapshot(path)
        with open(path, "rb") as f:
            data = f.read()
    finally:
        os.remove(path)
    audit.log(req, "export", "system", None, "Downloaded database backup")
    return Response.file(data, f"hrmis-backup-{datetime.now():%Y%m%d-%H%M}.db")


@route("POST", "/api/system/backup", "settings.manage")
def server_backup(req):
    name = f"hrmis-backup-{datetime.now():%Y%m%d-%H%M%S}.db"
    _snapshot(os.path.join(config.BACKUP_DIR, name))
    audit.log(req, "export", "system", None, f"Saved server backup {name}")
    return {"ok": True, "file": name}
