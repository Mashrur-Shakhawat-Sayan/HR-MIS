"""Authentication and user-account management.

Endpoints
---------
POST /api/auth/login              {username, password}         -> {token, user}
POST /api/auth/logout
GET  /api/auth/me                                              -> current user + permissions + company
POST /api/auth/change-password    {current_password, new_password}
GET  /api/users                   (users.manage)
POST /api/users                   (users.manage) {username, password, role, emp_id}
PUT  /api/users/{id}              (users.manage) {role, emp_id, is_active}
POST /api/users/{id}/reset-password (users.manage) {password}
GET  /api/roles                   role catalogue with permissions
"""
from ..core import audit, db, rbac, security
from ..core.http import ApiError, route
from ..core.utils import get_settings, now


def _public_user(conn, user):
    s = get_settings(conn)
    return {
        "id": user["id"], "username": user["username"], "role": user["role"],
        "role_label": rbac.ROLES.get(user["role"], {}).get("label", user["role"]),
        "emp_id": user["emp_id"], "full_name": user.get("full_name") or user["username"],
        "emp_code": user.get("emp_code"), "must_change_pw": bool(user["must_change_pw"]),
        "permissions": sorted(rbac.permissions_for(user["role"])),
        "company": {"name": s["company_name"], "short": s["company_short"], "currency": s["currency_symbol"]},
    }


@route("POST", "/api/auth/login", auth=False)
def login(req):
    username = str(req.body.get("username", "")).strip().lower()
    password = str(req.body.get("password", ""))
    if security.throttled(username):
        raise ApiError(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    user = db.one(req.db, """SELECT u.*, e.full_name, e.code AS emp_code FROM users u
                             LEFT JOIN employees e ON e.id = u.emp_id WHERE u.username = ?""", (username,))
    if not user or not security.verify_password(password, user["password_hash"]):
        security.record_failure(username)
        raise ApiError(401, "Incorrect username or password.")
    if not user["is_active"]:
        raise ApiError(403, "This account is disabled. Contact HR.")
    security.clear_failures(username)
    token = security.create_session(req.db, user["id"], req.ip)
    req.db.execute("UPDATE users SET last_login = ? WHERE id = ?", (now(), user["id"]))
    req.user = user
    audit.log(req, "login", "users", user["id"], "Signed in")
    return {"token": token, "user": _public_user(req.db, user)}


@route("POST", "/api/auth/logout")
def logout(req):
    security.end_session(req.db, req.headers.get("Authorization", ""))
    return {"ok": True}


@route("GET", "/api/auth/me")
def me(req):
    return _public_user(req.db, req.user)


@route("POST", "/api/auth/change-password")
def change_password(req):
    row = db.one(req.db, "SELECT password_hash FROM users WHERE id = ?", (req.user["id"],))
    if not security.verify_password(str(req.body.get("current_password", "")), row["password_hash"]):
        raise ApiError(400, "Current password is incorrect.")
    new = str(req.body.get("new_password", ""))
    problem = security.password_problem(new)
    if problem:
        raise ApiError(400, problem)
    req.db.execute("UPDATE users SET password_hash = ?, must_change_pw = 0 WHERE id = ?",
                   (security.hash_password(new), req.user["id"]))
    audit.log(req, "update", "users", req.user["id"], "Changed own password")
    return {"ok": True}


# ---------------------------------------------------------------- user admin
USER_SELECT = """SELECT u.id, u.username, u.role, u.emp_id, u.is_active, u.must_change_pw, u.last_login, u.created_at,
                        e.full_name, e.code AS emp_code
                   FROM users u LEFT JOIN employees e ON e.id = u.emp_id"""


@route("GET", "/api/roles")
def roles(req):
    return {"roles": [{"key": k, "label": v["label"], "permissions": sorted(rbac.permissions_for(k))} for k, v in rbac.ROLES.items()],
            "permissions": rbac.PERMISSIONS}


@route("GET", "/api/users", "users.manage")
def list_users(req):
    return {"items": db.q(req.db, USER_SELECT + " ORDER BY u.username")}


def _check_role(role):
    if role not in rbac.ROLES:
        raise ApiError(400, "Unknown role")


@route("POST", "/api/users", "users.manage")
def create_user(req):
    b = req.body
    username = str(b.get("username", "")).strip().lower()
    if not username:
        raise ApiError(400, "Username is required")
    _check_role(b.get("role", "employee"))
    problem = security.password_problem(str(b.get("password", "")))
    if problem:
        raise ApiError(400, problem)
    uid = db.insert(req.db, "users", {
        "username": username, "password_hash": security.hash_password(b["password"]), "role": b.get("role", "employee"),
        "emp_id": b.get("emp_id") or None, "is_active": 1, "must_change_pw": 1, "created_at": now()})
    audit.log(req, "create", "users", uid, f"Created user {username} ({b.get('role')})")
    return db.one(req.db, USER_SELECT + " WHERE u.id = ?", (uid,))


@route("PUT", "/api/users/{id}", "users.manage")
def update_user(req):
    uid = req.int_param()
    b = req.body
    data = {}
    target = db.one(req.db, "SELECT id, role, is_active FROM users WHERE id = ?", (uid,))
    if not target:
        raise ApiError(404, "User not found")
    if "role" in b:
        _check_role(b["role"])
        if uid == req.user["id"] and b["role"] != target["role"]:
            raise ApiError(400, "You cannot change your own role. Ask another administrator.")
        data["role"] = b["role"]
    if "emp_id" in b:
        data["emp_id"] = b["emp_id"] or None
    if "is_active" in b:
        if uid == req.user["id"] and not b["is_active"]:
            raise ApiError(400, "You cannot disable your own account.")
        data["is_active"] = 1 if b["is_active"] else 0
    losing_admin = target["role"] == "admin" and target["is_active"] and (data.get("role", "admin") != "admin" or data.get("is_active") == 0)
    if losing_admin and db.scalar(req.db, "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?", (uid,)) == 0:
        raise ApiError(400, "This is the last active administrator. Make someone else an administrator first.")
    db.update(req.db, "users", uid, data)
    if data.get("is_active") == 0:
        req.db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
    audit.log(req, "update", "users", uid, "Updated user account", data)
    return db.one(req.db, USER_SELECT + " WHERE u.id = ?", (uid,))


@route("POST", "/api/users/{id}/reset-password", "users.manage")
def reset_password(req):
    uid = req.int_param()
    pw = str(req.body.get("password", ""))
    problem = security.password_problem(pw)
    if problem:
        raise ApiError(400, problem)
    req.db.execute("UPDATE users SET password_hash = ?, must_change_pw = 1 WHERE id = ?", (security.hash_password(pw), uid))
    req.db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
    audit.log(req, "update", "users", uid, "Reset password")
    return {"ok": True}
