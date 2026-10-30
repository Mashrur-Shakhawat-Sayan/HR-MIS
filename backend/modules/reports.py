"""Reports catalogue. Every report returns {title, columns, rows} as JSON or, with ?format=csv, a CSV download.

GET /api/reports                      catalogue (only reports the user may run)
GET /api/reports/{key}?month=&year=&format=csv
"""
from ..core import db, rbac
from ..core.http import ApiError, Response, route
from ..core.utils import Calendar, get_settings, month_bounds, today, years_between
from .attendance import monthly_stats

REPORTS = {}


def report(key, title, group, needs=None, params=()):
    def deco(fn):
        REPORTS[key] = {"key": key, "title": title, "group": group, "needs": needs, "params": list(params), "fn": fn}
        return fn
    return deco


ACTIVE = "e.status IN ('Active','On Notice')"
EMP_JOIN = """FROM employees e LEFT JOIN departments d ON d.id = e.dept_id LEFT JOIN designations g ON g.id = e.designation_id
              LEFT JOIN business_units u ON u.id = e.unit_id"""


@report("employee-master", "Employee master list", "People", params=["status"])
def employee_master(conn, p):
    cond = "" if p.get("status") == "all" else f"WHERE {ACTIVE}"
    rows = db.q(conn, f"""SELECT e.code, e.full_name, e.gender, e.dob, e.phone, e.email, e.blood_group, u.name AS unit, d.name AS dept,
                                 g.title AS desig, e.grade, e.emp_type, e.join_date, e.status, e.exit_date {EMP_JOIN} {cond} ORDER BY e.code""")
    cols = ["Employee ID", "Name", "Gender", "Date of birth", "Mobile", "Email", "Blood", "Business unit", "Department", "Designation", "Grade", "Type", "Joined", "Status", "Exit date"]
    return cols, [list(r.values()) for r in rows]


@report("headcount", "Headcount by department and unit", "People")
def headcount(conn, p):
    rows = db.q(conn, f"""SELECT COALESCE(d.name,'—') AS dept, COALESCE(u.name,'—') AS unit, COUNT(*) AS n,
                                 SUM(e.gender='Male') AS m, SUM(e.gender='Female') AS f,
                                 SUM(e.emp_type='Permanent') AS perm, SUM(e.emp_type!='Permanent') AS other
                          {EMP_JOIN} WHERE {ACTIVE} GROUP BY d.name, u.name ORDER BY d.name""")
    return ["Department", "Business unit", "Headcount", "Male", "Female", "Permanent", "Other types"], [list(r.values()) for r in rows]


@report("joiners-leavers", "Joiners and leavers", "People", params=["year"])
def joiners_leavers(conn, p):
    y = p.get("year") or today()[:4]
    rows = db.q(conn, f"""SELECT 'Joined' AS kind, e.join_date AS dt, e.code, e.full_name, d.name, g.title, e.emp_type, '' AS reason {EMP_JOIN}
                           WHERE substr(e.join_date,1,4) = ?
                          UNION ALL
                          SELECT e.status, e.exit_date, e.code, e.full_name, d.name, g.title, e.emp_type, COALESCE(e.exit_reason,'') {EMP_JOIN}
                           WHERE e.exit_date IS NOT NULL AND substr(e.exit_date,1,4) = ? ORDER BY 2""", (y, y))
    return ["Movement", "Date", "Employee ID", "Name", "Department", "Designation", "Type", "Reason"], [list(r.values()) for r in rows]


@report("turnover", "Turnover by department", "People", params=["year"])
def turnover(conn, p):
    y = p.get("year") or today()[:4]
    rows = db.q(conn, f"""SELECT COALESCE(d.name,'—') AS dept, SUM({ACTIVE}) AS active,
                                 SUM(substr(e.join_date,1,4) = ?) AS joined,
                                 SUM(e.exit_date IS NOT NULL AND substr(e.exit_date,1,4) = ? AND e.status NOT IN ('Active','On Notice')) AS left_
                          {EMP_JOIN} GROUP BY d.name ORDER BY d.name""", (y, y))
    out = []
    for r in rows:
        avg = (r["active"] or 0) + (r["left_"] or 0) / 2
        out.append([r["dept"], r["active"], r["joined"], r["left_"], f"{(r['left_'] or 0) / avg * 100:.1f}%" if avg else "0%"])
    return ["Department", "Active", "Joined", "Left", "Turnover %"], out


