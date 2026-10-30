"""Attendance and holiday calendar.

Status codes: P present · L late · HD half day · A absent · LV on leave · WFH work from home · OD on official duty

Endpoints
---------
GET  /api/attendance/daily?date=            day sheet for all visible employees
PUT  /api/attendance/daily                  {date, records:[{emp_id,status,check_in,check_out,note}]}  (attendance.manage)
POST /api/attendance/mark-all               {date}  mark everyone not yet marked as present
GET  /api/attendance/register?month=        monthly register grid + totals
GET  /api/attendance/export?month=          register as CSV
POST /api/attendance/import                 {csv}  bulk import (biometric/device export)
GET  /api/attendance/my?month=              own attendance (self-service)
POST /api/attendance/clock                  {action: in|out}  self check-in / check-out
/api/holidays                               generic CRUD (everyone can view)
"""
import csv
import io
from datetime import datetime

from ..core import audit, db, rbac
from ..core.http import ApiError, Response, route
from ..core.resource import Resource
from ..core.utils import DATE_RX, TIME_RX, Calendar, Field, month_bounds, today

STATUS = {"P": "Present", "L": "Late", "HD": "Half day", "A": "Absent", "LV": "On leave", "WFH": "Work from home", "OD": "On duty"}
PRESENTISH = {"P", "L", "HD", "WFH", "OD"}

Resource("holidays", "holidays",
         [Field("date", "date", required=True), Field("name", required=True),
          Field("type", choices=["National", "Religious", "Company", "Optional"], default="National")],
         None, "holidays.manage", search=("t.name",), order="t.date", label="Holiday")


def eligible(conn, on_date, scope=None):
    sql = """SELECT e.id, e.code, e.full_name, d.name AS department, g.title AS designation
               FROM employees e LEFT JOIN departments d ON d.id = e.dept_id LEFT JOIN designations g ON g.id = e.designation_id
              WHERE e.join_date <= ? AND (e.exit_date IS NULL OR e.exit_date >= ?)
                AND (e.status IN ('Active','On Notice') OR e.exit_date IS NOT NULL)"""
    params = [on_date, on_date]
    if scope is not None:
        sql += f" AND e.id IN ({','.join('?' * len(scope)) or 'NULL'})"
        params += scope
    return db.q(conn, sql + " ORDER BY e.code", params)


def monthly_stats(conn, month, emp_ids=None, cal=None):
    """{emp_id: {P,L,HD,A,LV,WFH,OD, workdays, pct}} for the month up to today."""
    start, end, _ = month_bounds(month)
    cal = cal or Calendar(conn)
    last = min(end, today())
    params = [start, end]
    sql = "SELECT emp_id, date, status FROM attendance WHERE date BETWEEN ? AND ?"
    if emp_ids is not None:
        sql += f" AND emp_id IN ({','.join('?' * len(emp_ids)) or 'NULL'})"
        params += list(emp_ids)
    out = {}
    emps = {e["id"]: e for e in db.q(conn, "SELECT id, join_date, exit_date FROM employees")}
    for r in db.q(conn, sql, params):
        s = out.setdefault(r["emp_id"], {k: 0 for k in STATUS})
        if r["status"] in s:
            s[r["status"]] += 1
    targets = emp_ids if emp_ids is not None else list(emps)
    workdays = cal.workdays(start, last) if start <= last else []
    for eid in targets:
        e = emps.get(eid)
        if not e:
            continue
        s = out.setdefault(eid, {k: 0 for k in STATUS})
        wd = [x for x in workdays if x >= e["join_date"] and not (e["exit_date"] and x > e["exit_date"])]
        s["workdays"] = len(wd)
        s["pct"] = round(min(100.0, (s["P"] + s["L"] + s["WFH"] + s["OD"] + s["LV"] + s["HD"] * 0.5) / len(wd) * 100), 1) if wd else 0
    return out


