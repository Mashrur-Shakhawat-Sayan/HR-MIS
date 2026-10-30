"""Employee master data, profiles, documents and self-service profile.

Endpoints
---------
GET    /api/employees                 directory (?q, status, dept_id, unit_id, emp_type)
GET    /api/employees/lookup          lightweight list for dropdowns (any signed-in user)
GET    /api/employees/next-code       next free employee ID
GET    /api/employees/{id}            full profile (own profile allowed for everyone)
POST   /api/employees                 create (+ joining event, onboarding checklist, optional login)
PUT    /api/employees/{id}            update (salary/bank fields need employees.salary)
DELETE /api/employees/{id}            delete (only if no payroll history; otherwise archive)
GET    /api/employees/{id}/documents  list documents
POST   /api/employees/{id}/documents  upload {title, doc_type, filename, content_type, data(base64)}
GET    /api/documents/{id}/download
DELETE /api/documents/{id}
GET    /api/me/profile | PUT /api/me/profile   self-service
"""
import base64
import os
import re
import secrets

from .. import config
from ..core import audit, db, rbac, security
from ..core.http import ApiError, Response, route
from ..core.utils import Field, clean, get_settings, now, today

ACTIVE = ("Active", "On Notice")
STATUSES = ["Active", "On Notice", "Resigned", "Terminated", "Retired"]
TYPES = ["Permanent", "Probation", "Contract", "Intern", "Part-time"]

FIELDS = [
    Field("code", label="Employee ID"), Field("full_name", required=True, label="Full name"),
    Field("gender", choices=["Male", "Female", "Other"]), Field("dob", "date", label="Date of birth"),
    Field("marital_status"), Field("blood_group"), Field("phone"), Field("email"), Field("nid", label="NID"),
    Field("tin", label="e-TIN"), Field("father_name"), Field("mother_name"),
    Field("present_address"), Field("permanent_address"), Field("emergency_name"), Field("emergency_phone"),
    Field("unit_id", "fk", label="Business unit"), Field("dept_id", "fk", label="Department"),
    Field("designation_id", "fk", label="Designation"), Field("grade"),
    Field("emp_type", choices=TYPES, label="Employment type", default="Permanent"),
    Field("join_date", "date", required=True, label="Joining date"), Field("confirm_date", "date", label="Confirmation date"),
    Field("manager_id", "fk", label="Reporting manager"),
    Field("status", choices=STATUSES, default="Active"), Field("exit_date", "date", label="Exit date"), Field("exit_reason"),
    Field("gross_salary", "real", label="Gross salary"), Field("bank_name"), Field("bank_account"),
    Field("pf_member", "bool", label="PF member"),
]
SALARY_FIELDS = {"gross_salary", "bank_name", "bank_account", "pf_member", "tin"}
SELF_EDITABLE = {"phone", "email", "present_address", "permanent_address", "emergency_name", "emergency_phone",
                 "marital_status", "blood_group"}

SELECT = """SELECT e.*, u.name AS unit_name, d.name AS department, g.title AS designation, g.level AS designation_level,
                   m.full_name AS manager_name, m.code AS manager_code
              FROM employees e
              LEFT JOIN business_units u ON u.id = e.unit_id
              LEFT JOIN departments d ON d.id = e.dept_id
              LEFT JOIN designations g ON g.id = e.designation_id
              LEFT JOIN employees m ON m.id = e.manager_id"""


def _redact(req, row):
    if row and not rbac.has(req.user, "employees.salary") and row.get("id") != req.user.get("emp_id"):
        for k in SALARY_FIELDS:
            row.pop(k, None)
        row.pop("nid", None)
    return row


def next_code(conn):
    prefix = get_settings(conn)["employee_code_prefix"] or ""
    best = 1000
    for r in db.q(conn, "SELECT code FROM employees"):
        m = re.search(r"(\d+)$", r["code"] or "")
        if m:
            best = max(best, int(m.group(1)))
    return f"{prefix}{best + 1}"


def check_reporting_line(conn, emp_id, manager_id):
    """Refuse a manager assignment that would make someone report to themselves, directly or indirectly."""
    seen, cur = set(), int(manager_id)
    while cur and cur not in seen and len(seen) < 500:
        if cur == int(emp_id):
            raise ApiError(400, "That manager reports (directly or indirectly) to this employee. Choose someone else to avoid a reporting loop.")
        seen.add(cur)
        row = conn.execute("SELECT manager_id FROM employees WHERE id = ?", (cur,)).fetchone()
        cur = row["manager_id"] if row else None