@report("celebrations", "Birthdays and work anniversaries", "People", params=["month"])
def celebrations(conn, p):
    m = (p.get("month") or today()[:7])[5:7]
    out = []
    for r in db.q(conn, f"SELECT e.code, e.full_name, d.name AS dept, e.dob, e.join_date {EMP_JOIN} WHERE {ACTIVE}"):
        if r["dob"] and r["dob"][5:7] == m:
            out.append([r["dob"][8:], "Birthday", r["code"], r["full_name"], r["dept"], ""])
        if r["join_date"][5:7] == m and r["join_date"][:4] < today()[:4]:
            out.append([r["join_date"][8:], "Work anniversary", r["code"], r["full_name"], r["dept"],
                        f"{years_between(r['join_date'], today()[:4] + r['join_date'][4:])} years"])
    return ["Day", "Occasion", "Employee ID", "Name", "Department", "Milestone"], sorted(out)


@report("probation", "Probation, contract and interns", "People")
def probation(conn, p):
    months = get_settings(conn)["probation_months"]
    rows = db.q(conn, f"SELECT e.code, e.full_name, d.name, g.title, e.emp_type, e.join_date {EMP_JOIN} WHERE {ACTIVE} AND e.emp_type != 'Permanent' ORDER BY e.join_date")
    out = []
    for r in rows:
        y, mo, dd = map(int, r["join_date"].split("-"))
        mo += months
        y += (mo - 1) // 12
        mo = (mo - 1) % 12 + 1
        out.append(list(r.values()) + [f"{y}-{mo:02d}-{min(dd, 28):02d}" if r["emp_type"] == "Probation" else ""])
    return ["Employee ID", "Name", "Department", "Designation", "Type", "Joined", "Confirmation due"], out


@report("attendance-summary", "Monthly attendance summary", "Time & Leave", needs="attendance.view_all", params=["month"])
def attendance_summary(conn, p):
    month = p.get("month") or today()[:7]
    _, end, _ = month_bounds(month)
    emps = db.q(conn, f"SELECT e.id, e.code, e.full_name, d.name AS dept {EMP_JOIN} WHERE e.join_date <= ? AND ({ACTIVE} OR e.exit_date >= ?) ORDER BY e.code",
                (end, month + "-01"))
    st = monthly_stats(conn, month, [e["id"] for e in emps])
    out = []
    for e in emps:
        s = st.get(e["id"], {})
        out.append([e["code"], e["full_name"], e["dept"], s.get("workdays", 0), s.get("P", 0), s.get("L", 0), s.get("HD", 0),
                    s.get("A", 0), s.get("LV", 0), s.get("WFH", 0) + s.get("OD", 0), f"{s.get('pct', 0)}%"])
    return ["Employee ID", "Name", "Department", "Working days", "Present", "Late", "Half day", "Absent", "Leave", "WFH / OD", "Attendance %"], out


@report("late-absent", "Late-comers and absentees", "Time & Leave", needs="attendance.view_all", params=["month"])
def late_absent(conn, p):
    cols, rows = attendance_summary(conn, p)
    rows = [r for r in rows if r[5] or r[7]]
    rows.sort(key=lambda r: (-(r[7] or 0), -(r[5] or 0)))
    return cols, rows