@route("GET", "/api/attendance/daily", ["attendance.view_all", "team.view"])
def daily(req):
    day = req.q("date", today())
    if not DATE_RX.match(day):
        raise ApiError(400, "Invalid date")
    cal = Calendar(req.db)
    scope = rbac.scope_emp_ids(req.db, req.user, "attendance.view_all")
    rows = eligible(req.db, day, scope)
    recs = {r["emp_id"]: r for r in db.q(req.db, "SELECT * FROM attendance WHERE date = ?", (day,))}
    leaves = {r["emp_id"]: r["name"] for r in db.q(req.db, """SELECT r.emp_id, t.name FROM leave_requests r JOIN leave_types t ON t.id = r.leave_type_id
                                                              WHERE r.status = 'Approved' AND ? BETWEEN r.from_date AND r.to_date""", (day,))}
    summary = {k: 0 for k in STATUS}
    summary["unmarked"] = 0
    for r in rows:
        a = recs.get(r["id"], {})
        r.update(status=a.get("status") or "", check_in=a.get("check_in"), check_out=a.get("check_out"),
                 note=a.get("note"), source=a.get("source"), leave_type=leaves.get(r["id"]))
        summary[r["status"] if r["status"] else "unmarked"] += 1
    return {"date": day, "workday": cal.is_workday(day), "holiday": cal.holidays.get(day),
            "weekend": datetime.fromisoformat(day).weekday() in cal.weekend, "rows": rows, "summary": summary,
            "work_start": cal.settings["work_start"], "work_end": cal.settings["work_end"], "grace": cal.settings["grace_minutes"]}


def upsert(conn, cal, emp_id, day, status, check_in=None, check_out=None, note=None, source="Manual"):
    if status and status not in STATUS:
        raise ApiError(400, f"Unknown attendance status {status}")
    for t in (check_in, check_out):
        if t and not TIME_RX.match(t):
            raise ApiError(400, "Times must be HH:MM")
    if not status and check_in:
        status = "P"
    if status in ("P", "L") and check_in:
        status = "L" if cal.is_late(check_in) else "P"
    if status in ("A", "LV"):
        check_in = check_out = None
    if not status:
        conn.execute("DELETE FROM attendance WHERE emp_id = ? AND date = ?", (emp_id, day))
        return
    conn.execute("""INSERT INTO attendance (emp_id, date, status, check_in, check_out, note, source) VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(emp_id, date) DO UPDATE SET status=excluded.status, check_in=excluded.check_in,
                    check_out=excluded.check_out, note=excluded.note, source=excluded.source""",
                 (emp_id, day, status, check_in, check_out, note, source))


@route("PUT", "/api/attendance/daily", "attendance.manage")
def save_daily(req):
    day = req.body.get("date")
    if not DATE_RX.match(day or ""):
        raise ApiError(400, "Invalid date")
    cal = Calendar(req.db)
    n = 0
    future = day > today()
    for r in req.body.get("records", []):
        if future and (r.get("status") or "") in ("P", "L", "HD", "A"):
            raise ApiError(400, "For future dates you can only record leave, work from home or on duty.")
        upsert(req.db, cal, int(r["emp_id"]), day, r.get("status") or "", r.get("check_in") or None,
               r.get("check_out") or None, r.get("note") or None)
        n += 1
    audit.log(req, "update", "attendance", None, f"Saved {n} attendance record(s) for {day}")
    return {"ok": True, "saved": n}


@route("POST", "/api/attendance/mark-all", "attendance.manage")
def mark_all(req):
    day = req.body.get("date") or today()
    if day > today():
        raise ApiError(400, "Attendance can't be marked as present for a future date.")
    cal = Calendar(req.db)
    marked = {r["emp_id"] for r in db.q(req.db, "SELECT emp_id FROM attendance WHERE date = ?", (day,))}
    n = 0
    for e in eligible(req.db, day):
        if e["id"] not in marked:
            upsert(req.db, cal, e["id"], day, "P", cal.settings["work_start"],
                   cal.settings["work_end"] if day < today() else None)
            n += 1
    audit.log(req, "update", "attendance", None, f"Marked {n} employee(s) present on {day}")
    return {"ok": True, "marked": n}


def _register(req, month):
    start, end, n_days = month_bounds(month)
    cal = Calendar(req.db)
    scope = rbac.scope_emp_ids(req.db, req.user, "attendance.view_all")
    emps = [e for e in eligible(req.db, end, scope)]
    # include people who left during the month
    left = db.q(req.db, "SELECT id, code, full_name FROM employees WHERE exit_date BETWEEN ? AND ? AND status NOT IN ('Active','On Notice')", (start, end))
    ids = {e["id"] for e in emps}
    emps += [l for l in left if l["id"] not in ids and (scope is None or l["id"] in scope)]
    cells = {}
    for r in db.q(req.db, "SELECT emp_id, date, status, check_in, check_out FROM attendance WHERE date BETWEEN ? AND ?", (start, end)):
        cells.setdefault(r["emp_id"], {})[r["date"]] = r["status"]
    days = []
    for i in range(1, n_days + 1):
        ds = f"{month}-{i:02d}"
        wd = datetime.fromisoformat(ds).weekday()
        days.append({"date": ds, "day": i, "dow": "MTWTFSS"[wd], "type": "H" if ds in cal.holidays else ("W" if wd in cal.weekend else ""),
                     "holiday": cal.holidays.get(ds)})
    stats = monthly_stats(req.db, month, [e["id"] for e in emps], cal)
    for e in emps:
        e["cells"] = cells.get(e["id"], {})
        e["totals"] = stats.get(e["id"], {})
    return {"month": month, "days": days, "rows": emps}