def get_employee(conn, emp_id):
    row = db.one(conn, SELECT + " WHERE e.id = ?", (emp_id,))
    if not row:
        raise ApiError(404, "Employee not found")
    return row


# ---------------------------------------------------------------- directory
@route("GET", "/api/employees", ["employees.view", "team.view"])
def list_employees(req):
    where, params = [], []
    scope = rbac.scope_emp_ids(req.db, req.user, "employees.view")
    if scope is not None:
        where.append(f"e.id IN ({','.join('?' * len(scope)) or 'NULL'})")
        params += scope
    status = req.q("status", "Active")
    if status == "Active":
        where.append("e.status IN ('Active','On Notice')")
    elif status != "all":
        where.append("e.status = ?")
        params.append(status)
    for key in ("dept_id", "unit_id", "emp_type", "designation_id", "manager_id"):
        if req.q(key):
            where.append(f"e.{key} = ?")
            params.append(req.q(key))
    if req.q("q"):
        where.append("(e.full_name LIKE ? OR e.code LIKE ? OR e.phone LIKE ? OR e.email LIKE ? OR g.title LIKE ?)")
        params += [f"%{req.q('q')}%"] * 5
    sql = SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY e.code"
    return {"items": [_redact(req, r) for r in db.q(req.db, sql, params)]}


@route("GET", "/api/employees/lookup")
def lookup(req):
    cond = "" if req.q("all") else "WHERE e.status IN ('Active','On Notice')"
    return {"items": db.q(req.db, f"""SELECT e.id, e.code, e.full_name, e.gender, e.dept_id, e.manager_id, d.name AS department,
                                             g.title AS designation, e.status
                                        FROM employees e LEFT JOIN departments d ON d.id = e.dept_id
                                        LEFT JOIN designations g ON g.id = e.designation_id {cond} ORDER BY e.full_name""")}


@route("GET", "/api/employees/next-code", "employees.manage")
def get_next_code(req):
    return {"code": next_code(req.db)}


@route("GET", "/api/employees/{id}")
def profile(req):
    emp_id = req.int_param()
    own = emp_id == req.user.get("emp_id")
    if not own and not rbac.can_see_employee(req.db, req.user, emp_id, "employees.view"):
        raise ApiError(403, "You do not have permission to view this employee.")
    row = _redact(req, get_employee(req.db, emp_id))
    from . import leave  # local import avoids a circular import at load time
    row["leave_balance"] = leave.balances_for(req.db, emp_id, int(today()[:4]))
    row["assets"] = db.q(req.db, "SELECT id, tag, name, category, issued_on, status FROM assets WHERE emp_id = ?", (emp_id,))
    can_life = rbac.has(req.user, "lifecycle.view") or own
    row["events"] = db.q(req.db, "SELECT * FROM emp_events WHERE emp_id = ? ORDER BY effective_date DESC, id DESC", (emp_id,)) if can_life else []
    row["tasks"] = db.q(req.db, "SELECT * FROM emp_tasks WHERE emp_id = ? ORDER BY category, id", (emp_id,)) if rbac.has(req.user, "lifecycle.view") else []
    row["disciplinary"] = db.q(req.db, "SELECT * FROM disciplinary WHERE emp_id = ? ORDER BY action_date DESC", (emp_id,)) if rbac.has(req.user, "lifecycle.view") else []
    row["reviews"] = db.q(req.db, "SELECT id, period, score, status FROM reviews WHERE emp_id = ? ORDER BY id DESC", (emp_id,)) \
        if (rbac.has(req.user, "performance.view") or own) else []
    row["documents"] = db.q(req.db, "SELECT id, title, doc_type, filename, size, uploaded_at FROM emp_documents WHERE emp_id = ? ORDER BY id DESC", (emp_id,)) \
        if (rbac.has(req.user, "employees.documents") or own) else []
    row["loans"] = db.q(req.db, "SELECT id, loan_type, principal, installment, status FROM loans WHERE emp_id = ?", (emp_id,)) \
        if (rbac.has(req.user, "loans.view") or own) else []
    row["team"] = db.q(req.db, "SELECT id, code, full_name FROM employees WHERE manager_id = ? AND status IN ('Active','On Notice')", (emp_id,))
    row["user"] = db.one(req.db, "SELECT id, username, role, is_active, last_login FROM users WHERE emp_id = ?", (emp_id,)) \
        if rbac.has(req.user, "users.manage") else None
    return row


