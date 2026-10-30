"""Dashboard: one call that returns the widgets the signed-in user is allowed to see.

GET /api/dashboard
"""
from ..core import db, rbac
from ..core.http import route
from ..core.utils import Calendar, add_days, current_month, get_settings, today, years_between
from .attendance import PRESENTISH, eligible
from .leave import balances_for


def _attendance_trend(conn, cal, scope):
    out, day = [], today()
    for _ in range(60):
        if len(out) == 7:
            break
        if cal.is_workday(day):
            emps = eligible(conn, day, scope)
            if emps:
                ids = [e["id"] for e in emps]
                rows = db.q(conn, f"SELECT status FROM attendance WHERE date = ? AND emp_id IN ({','.join('?' * len(ids))})", [day] + ids)
                if rows:
                    present = sum(1 for r in rows if r["status"] in PRESENTISH)
                    out.append({"date": day, "pct": round(present / len(emps) * 100, 1), "present": present, "total": len(emps)})
        day = add_days(day, -1)
    return list(reversed(out))


@route("GET", "/api/dashboard")
def dashboard(req):
    conn, u, t = req.db, req.user, today()
    cal = Calendar(conn)
    s = cal.settings
    out = {"today": t, "workday": cal.is_workday(t), "holiday": cal.holidays.get(t), "company": s["company_name"], "widgets": []}

    # --- personal block (everyone with an employee record)
    if u.get("emp_id"):
        me = db.one(conn, """SELECT e.full_name, e.code, g.title AS designation, d.name AS department, e.join_date
                               FROM employees e LEFT JOIN designations g ON g.id = e.designation_id
                               LEFT JOIN departments d ON d.id = e.dept_id WHERE e.id = ?""", (u["emp_id"],))
        out["me"] = me
        out["my_today"] = db.one(conn, "SELECT status, check_in, check_out FROM attendance WHERE emp_id = ? AND date = ?", (u["emp_id"], t))
        out["my_leave"] = balances_for(conn, u["emp_id"], int(t[:4]))
        out["my_pending"] = db.scalar(conn, "SELECT COUNT(*) FROM leave_requests WHERE emp_id = ? AND status = 'Pending'", (u["emp_id"],))

    if not rbac.has(u, "dashboard.view"):
        out["notices"] = db.q(conn, "SELECT * FROM notices WHERE expires_on IS NULL OR expires_on >= ? ORDER BY posted_on DESC LIMIT 5", (t,))
        out["holidays"] = db.q(conn, "SELECT * FROM holidays WHERE date >= ? ORDER BY date LIMIT 5", (t,))
        return out

    team_only = not rbac.has(u, "attendance.view_all")
    att_scope = rbac.scope_emp_ids(conn, u, "attendance.view_all")
    act = eligible(conn, t, att_scope)
    ids = [e["id"] for e in act if not (team_only and e["id"] == u.get("emp_id"))]
    rec = {r["emp_id"]: r["status"] for r in db.q(conn, "SELECT emp_id, status FROM attendance WHERE date = ?", (t,))}
    present = sum(1 for i in ids if rec.get(i) in PRESENTISH)
    late = sum(1 for i in ids if rec.get(i) == "L")
    on_leave = sum(1 for i in ids if rec.get(i) == "LV")
    kpi = {"headcount": len(ids), "present": present, "late": late, "on_leave": on_leave, "team_only": team_only}

    if not team_only:
        kpi["units"] = db.scalar(conn, "SELECT COUNT(*) FROM business_units")
        kpi["departments"] = db.scalar(conn, "SELECT COUNT(*) FROM departments")
        kpi["joiners_month"] = db.scalar(conn, "SELECT COUNT(*) FROM employees WHERE substr(join_date,1,7) = ?", (current_month(),))
        kpi["leavers_year"] = db.scalar(conn, "SELECT COUNT(*) FROM employees WHERE exit_date IS NOT NULL AND substr(exit_date,1,4) = ? AND status NOT IN ('Active','On Notice')", (t[:4],))
    if rbac.has(u, "employees.salary") or rbac.has(u, "payroll.view"):
        kpi["monthly_gross"] = db.scalar(conn, "SELECT COALESCE(SUM(gross_salary),0) FROM employees WHERE status IN ('Active','On Notice')")
        last = db.one(conn, "SELECT month, status FROM payroll_runs ORDER BY month DESC LIMIT 1")
        kpi["last_payroll"] = last
    if rbac.has(u, "recruitment.view"):
        kpi["open_jobs"] = db.scalar(conn, "SELECT COUNT(*) FROM jobs WHERE status = 'Open'")
        kpi["vacancies"] = db.scalar(conn, "SELECT COALESCE(SUM(vacancies),0) FROM jobs WHERE status = 'Open'")
        kpi["pipeline"] = db.scalar(conn, "SELECT COUNT(*) FROM candidates WHERE stage NOT IN ('Hired','Rejected')")
    out["kpi"] = kpi

    # approvals waiting for this user
    approvals = {}
    if rbac.has(u, "leave.approve"):
        sql = """SELECT r.id, r.from_date, r.to_date, r.days, t.name AS leave_type, e.full_name, e.code FROM leave_requests r
                   JOIN leave_types t ON t.id = r.leave_type_id JOIN employees e ON e.id = r.emp_id WHERE r.status = 'Pending'"""
        params = []
        if not rbac.has(u, "leave.view_all"):
            sql += " AND e.manager_id = ?"
            params.append(u.get("emp_id") or -1)
        approvals["leave"] = db.q(conn, sql + " AND r.emp_id != ? ORDER BY r.from_date LIMIT 8", params + [u.get("emp_id") or -1])
    if rbac.has(u, "claims.approve"):
        sql = "SELECT c.id, c.amount, c.category, c.claim_date, e.full_name FROM claims c JOIN employees e ON e.id = c.emp_id WHERE c.status = 'Pending'"
        params = []
        if not rbac.has(u, "claims.view_all"):
            sql += " AND e.manager_id = ?"
            params.append(u.get("emp_id") or -1)
        approvals["claims"] = db.q(conn, sql + " ORDER BY c.claim_date LIMIT 8", params)
    if rbac.has(u, "loans.manage"):
        approvals["loans"] = db.q(conn, "SELECT l.id, l.loan_type, l.principal, e.full_name FROM loans l JOIN employees e ON e.id = l.emp_id WHERE l.status = 'Pending'")
    out["approvals"] = approvals

    out["trend"] = _attendance_trend(conn, cal, att_scope)
    where = "" if not team_only else f" AND e.id IN ({','.join(str(int(i)) for i in ids) or 'NULL'})"
    out["by_department"] = db.q(conn, f"""SELECT COALESCE(d.name,'Unassigned') AS name, COUNT(*) AS n FROM employees e
                                            LEFT JOIN departments d ON d.id = e.dept_id WHERE e.status IN ('Active','On Notice'){where}
                                           GROUP BY d.name ORDER BY n DESC""")
    out["by_gender"] = db.q(conn, f"SELECT COALESCE(gender,'Unspecified') AS name, COUNT(*) AS n FROM employees e WHERE status IN ('Active','On Notice'){where} GROUP BY gender")
    out["by_type"] = db.q(conn, f"SELECT emp_type AS name, COUNT(*) AS n FROM employees e WHERE status IN ('Active','On Notice'){where} GROUP BY emp_type ORDER BY n DESC")

    mm = t[5:7]
    cel = []
    for e in db.q(conn, f"SELECT id, full_name, dob, join_date FROM employees e WHERE status IN ('Active','On Notice'){where}"):
        if e["dob"] and e["dob"][5:7] == mm:
            cel.append({"name": e["full_name"], "kind": "Birthday", "date": e["dob"], "day": e["dob"][8:]})
        if e["join_date"] and e["join_date"][5:7] == mm and e["join_date"][:4] < t[:4]:
            cel.append({"name": e["full_name"], "kind": "Work anniversary", "date": e["join_date"], "day": e["join_date"][8:],
                        "years": years_between(e["join_date"], t[:4] + e["join_date"][4:])})
    out["celebrations"] = sorted(cel, key=lambda x: x["day"])
    out["notices"] = db.q(conn, "SELECT * FROM notices WHERE expires_on IS NULL OR expires_on >= ? ORDER BY posted_on DESC LIMIT 4", (t,))
    out["holidays"] = db.q(conn, "SELECT * FROM holidays WHERE date >= ? ORDER BY date LIMIT 5", (t,))
    if rbac.has(u, "lifecycle.view"):
        out["open_tasks"] = db.scalar(conn, "SELECT COUNT(*) FROM emp_tasks WHERE done = 0")
    return out
