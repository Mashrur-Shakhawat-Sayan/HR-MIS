"""Employee lifecycle: career events, onboarding/offboarding checklists, disciplinary actions.

Recording an event APPLIES it to the employee record:

  Promotion     -> designation_id, grade, optional gross_salary
  Transfer      -> dept_id, unit_id, manager_id
  Increment     -> gross_salary (or increment_pct)
  Confirmation  -> emp_type = Permanent, confirm_date
  Resignation / Termination / Retirement -> status, exit_date, exit_reason (+ offboarding checklist)
  Re-hire       -> status Active, exit cleared

Endpoints
---------
POST   /api/employees/{id}/events     record & apply an event        (lifecycle.manage)
GET    /api/lifecycle/events          recent events (?emp_id, type)   (lifecycle.view)
DELETE /api/lifecycle/events/{id}     delete history entry (no revert)
GET    /api/lifecycle/tasks           open checklist items (?emp_id, category, open=1)
POST   /api/employees/{id}/tasks      add checklist item
PUT    /api/tasks/{id}                update / tick item
DELETE /api/tasks/{id}
GET    /api/lifecycle/confirmations-due  probationers whose probation has ended or ends within 30 days
/api/disciplinary                     generic CRUD
"""
from ..core import audit, db
from ..core.http import ApiError, route
from ..core.resource import Resource
from ..core.utils import Field, add_days, get_settings, now, today
from ..core.utils import DAILY_JOBS
from .employees import check_reporting_line, get_employee

EVENT_TYPES = ["Promotion", "Transfer", "Increment", "Confirmation", "Resignation", "Termination", "Retirement", "Re-hire"]
OFFBOARDING = [
    ("Accept resignation / issue termination letter", "HR"), ("Knowledge handover to line manager", "Line Manager"),
    ("Return laptop, phone, SIM and other assets", "IT / Admin"), ("Return ID card and access card", "Admin"),
    ("Disable email and system accounts", "IT"), ("Clear outstanding loans and advances", "Accounts"),
    ("Calculate final settlement (salary, leave encashment, PF)", "Payroll"), ("Exit interview", "HR"),
    ("Issue experience / release certificate", "HR"),
]


def _label(conn, table, col, value):
    if not value:
        return None
    row = db.one(conn, f"SELECT {col} AS v FROM {table} WHERE id = ?", (value,))
    return row["v"] if row else None