@route("GET", "/api/attendance/register", ["attendance.view_all", "team.view"])
def register(req):
    return _register(req, req.q("month", today()[:7]))


@route("GET", "/api/attendance/export", ["attendance.view_all", "team.view"])
def export(req):
    data = _register(req, req.q("month", today()[:7]))
    head = ["Employee ID", "Name"] + [str(d["day"]) for d in data["days"]] + ["Present", "Late", "Half day", "Absent", "Leave", "WFH", "On duty", "Working days", "Attendance %"]
    rows = [head]
    for e in data["rows"]:
        t = e["totals"]
        rows.append([e["code"], e["full_name"]] + [e["cells"].get(d["date"], d["type"]) for d in data["days"]] +
                    [t.get(k, 0) for k in ("P", "L", "HD", "A", "LV", "WFH", "OD")] + [t.get("workdays", 0), t.get("pct", 0)])
    return Response.csv(f"attendance-{data['month']}.csv", rows)


@route("POST", "/api/attendance/import", "attendance.manage")
def import_csv(req):
    text = str(req.body.get("csv", ""))
    cal = Calendar(req.db)
    codes = {r["code"].lower(): r["id"] for r in db.q(req.db, "SELECT id, code FROM employees")}
    ok, errors = 0, []
    for i, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        if not row or not "".join(row).strip():
            continue
        row = [c.strip() for c in row] + ["", "", "", ""]
        code, day, cin, cout, status = row[:5]
        if i == 1 and not DATE_RX.match(day):
            continue  # header line
        emp_id = codes.get(code.lower())
        if not emp_id:
            errors.append(f"Line {i}: unknown employee ID '{code}'")
            continue
        if not DATE_RX.match(day):
            errors.append(f"Line {i}: date must be YYYY-MM-DD")
            continue
        try:
            upsert(req.db, cal, emp_id, day, status.upper() if status else ("P" if cin else "A"), cin[:5] or None, cout[:5] or None, None, "Import")
            ok += 1
        except ApiError as e:
            errors.append(f"Line {i}: {e.message}")
    audit.log(req, "create", "attendance", None, f"Imported {ok} attendance row(s)")
    return {"imported": ok, "errors": errors[:50]}


@route("GET", "/api/attendance/my", "self.attendance")
def my_attendance(req):
    if not req.user.get("emp_id"):
        raise ApiError(404, "Your account is not linked to an employee record.")
    month = req.q("month", today()[:7])
    start, end, _ = month_bounds(month)
    rows = db.q(req.db, "SELECT date, status, check_in, check_out, note FROM attendance WHERE emp_id = ? AND date BETWEEN ? AND ? ORDER BY date",
                (req.user["emp_id"], start, end))
    stats = monthly_stats(req.db, month, [req.user["emp_id"]]).get(req.user["emp_id"], {})
    today_rec = db.one(req.db, "SELECT * FROM attendance WHERE emp_id = ? AND date = ?", (req.user["emp_id"], today()))
    return {"month": month, "rows": rows, "totals": stats, "today": today_rec, "is_workday": Calendar(req.db).is_workday(today())}


@route("POST", "/api/attendance/clock", "self.attendance")
def clock(req):
    emp_id = req.user.get("emp_id")
    if not emp_id:
        raise ApiError(404, "Your account is not linked to an employee record.")
    action = req.body.get("action")
    now_t = datetime.now().strftime("%H:%M")
    cal = Calendar(req.db)
    rec = db.one(req.db, "SELECT * FROM attendance WHERE emp_id = ? AND date = ?", (emp_id, today()))
    if action == "in":
        if rec and rec.get("check_in"):
            raise ApiError(400, f"You already checked in at {rec['check_in']}.")
        upsert(req.db, cal, emp_id, today(), "P", now_t, None, None, "Self")
    elif action == "out":
        if not rec or not rec.get("check_in"):
            raise ApiError(400, "Check in first.")
        req.db.execute("UPDATE attendance SET check_out = ? WHERE id = ?", (now_t, rec["id"]))
    else:
        raise ApiError(400, "Unknown action")
    return {"ok": True, "time": now_t}
