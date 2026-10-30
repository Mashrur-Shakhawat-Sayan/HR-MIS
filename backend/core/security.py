"""Passwords, sessions and login throttling.

* Passwords: PBKDF2-HMAC-SHA256, 200,000 iterations, per-user random salt.
* Sessions: random 256-bit bearer token; only its SHA-256 hash is stored.
* Throttling: after MAX_LOGIN_ATTEMPTS failures in 15 minutes the username is locked out temporarily.
"""
import hashlib
import hmac
import os
import secrets
import threading
import time
from datetime import datetime, timedelta

from .. import config
from . import rbac

ITERATIONS = 200_000
_failures = {}
_lock = threading.Lock()


def hash_password(password):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password, stored):
    try:
        _, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, AttributeError):
        return False


def password_problem(password):
    """Return a message if the password is too weak, else None."""
    if len(password or "") < 8:
        return "Password must be at least 8 characters."
    if password.isdigit() or password.isalpha():
        return "Password must contain both letters and numbers."
    return None


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn, user_id, ip):
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(timespec="seconds"),))
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, ip) VALUES (?,?,?,?,?)",
        (_hash_token(token), user_id, now.isoformat(timespec="seconds"),
         (now + timedelta(hours=config.SESSION_HOURS)).isoformat(timespec="seconds"), ip),
    )
    return token


def end_session(conn, header):
    token = header[7:] if header.startswith("Bearer ") else ""
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))


def authenticate(conn, header):
    """Resolve an Authorization header to a user dict (with permissions) or None."""
    if not header.startswith("Bearer "):
        return None
    row = conn.execute(
        """SELECT u.id, u.username, u.role, u.emp_id, u.must_change_pw, u.is_active, s.expires_at,
                  e.full_name, e.code AS emp_code
             FROM sessions s JOIN users u ON u.id = s.user_id
             LEFT JOIN employees e ON e.id = u.emp_id
            WHERE s.token_hash = ?""",
        (_hash_token(header[7:]),),
    ).fetchone()
    if not row or not row["is_active"] or row["expires_at"] < datetime.now().isoformat(timespec="seconds"):
        return None
    row["permissions"] = sorted(rbac.permissions_for(row["role"]))
    return row


def throttled(username):
    with _lock:
        now = time.time()
        attempts = [t for t in _failures.get(username, []) if now - t < 900]
        _failures[username] = attempts
        return len(attempts) >= config.MAX_LOGIN_ATTEMPTS


def record_failure(username):
    with _lock:
        _failures.setdefault(username, []).append(time.time())


def clear_failures(username):
    with _lock:
        _failures.pop(username, None)
