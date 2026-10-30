"""Audit trail: who changed what, and when."""
import json
from datetime import datetime


def log(req, action, entity, entity_id=None, summary="", data=None):
    user = req.user or {}
    req.db.execute(
        "INSERT INTO audit_log (ts, user_id, username, action, entity, entity_id, summary, details, ip) VALUES (?,?,?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), user.get("id"), user.get("username"), action, entity,
         entity_id, summary[:300], json.dumps(data, default=str, ensure_ascii=False)[:4000] if data else None, req.ip),
    )