@report("leave-register", "Leave register", "Time & Leave", needs="leave.view_all", params=["year"])
def leave_register(conn, p):
    y = p.get("year") or today()[:4]
    rows = db.q(conn, """SELECT e.code, e.full_name, d.name, t.name AS lt, r.from_date, r.to_date, r.days, r.status, r.reason, r.decided_by
                           FROM leave_requests r JOIN employees e ON e.id = r.emp_id JOIN leave_types t ON t.id = r.leave_type_id
                           LEFT JOIN departments d ON d.id = e.dept_id WHERE substr(r.from_date,1,4) = ? ORDER BY r.from_date""", (y,))
    return ["Employee ID", "Name", "Department", "Leave type", "From", "To", "Days", "Status", "Reason", "Decided by"], [list(r.values()) for r in rows]


@report("leave-balance", "Leave balance statement", "Time & Leave", needs="leave.view_all", params=["year"])
def leave_balance(conn, p):
    from .leave import balances_for
    y = int(p.get("year") or today()[:4])
    types = db.q(conn, "SELECT name FROM leave_types WHERE active = 1 AND days_per_year > 0 ORDER BY id")
    out = []
    for e in db.q(conn, f"SELECT e.id, e.code, e.full_name {EMP_JOIN} WHERE {ACTIVE} ORDER BY e.code"):
        b = {x["leave_type"]: x for x in balances_for(conn, e["id"], y)}
        out.append([e["code"], e["full_name"]] + [f"{b[t['name']]['remaining']:g} / {b[t['name']]['entitled']:g}" if t["name"] in b and b[t["name"]]["remaining"] is not None else "—" for t in types])
    return ["Employee ID", "Name"] + [t["name"] + " (left / entitled)" for t in types], out


@report("payroll-summary", "Payroll summary by month", "Payroll", needs="payroll.view", params=["year"])
def payroll_summary(conn, p):
    y = p.get("year") or today()[:4]
    rows = db.q(conn, """SELECT r.month, r.status, COUNT(s.id), SUM(s.gross), SUM(s.ot_amount), SUM(s.bonus), SUM(s.pf), SUM(s.tax),
                                SUM(s.lwp_deduction + s.loan_deduction + s.other_deduction), SUM(s.net), SUM(s.pf_employer)
                           FROM payroll_runs r LEFT JOIN payslips s ON s.run_id = r.id WHERE substr(r.month,1,4) = ? GROUP BY r.id ORDER BY r.month""", (y,))
    return ["Month", "Status", "Employees", "Gross", "Overtime", "Bonus", "PF", "Tax", "Other deductions", "Net paid", "Employer PF"], \
        [[round(v) if isinstance(v, float) else v for v in r.values()] for r in rows]


@report("salary-cost", "Salary cost by department", "Payroll", needs="employees.salary")
def salary_cost(conn, p):
    s = get_settings(conn)
    rows = db.q(conn, f"SELECT COALESCE(d.name,'—') AS dept, COUNT(*) AS n, SUM(e.gross_salary) AS g {EMP_JOIN} WHERE {ACTIVE} GROUP BY d.name ORDER BY g DESC")
    out = []
    for r in rows:
        g = r["g"] or 0
        annual = g * 12 + g * s["basic_pct"] / 100 * s["festival_bonus_pct"] / 100 * 2 + g * s["basic_pct"] / 100 * s["pf_employer_pct"] / 100 * 12
        out.append([r["dept"], r["n"], round(g), round(g / r["n"]) if r["n"] else 0, round(annual)])
    return ["Department", "Headcount", "Monthly gross", "Average gross", "Annual cost (12 months + 2 bonuses + employer PF)"], out


@report("loans-outstanding", "Outstanding loans and advances", "Payroll", needs="loans.view")
def loans_outstanding(conn, p):
    rows = db.q(conn, """SELECT e.code, e.full_name, l.loan_type, l.issued_on, l.principal, l.installment,
                                COALESCE((SELECT SUM(amount) FROM loan_repayments r WHERE r.loan_id = l.id),0) AS repaid, l.status
                           FROM loans l JOIN employees e ON e.id = l.emp_id WHERE l.status IN ('Active','Pending') ORDER BY e.code""")
    return ["Employee ID", "Name", "Type", "Issued", "Amount", "Installment", "Repaid", "Outstanding", "Status"], \
        [[r["code"], r["full_name"], r["loan_type"], r["issued_on"], round(r["principal"]), round(r["installment"]), round(r["repaid"]),
          round(r["principal"] - r["repaid"]), r["status"]] for r in rows]