# ---------------------------------------------------------------- write
DEFAULT_ONBOARDING = [
    ("Collect signed appointment letter", "HR"), ("Collect NID, photos and academic certificates", "HR"),
    ("Open salary bank account / verify account details", "Accounts"), ("Issue employee ID card", "HR"),
    ("Create email and system accounts", "IT"), ("Issue laptop / equipment", "IT"),
    ("Department induction and introduction to team", "Line Manager"), ("Enrol in provident fund", "Accounts"),
]


def _check_salary_perm(req, data):
    if any(k in data for k in SALARY_FIELDS) and not rbac.has(req.user, "employees.salary"):
        for k in SALARY_FIELDS:
            data.pop(k, None)


@route("POST", "/api/employees", "employees.manage")
def create_employee(req):
    data = clean(FIELDS, req.body)
    _check_salary_perm(req, data)
    data["code"] = data.get("code") or next_code(req.db)
    data.setdefault("gross_salary", 0)
    if data.get("pf_member") is None:
        data["pf_member"] = 0 if data.get("emp_type") == "Intern" else 1
    data["created_at"] = now()
    emp_id = db.insert(req.db, "employees", data)
    db.insert(req.db, "emp_events", {"emp_id": emp_id, "event_type": "Joining", "effective_date": data["join_date"],
                                     "new_value": data.get("emp_type"), "details": "Joined the company",
                                     "created_by": req.user["username"], "created_at": now()})
    for task, owner in DEFAULT_ONBOARDING:
        db.insert(req.db, "emp_tasks", {"emp_id": emp_id, "category": "Onboarding", "task": task, "owner": owner,
                                        "due_date": data["join_date"], "done": 0})
    result = {"employee": get_employee(req.db, emp_id)}
    if req.body.get("create_login"):
        if not rbac.has(req.user, "users.manage"):
            raise ApiError(403, "Only administrators can create login accounts.")
        temp = "Hr" + secrets.token_hex(3) + str(secrets.randbelow(90) + 10)
        uname = data["code"].lower()
        db.insert(req.db, "users", {"username": uname, "password_hash": security.hash_password(temp),
                                    "role": req.body.get("role") or "employee", "emp_id": emp_id, "is_active": 1,
                                    "must_change_pw": 1, "created_at": now()})
        result["login"] = {"username": uname, "temporary_password": temp}
    audit.log(req, "create", "employees", emp_id, f"Created employee {data['code']} {data['full_name']}", data)
    return result


@route("PUT", "/api/employees/{id}", "employees.manage")
def update_employee(req):
    emp_id = req.int_param()
    old = get_employee(req.db, emp_id)
    data = clean(FIELDS, req.body, partial=True)
    _check_salary_perm(req, data)
    if "code" in data and not data["code"]:
        data.pop("code")
    if data.get("manager_id"):
        check_reporting_line(req.db, emp_id, data["manager_id"])
    data["updated_at"] = now()
    db.update(req.db, "employees", emp_id, data)
    new = get_employee(req.db, emp_id)
    # Keep the career history complete even when HR edits the record directly.
    changes = [("designation", "Promotion"), ("department", "Transfer"), ("unit_name", "Transfer")]
    for col, kind in changes:
        if old.get(col) != new.get(col) and old.get(col) and new.get(col):
            db.insert(req.db, "emp_events", {"emp_id": emp_id, "event_type": kind, "effective_date": today(),
                                             "old_value": old[col], "new_value": new[col], "details": "Updated from employee record",
                                             "created_by": req.user["username"], "created_at": now()})
    if "gross_salary" in data and float(old.get("gross_salary") or 0) != float(new.get("gross_salary") or 0):
        db.insert(req.db, "emp_events", {"emp_id": emp_id, "event_type": "Increment", "effective_date": today(),
                                         "old_value": str(old.get("gross_salary")), "new_value": str(new.get("gross_salary")),
                                         "details": "Gross salary changed from employee record",
                                         "created_by": req.user["username"], "created_at": now()})
    audit.log(req, "update", "employees", emp_id, f"Updated employee {new['code']}",
              {k: v for k, v in data.items() if old.get(k) != v and k != "updated_at"})
    return _redact(req, new)