@route("POST", "/api/employees/{id}/events", "lifecycle.manage")
def record_event(req):
    emp_id = req.int_param()
    emp = get_employee(req.db, emp_id)
    b = req.body
    kind = b.get("event_type")
    if kind not in EVENT_TYPES:
        raise ApiError(400, "Choose a valid event type")
    eff = b.get("effective_date") or today()
    changes, old_v, new_v = {}, None, None

    if kind == "Promotion":
        if not b.get("designation_id"):
            raise ApiError(400, "Choose the new designation")
        changes["designation_id"] = int(b["designation_id"])
        g = db.one(req.db, "SELECT title, grade FROM designations WHERE id = ?", (changes["designation_id"],))
        changes["grade"] = b.get("grade") or (g["grade"] if g else emp["grade"])
        old_v, new_v = emp["designation"], g["title"] if g else None
        if b.get("gross_salary"):
            changes["gross_salary"] = float(b["gross_salary"])
            new_v += f" · gross {emp['gross_salary']:,.0f} → {changes['gross_salary']:,.0f}"
    elif kind == "Transfer":
        for k in ("dept_id", "unit_id", "manager_id"):
            if b.get(k):
                changes[k] = int(b[k])
        if not changes:
            raise ApiError(400, "Choose the new department, unit or manager")
        if changes.get("manager_id"):
            check_reporting_line(req.db, emp_id, changes["manager_id"])
        old_v = f"{emp['department'] or '-'} / {emp['unit_name'] or '-'}"
        new_v = f"{_label(req.db, 'departments', 'name', changes.get('dept_id')) or emp['department']} / " \
                f"{_label(req.db, 'business_units', 'name', changes.get('unit_id')) or emp['unit_name']}"
    elif kind == "Increment":
        cur = float(emp["gross_salary"] or 0)
        if b.get("increment_pct"):
            new = round(cur * (1 + float(b["increment_pct"]) / 100) / 10) * 10
        elif b.get("gross_salary"):
            new = float(b["gross_salary"])
        else:
            raise ApiError(400, "Enter the new gross salary or an increment percentage")
        changes["gross_salary"] = new
        old_v, new_v = f"{cur:,.0f}", f"{new:,.0f} ({(new - cur) / cur * 100 if cur else 0:+.1f}%)"
    elif kind == "Confirmation":
        changes = {"emp_type": "Permanent", "confirm_date": eff}
        old_v, new_v = emp["emp_type"], "Permanent"
    elif kind in ("Resignation", "Termination", "Retirement"):
        status = {"Resignation": "Resigned", "Termination": "Terminated", "Retirement": "Retired"}[kind]
        exit_date = b.get("exit_date") or eff
        changes = {"status": "On Notice" if exit_date > today() else status, "exit_date": exit_date,
                   "exit_reason": b.get("details") or kind}
        if exit_date <= today():
            disable_login(req.db, emp_id)
        old_v, new_v = emp["status"], f"{status} (last working day {exit_date})"
        for task, owner in OFFBOARDING:
            db.insert(req.db, "emp_tasks", {"emp_id": emp_id, "category": "Offboarding", "task": task, "owner": owner,
                                            "due_date": exit_date, "done": 0})
    elif kind == "Re-hire":
        changes = {"status": "Active", "exit_date": None, "exit_reason": None, "join_date": eff}
        old_v, new_v = emp["status"], "Active"

    changes["updated_at"] = now()
    db.update(req.db, "employees", emp_id, changes)
    ev_id = db.insert(req.db, "emp_events", {"emp_id": emp_id, "event_type": kind, "effective_date": eff,
                                             "old_value": old_v, "new_value": new_v, "details": b.get("details"),
                                             "created_by": req.user["username"], "created_at": now()})
    audit.log(req, "create", "emp_events", ev_id, f"{kind} recorded for {emp['code']}", changes)
    return {"ok": True, "event_id": ev_id}


FINAL_STATUS = {"Resignation": "Resigned", "Termination": "Terminated", "Retirement": "Retired"}


def disable_login(conn, emp_id):
    conn.execute("UPDATE users SET is_active = 0 WHERE emp_id = ?", (emp_id,))
    conn.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE emp_id = ?)", (emp_id,))


def apply_due_exits(conn):
    """Daily job: employees "On Notice" whose last working day has passed get their final status and lose app access."""
    for r in db.q(conn, "SELECT id FROM employees WHERE status = 'On Notice' AND exit_date IS NOT NULL AND exit_date < ?", (today(),)):
        ev = db.one(conn, """SELECT event_type FROM emp_events WHERE emp_id = ? AND event_type IN ('Resignation','Termination','Retirement')
                              ORDER BY effective_date DESC, id DESC LIMIT 1""", (r["id"],))
        conn.execute("UPDATE employees SET status = ?, updated_at = ? WHERE id = ?",
                     (FINAL_STATUS.get(ev["event_type"] if ev else None, "Resigned"), now(), r["id"]))
        disable_login(conn, r["id"])


DAILY_JOBS.append(apply_due_exits)


