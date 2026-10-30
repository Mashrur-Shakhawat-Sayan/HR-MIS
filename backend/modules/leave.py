"""Leave management: types, requests & approval workflow, balances, adjustments, calendar.

Workflow:  Pending ──approve──▶ Approved ──cancel──▶ Cancelled
                    └─reject──▶ Rejected
Approving marks the working days as LV in attendance; cancelling/rejecting removes them.
Line managers (team.view + leave.approve) can only decide on their direct reports; nobody
can approve their own request.

Endpoints
---------
/api/leave-types                         generic CRUD (leave.manage)
GET  /api/leave/requests                 ?status, emp_id, mine=1
POST /api/leave/requests                 apply {leave_type_id, from_date, to_date, reason, half_day, emp_id?}
POST /api/leave/requests/{id}/decision   {decision: Approved|Rejected, remarks}
POST /api/leave/requests/{id}/cancel
GET  /api/leave/balances                 ?year, emp_id
GET  /api/leave/calendar                 ?month   approved leave overlapping the month
GET  /api/leave/adjustments | POST /api/leave/adjustments | DELETE /api/leave/adjustments/{id}
GET  /api/leave/preview                  ?leave_type_id&from_date&to_date&half_day  -> days + balance
"""
from ..core import audit, db, rbac
from ..core.http import ApiError, route
from ..core.resource import Resource
from ..core.utils import DATE_RX, Calendar, Field, daterange, month_bounds, now, today

Resource("leave-types", "leave_types",
         [Field("name", required=True), Field("days_per_year", "real", required=True, label="Days per year"),
          Field("gender", choices=["Any", "Female", "Male"], default="Any"), Field("paid", "bool", default=1),
          Field("calendar_days", "bool", default=0, label="Count calendar days"), Field("carry_forward", "bool", default=0),
          Field("max_carry", "real", default=0), Field("active", "bool", default=1), Field("color")],
         None, "leave.manage", order="t.id", label="Leave type")

REQ_SELECT = """SELECT r.*, t.name AS leave_type, t.paid, e.full_name, e.code, e.manager_id, d.name AS department
                  FROM leave_requests r JOIN leave_types t ON t.id = r.leave_type_id
                  JOIN employees e ON e.id = r.emp_id LEFT JOIN departments d ON d.id = e.dept_id"""


def count_days(cal, ltype, start, end, half_day=False):
    if not (DATE_RX.match(start or "") and DATE_RX.match(end or "")) or end < start:
        raise ApiError(400, "Choose a valid date range")
    if ltype["calendar_days"]:
        n = len(list(daterange(start, end)))
    else:
        n = len(cal.workdays(start, end))
    if half_day:
        if start != end:
            raise ApiError(400, "Half-day leave must be a single date")
        n = 0.5 if n else 0
    return n


def balances_for(conn, emp_id, year):
    emp = db.one(conn, "SELECT gender FROM employees WHERE id = ?", (emp_id,))
    if not emp:
        return []
    out = []
    for t in db.q(conn, "SELECT * FROM leave_types WHERE active = 1 ORDER BY id"):
        if t["gender"] != "Any" and t["gender"] != emp["gender"]:
            continue
        used = db.scalar(conn, "SELECT COALESCE(SUM(days),0) FROM leave_requests WHERE emp_id=? AND leave_type_id=? AND status='Approved' AND substr(from_date,1,4)=?",
                         (emp_id, t["id"], str(year)))
        pending = db.scalar(conn, "SELECT COALESCE(SUM(days),0) FROM leave_requests WHERE emp_id=? AND leave_type_id=? AND status='Pending' AND substr(from_date,1,4)=?",
                            (emp_id, t["id"], str(year)))
        adj = db.scalar(conn, "SELECT COALESCE(SUM(days),0) FROM leave_adjustments WHERE emp_id=? AND leave_type_id=? AND year=?",
                        (emp_id, t["id"], year))
        entitled = (t["days_per_year"] or 0) + adj
        out.append({"leave_type_id": t["id"], "leave_type": t["name"], "paid": t["paid"], "color": t["color"],
                    "entitled": entitled, "adjustment": adj, "used": used, "pending": pending,
                    "remaining": entitled - used if t["days_per_year"] else None})
    return out


def _mark(conn, cal, r, on):
    for day in cal.workdays(r["from_date"], r["to_date"]):
        if on:
            conn.execute("""INSERT INTO attendance (emp_id, date, status, source, note) VALUES (?,?,'LV','Leave',?)
                            ON CONFLICT(emp_id, date) DO UPDATE SET status='LV', check_in=NULL, check_out=NULL, source='Leave', note=excluded.note""",
                         (r["emp_id"], day, f"Leave #{r['id']}"))
        else:
            conn.execute("DELETE FROM attendance WHERE emp_id = ? AND date = ? AND status = 'LV'", (r["emp_id"], day))


def _get(req, rid):
    r = db.one(req.db, REQ_SELECT + " WHERE r.id = ?", (rid,))
    if not r:
        raise ApiError(404, "Leave request not found")
    return r