@route("DELETE", "/api/employees/{id}", "employees.manage")
def delete_employee(req):
    emp_id = req.int_param()
    emp = get_employee(req.db, emp_id)
    if db.scalar(req.db, "SELECT COUNT(*) FROM payslips WHERE emp_id = ?", (emp_id,)):
        raise ApiError(409, "This employee has payroll history. Set the status to Resigned/Terminated instead of deleting.")
    for row in db.q(req.db, "SELECT stored_name FROM emp_documents WHERE emp_id = ?", (emp_id,)):
        try:
            os.remove(os.path.join(config.UPLOAD_DIR, row["stored_name"]))
        except OSError:
            pass
    req.db.execute("UPDATE employees SET manager_id = NULL WHERE manager_id = ?", (emp_id,))
    req.db.execute("UPDATE departments SET head_emp_id = NULL WHERE head_emp_id = ?", (emp_id,))
    for t in ("attendance", "leave_requests", "leave_adjustments", "claims", "loans", "training_participants"):
        req.db.execute(f"DELETE FROM {t} WHERE emp_id = ?", (emp_id,))
    req.db.execute("UPDATE reviews SET reviewer_id = NULL WHERE reviewer_id = ?", (emp_id,))
    req.db.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
    audit.log(req, "delete", "employees", emp_id, f"Deleted employee {emp['code']} {emp['full_name']}")
    return {"ok": True}


# ---------------------------------------------------------------- documents
def _doc_access(req, emp_id):
    if emp_id != req.user.get("emp_id") and not rbac.has(req.user, "employees.documents"):
        raise ApiError(403, "You do not have permission to access these documents.")


@route("GET", "/api/employees/{id}/documents")
def list_docs(req):
    emp_id = req.int_param()
    _doc_access(req, emp_id)
    return {"items": db.q(req.db, "SELECT id, title, doc_type, filename, size, uploaded_by, uploaded_at FROM emp_documents WHERE emp_id = ? ORDER BY id DESC", (emp_id,))}


@route("POST", "/api/employees/{id}/documents", "employees.documents")
def upload_doc(req):
    emp_id = req.int_param()
    get_employee(req.db, emp_id)
    b = req.body
    try:
        raw = base64.b64decode(b.get("data", ""), validate=True)
    except ValueError:
        raise ApiError(400, "File data is not valid")
    if not raw:
        raise ApiError(400, "Choose a file to upload")
    filename = os.path.basename(str(b.get("filename") or "document"))
    ext = re.sub(r"[^A-Za-z0-9.]", "", os.path.splitext(filename)[1])[:10]
    stored = f"{emp_id}_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(config.UPLOAD_DIR, stored), "wb") as f:
        f.write(raw)
    doc_id = db.insert(req.db, "emp_documents", {
        "emp_id": emp_id, "title": b.get("title") or filename, "doc_type": b.get("doc_type") or "Other", "filename": filename,
        "stored_name": stored, "size": len(raw), "content_type": b.get("content_type") or "application/octet-stream",
        "uploaded_by": req.user["username"], "uploaded_at": now()})
    audit.log(req, "create", "emp_documents", doc_id, f"Uploaded {filename} for employee #{emp_id}")
    return {"id": doc_id}


@route("GET", "/api/documents/{id}/download")
def download_doc(req):
    doc = db.one(req.db, "SELECT * FROM emp_documents WHERE id = ?", (req.int_param(),))
    if not doc:
        raise ApiError(404, "Document not found")
    _doc_access(req, doc["emp_id"])
    path = os.path.join(config.UPLOAD_DIR, doc["stored_name"])
    if not os.path.isfile(path):
        raise ApiError(404, "The stored file is missing")
    with open(path, "rb") as f:
        return Response.file(f.read(), doc["filename"], doc["content_type"] or "application/octet-stream")


@route("DELETE", "/api/documents/{id}", "employees.documents")
def delete_doc(req):
    doc = db.one(req.db, "SELECT * FROM emp_documents WHERE id = ?", (req.int_param(),))
    if not doc:
        raise ApiError(404, "Document not found")
    req.db.execute("DELETE FROM emp_documents WHERE id = ?", (doc["id"],))
    try:
        os.remove(os.path.join(config.UPLOAD_DIR, doc["stored_name"]))
    except OSError:
        pass
    audit.log(req, "delete", "emp_documents", doc["id"], f"Deleted document {doc['filename']}")
    return {"ok": True}


# ---------------------------------------------------------------- self-service
@route("GET", "/api/me/profile", "self.profile")
def my_profile(req):
    if not req.user.get("emp_id"):
        raise ApiError(404, "Your account is not linked to an employee record.")
    req.params["id"] = str(req.user["emp_id"])
    return profile(req)


@route("PUT", "/api/me/profile", "self.profile")
def update_my_profile(req):
    if not req.user.get("emp_id"):
        raise ApiError(404, "Your account is not linked to an employee record.")
    data = {k: v for k, v in clean(FIELDS, req.body, partial=True).items() if k in SELF_EDITABLE}
    data["updated_at"] = now()
    db.update(req.db, "employees", req.user["emp_id"], data)
    audit.log(req, "update", "employees", req.user["emp_id"], "Updated own profile", data)
    return {"ok": True}