@report("claims-summary", "Expense claims by category", "Payroll", needs="claims.view_all", params=["year"])
def claims_summary(conn, p):
    y = p.get("year") or today()[:4]
    rows = db.q(conn, """SELECT category, COUNT(*), SUM(amount), SUM(CASE WHEN status='Pending' THEN amount ELSE 0 END),
                                SUM(CASE WHEN status='Approved' THEN amount ELSE 0 END), SUM(CASE WHEN status='Paid' THEN amount ELSE 0 END)
                           FROM claims WHERE substr(claim_date,1,4) = ? GROUP BY category ORDER BY 3 DESC""", (y,))
    return ["Category", "Claims", "Total", "Pending", "Approved (unpaid)", "Paid"], [[round(v) if isinstance(v, float) else v for v in r.values()] for r in rows]


@report("training-summary", "Training summary", "Talent", needs="training.view", params=["year"])
def training_summary(conn, p):
    y = p.get("year") or today()[:4]
    rows = db.q(conn, """SELECT t.start_date, t.title, t.category, t.mode, t.hours, t.status,
                                (SELECT COUNT(*) FROM training_participants x WHERE x.training_id = t.id),
                                (SELECT COUNT(*) FROM training_participants x WHERE x.training_id = t.id AND x.attended = 1), t.cost
                           FROM trainings t WHERE substr(t.start_date,1,4) = ? ORDER BY t.start_date""", (y,))
    return ["Date", "Program", "Category", "Mode", "Hours", "Status", "Nominated", "Attended", "Cost"], [list(r.values()) for r in rows]


@report("performance-summary", "Performance ratings", "Talent", needs="performance.view_all", params=["period"])
def performance_summary(conn, p):
    cond, params = ("WHERE r.period = ?", [p["period"]]) if p.get("period") else ("", [])
    rows = db.q(conn, f"""SELECT e.code, e.full_name, d.name, r.period, r.quality, r.productivity, r.teamwork, r.punctuality, r.initiative, r.score, r.status
                            FROM reviews r JOIN employees e ON e.id = r.emp_id LEFT JOIN departments d ON d.id = e.dept_id {cond} ORDER BY r.score DESC""", params)
    return ["Employee ID", "Name", "Department", "Period", "Quality", "Productivity", "Teamwork", "Punctuality", "Initiative", "Score", "Status"], [list(r.values()) for r in rows]


@report("asset-register", "Asset register", "Administration", needs="assets.view")
def asset_register(conn, p):
    rows = db.q(conn, """SELECT a.tag, a.name, a.category, a.serial, e.code, e.full_name, a.issued_on, a.value, a.condition, a.status
                           FROM assets a LEFT JOIN employees e ON e.id = a.emp_id ORDER BY a.tag""")
    return ["Tag", "Asset", "Category", "Serial", "Employee ID", "Assigned to", "Issued", "Value", "Condition", "Status"], [list(r.values()) for r in rows]


def _allowed(user, r):
    return rbac.has(user, "reports.view") and (not r["needs"] or rbac.has(user, r["needs"]))


@route("GET", "/api/reports", "reports.view")
def catalogue(req):
    return {"items": [{k: v for k, v in r.items() if k != "fn"} for r in REPORTS.values() if _allowed(req.user, r)]}


@route("GET", "/api/reports/{key}", "reports.view")
def run_report(req):
    r = REPORTS.get(req.params["key"])
    if not r:
        raise ApiError(404, "Unknown report")
    if not _allowed(req.user, r):
        raise ApiError(403, "You do not have permission to run this report.")
    cols, rows = r["fn"](req.db, req.query)
    if req.q("format") == "csv":
        return Response.csv(f"{r['key']}.csv", [cols] + rows)
    return {"title": r["title"], "columns": cols, "rows": rows}