@route("GET", "/api/leave/requests", ["leave.view_all", "leave.approve", "self.leave"])
def list_requests(req):
    where, params = [], []
    if req.q("mine"):
        where.append("r.emp_id = ?")
        params.append(req.user.get("emp_id") or -1)
    else:
        scope = rbac.scope_emp_ids(req.db, req.user, "leave.view_all")
        if scope is not None:
            where.append(f"r.emp_id IN ({','.join('?' * len(scope)) or 'NULL'})")
            params += scope
    for key, col in (("status", "r.status"), ("emp_id", "r.emp_id"), ("leave_type_id", "r.leave_type_id")):
        if req.q(key):
            where.append(f"{col} = ?")
            params.append(req.q(key))
    if req.q("year"):
        where.append("substr(r.from_date,1,4) = ?")
        params.append(req.q("year"))
    sql = REQ_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY r.status = 'Pending' DESC, r.from_date DESC"
    rows = db.q(req.db, sql, params)
    me = req.user.get("emp_id")
    for r in rows:
        r["can_decide"] = r["status"] == "Pending" and r["emp_id"] != me and rbac.has(req.user, "leave.approve") and \
            (rbac.has(req.user, "leave.view_all") or r["manager_id"] == me)
    return {"items": rows}


@route("GET", "/api/leave/preview", ["self.leave", "leave.manage"])
def preview(req):
    t = db.one(req.db, "SELECT * FROM leave_types WHERE id = ?", (req.q("leave_type_id"),))
    if not t:
        raise ApiError(400, "Choose a leave type")
    emp_id = int(req.q("emp_id") or req.user.get("emp_id") or 0)
    days = count_days(Calendar(req.db), t, req.q("from_date"), req.q("to_date"), req.q("half_day") in ("1", "true"))
    bal = next((b for b in balances_for(req.db, emp_id, int(req.q("from_date")[:4])) if b["leave_type_id"] == t["id"]), None)
    return {"days": days, "balance": bal, "calendar_days": bool(t["calendar_days"])}


@route("POST", "/api/leave/requests", ["self.leave", "leave.manage"])
def apply(req):
    b = req.body
    emp_id = int(b.get("emp_id") or req.user.get("emp_id") or 0)
    if not emp_id:
        raise ApiError(400, "Choose an employee")
    on_behalf = emp_id != req.user.get("emp_id")
    if on_behalf and not rbac.has(req.user, "leave.manage"):
        raise ApiError(403, "You can only apply leave for yourself.")
    t = db.one(req.db, "SELECT * FROM leave_types WHERE id = ? AND active = 1", (b.get("leave_type_id"),))
    if not t:
        raise ApiError(400, "Choose a leave type")
    emp = db.one(req.db, "SELECT gender, full_name FROM employees WHERE id = ?", (emp_id,))
    if t["gender"] != "Any" and emp and emp["gender"] != t["gender"]:
        raise ApiError(400, f"{t['name']} leave is only available to {t['gender'].lower()} employees.")
    cal = Calendar(req.db)
    start, end = b.get("from_date"), b.get("to_date") or b.get("from_date")
    days = count_days(cal, t, start, end, bool(b.get("half_day")))
    if days <= 0:
        raise ApiError(400, "The selected dates contain no working days.")
    clash = db.one(req.db, """SELECT id FROM leave_requests WHERE emp_id = ? AND status IN ('Pending','Approved')
                              AND from_date <= ? AND to_date >= ?""", (emp_id, end, start))
    if clash:
        raise ApiError(409, "These dates overlap another leave request.")
    bal = next((x for x in balances_for(req.db, emp_id, int(start[:4])) if x["leave_type_id"] == t["id"]), None)
    if bal and bal["remaining"] is not None and days > bal["remaining"] - bal["pending"] and not (b.get("force") and rbac.has(req.user, "leave.manage")):
        raise ApiError(400, f"Not enough {t['name']} leave: {max(0, bal['remaining'] - bal['pending'])} day(s) available.")
    approve_now = bool(b.get("approve")) and rbac.has(req.user, "leave.manage") and on_behalf
    rid = db.insert(req.db, "leave_requests", {
        "emp_id": emp_id, "leave_type_id": t["id"], "from_date": start, "to_date": end, "days": days,
        "reason": b.get("reason"), "status": "Approved" if approve_now else "Pending", "applied_at": now(),
        "applied_by": req.user["username"], "decided_by": req.user["username"] if approve_now else None,
        "decided_at": now() if approve_now else None})
    if approve_now:
        _mark(req.db, cal, _get(req, rid), True)
    audit.log(req, "create", "leave_requests", rid, f"{t['name']} leave {start}–{end} ({days} d) for {emp['full_name'] if emp else emp_id}")
    return _get(req, rid)


