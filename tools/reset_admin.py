"""Emergency: reset (or re-create) the `admin` account to password Admin@123.

Stop HR-MIS first, then run from the project folder:   python tools/reset_admin.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import config  # noqa: E402
from backend.core import db, security  # noqa: E402
from backend.core.utils import now  # noqa: E402

if not os.path.exists(config.DB_PATH):
    sys.exit(f"No database at {config.DB_PATH}")
conn = db.connect()
pw = security.hash_password("Admin@123")
if db.one(conn, "SELECT id FROM users WHERE username = 'admin'"):
    conn.execute("UPDATE users SET password_hash = ?, is_active = 1, must_change_pw = 1, role = 'admin' WHERE username = 'admin'", (pw,))
else:
    db.insert(conn, "users", {"username": "admin", "password_hash": pw, "role": "admin", "is_active": 1, "must_change_pw": 1, "created_at": now()})
conn.execute("DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE username = 'admin')")
conn.commit()
conn.close()
print("admin password reset to Admin@123 — you will be asked to change it after signing in.")