@route("GET", "/api/lifecycle/events", "lifecycle.view")
def list_events(req):
    where, params = [], []
    if req.q("emp_id"):
        where.append("v.emp_id = ?")
        params.append(req.q("emp_id"))
    if req.q("type"):
        where.append("v.event_type = ?")
        params.append(req.q("type"))
    sql = """SELECT v.*, e.full_name, e.code FROM emp_events v JOIN employees e ON e.id = v.emp_id""" + \
          (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY v.effective_date DESC, v.id DESC LIMIT 500"
    return {"items": db.q(req.db, sql, params)}


@route("DELETE", "/api/lifecycle/events/{id}", "lifecycle.manage")
def delete_event(req):
    req.db.execute("DELETE FROM emp_events WHERE id = ?", (req.int_param(),))
    audit.log(req, "delete", "emp_events", req.int_param(), "Deleted career history entry")
    return {"ok": True}


# ---------------------------------------------------------------- checklists
TASK_FIELDS = [Field("category", choices=["Onboarding", "Offboarding", "Other"], default="Onboarding"),
               Field("task", required=True), Field("owner"), Field("due_date", "date"), Field("done", "bool")]


@route("GET", "/api/lifecycle/tasks", "lifecycle.view")
def list_tasks(req):
    where, params = [], []
    if req.q("emp_id"):
        where.append("t.emp_id = ?")
        params.append(req.q("emp_id"))
    if req.q("category"):
        where.append("t.category = ?")
        params.append(req.q("category"))
    if req.q("open"):
        where.append("t.done = 0")
    sql = """SELECT t.*, e.full_name, e.code FROM emp_tasks t JOIN employees e ON e.id = t.emp_id""" + \
          (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY t.done, t.due_date, t.id"
    return {"items": db.q(req.db, sql, params)}


@route("POST", "/api/employees/{id}/tasks", "lifecycle.manage")
def add_task(req):
    emp_id = req.int_param()
    get_employee(req.db, emp_id)
    data = clean_task(req.body)
    data["emp_id"] = emp_id
    return {"id": db.insert(req.db, "emp_tasks", data)}


def clean_task(body, partial=False):
    from ..core.utils import clean
    return clean(TASK_FIELDS, body, partial)


@route("PUT", "/api/tasks/{id}", "lifecycle.manage")
def update_task(req):
    data = clean_task(req.body, partial=True)
    if "done" in data:
        data["done_at"] = now() if data["done"] else None
    db.update(req.db, "emp_tasks", req.int_param(), data)
    return {"ok": True}


@route("DELETE", "/api/tasks/{id}", "lifecycle.manage")
def delete_task(req):
    req.db.execute("DELETE FROM emp_tasks WHERE id = ?", (req.int_param(),))
    return {"ok": True}


@route("GET", "/api/lifecycle/confirmations-due", "lifecycle.view")
def confirmations_due(req):
    months = int(get_settings(req.db)["probation_months"])
    rows = db.q(req.db, """SELECT e.id, e.code, e.full_name, e.join_date, d.name AS department, g.title AS designation
                             FROM employees e LEFT JOIN departments d ON d.id = e.dept_id
                             LEFT JOIN designations g ON g.id = e.designation_id
                            WHERE e.emp_type = 'Probation' AND e.status IN ('Active','On Notice') ORDER BY e.join_date""")
    horizon = add_days(today(), 30)
    out = []
    for r in rows:
        y, m, dd = map(int, r["join_date"].split("-"))
        m += months
        y += (m - 1) // 12
        m = (m - 1) % 12 + 1
        due = f"{y}-{m:02d}-{min(dd, 28):02d}"
        if due <= horizon:
            r["due_date"] = due
            r["overdue"] = due < today()
            out.append(r)
    return {"items": out}


Resource("disciplinary", "disciplinary",
         [Field("emp_id", "fk", required=True, label="Employee"), Field("action_date", "date", required=True, label="Date"),
          Field("action_type", required=True, label="Action",
                choices=["Verbal Warning", "Written Warning", "Show Cause", "Suspension", "Final Warning", "Termination"]),
          Field("reason"), Field("issued_by"), Field("status", choices=["Open", "Replied", "Closed"], default="Open"),
          Field("resolution")],
         "lifecycle.view", "lifecycle.manage", timestamps=True,
         select="SELECT t.*, e.full_name, e.code FROM disciplinary t JOIN employees e ON e.id = t.emp_id",
         search=("e.full_name", "e.code", "t.action_type", "t.reason"), filters=("t.emp_id", "t.status"),
         order="t.action_date DESC", label="Disciplinary record")