@route("POST", "/api/leave/requests/{id}/decision", "leave.approve")
def decide(req):
    r = _get(req, req.int_param())
    decision = req.body.get("decision")
    if decision not in ("Approved", "Rejected"):
        raise ApiError(400, "Decision must be Approved or Rejected")
    if r["status"] != "Pending":
        raise ApiError(409, f"This request is already {r['status'].lower()}.")
    if r["emp_id"] == req.user.get("emp_id"):
        raise ApiError(403, "You cannot decide on your own leave request.")
    if not rbac.has(req.user, "leave.view_all") and r["manager_id"] != req.user.get("emp_id"):
        raise ApiError(403, "You can only decide on leave for your direct reports.")
    db.update(req.db, "leave_requests", r["id"], {"status": decision, "decided_by": req.user["username"],
                                                  "decided_at": now(), "remarks": req.body.get("remarks")})
    if decision == "Approved":
        _mark(req.db, Calendar(req.db), r, True)
    audit.log(req, "update", "leave_requests", r["id"], f"{decision} leave of {r['full_name']}")
    return _get(req, r["id"])


@route("POST", "/api/leave/requests/{id}/cancel", ["self.leave", "leave.manage"])
def cancel(req):
    r = _get(req, req.int_param())
    own = r["emp_id"] == req.user.get("emp_id")
    if not own and not rbac.has(req.user, "leave.manage"):
        raise ApiError(403, "You can only cancel your own leave.")
    if r["status"] not in ("Pending", "Approved"):
        raise ApiError(409, "Only pending or approved leave can be cancelled.")
    if own and not rbac.has(req.user, "leave.manage") and r["status"] == "Approved" and r["from_date"] <= today():
        raise ApiError(409, "Leave that has already started can only be cancelled by HR.")
    if r["status"] == "Approved":
        _mark(req.db, Calendar(req.db), r, False)
    db.update(req.db, "leave_requests", r["id"], {"status": "Cancelled", "decided_by": req.user["username"], "decided_at": now()})
    audit.log(req, "update", "leave_requests", r["id"], f"Cancelled leave of {r['full_name']}")
    return {"ok": True}


@route("GET", "/api/leave/balances", ["leave.view_all", "self.leave"])
def balances(req):
    year = int(req.q("year", today()[:4]))
    if req.q("emp_id"):
        emp_id = int(req.q("emp_id"))
        if not rbac.can_see_employee(req.db, req.user, emp_id, "leave.view_all"):
            raise ApiError(403, "You do not have permission to see this balance.")
        return {"year": year, "items": balances_for(req.db, emp_id, year)}
    scope = rbac.scope_emp_ids(req.db, req.user, "leave.view_all")
    sql = """SELECT e.id, e.code, e.full_name, e.gender, d.name AS department FROM employees e
               LEFT JOIN departments d ON d.id = e.dept_id WHERE e.status IN ('Active','On Notice')"""
    params = []
    if scope is not None:
        sql += f" AND e.id IN ({','.join('?' * len(scope)) or 'NULL'})"
        params = scope
    emps = db.q(req.db, sql + " ORDER BY e.code", params)
    for e in emps:
        e["balances"] = balances_for(req.db, e["id"], year)
    types = db.q(req.db, "SELECT id, name, gender, days_per_year FROM leave_types WHERE active = 1 ORDER BY id")
    return {"year": year, "types": types, "items": emps}


@route("GET", "/api/leave/calendar", ["leave.view_all", "leave.approve", "self.leave"])
def leave_calendar(req):
    start, end, _ = month_bounds(req.q("month", today()[:7]))
    scope = rbac.scope_emp_ids(req.db, req.user, "leave.view_all")
    sql = REQ_SELECT + " WHERE r.status = 'Approved' AND r.from_date <= ? AND r.to_date >= ?"
    params = [end, start]
    if scope is not None:
        sql += f" AND r.emp_id IN ({','.join('?' * len(scope)) or 'NULL'})"
        params += scope
    return {"items": db.q(req.db, sql + " ORDER BY r.from_date", params)}


@route("GET", "/api/leave/adjustments", "leave.view_all")
def list_adjustments(req):
    return {"items": db.q(req.db, """SELECT a.*, e.full_name, e.code, t.name AS leave_type FROM leave_adjustments a
                                       JOIN employees e ON e.id = a.emp_id JOIN leave_types t ON t.id = a.leave_type_id
                                      ORDER BY a.year DESC, a.id DESC""")}


@route("POST", "/api/leave/adjustments", "leave.manage")
def add_adjustment(req):
    b = req.body
    try:
        data = {"emp_id": int(b["emp_id"]), "leave_type_id": int(b["leave_type_id"]), "year": int(b.get("year") or today()[:4]),
                "days": float(b["days"]), "note": b.get("note"), "created_by": req.user["username"], "created_at": now()}
    except (KeyError, ValueError, TypeError):
        raise ApiError(400, "Employee, leave type and days are required")
    aid = db.insert(req.db, "leave_adjustments", data)
    audit.log(req, "create", "leave_adjustments", aid, f"Leave adjustment {data['days']:+} days", data)
    return {"id": aid}


@route("DELETE", "/api/leave/adjustments/{id}", "leave.manage")
def delete_adjustment(req):
    req.db.execute("DELETE FROM leave_adjustments WHERE id = ?", (req.int_param(),))
    audit.log(req, "delete", "leave_adjustments", req.int_param(), "Deleted leave adjustment")
    return {"ok": True}
