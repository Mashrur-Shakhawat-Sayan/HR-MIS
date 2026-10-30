"""Payroll engine and payroll runs.

Calculation (per employee, per month) — all percentages come from Settings:

  pay_days        = calendar days employed in the month (joiners / leavers are pro-rated)
  gross           = full_gross × pay_days / month_days
  basic           = gross × basic_pct          house_rent = gross × house_rent_pct
  medical         = gross × medical_pct        conveyance = gross − basic − house_rent − medical
  basic_full      = full_gross × basic_pct (used for per-day / per-hour rates)
  LWP days        = absent days + ½ × half days + unpaid-leave working days + ⌊late days ÷ late_per_lwp_day⌋
  LWP deduction   = basic_full ÷ lwp_divisor_days × LWP days
  overtime        = basic_full ÷ ot_divisor_hours × ot_multiplier × OT hours
  festival bonus  = basic_full × festival_bonus_pct   (only when the run includes bonus)
  PF (employee)   = basic × pf_employee_pct   (PF members only); employer share shown separately
  income tax TDS  = gross × tax_pct  when full_gross ≥ tax_min_gross
  loan deduction  = Σ min(installment, outstanding) of active loans that have started
  net             = gross + overtime + bonus + additions − (PF + tax + LWP + loan + other deductions)

Run lifecycle:  (none) ─generate─▶ Draft ─finalize─▶ Finalized ─pay─▶ Paid
                 Draft can be regenerated and adjusted; Finalized can be reopened.

Endpoints
---------
GET    /api/payroll/runs
GET    /api/payroll/runs/{month}                     run + payslips (preview if not generated)
POST   /api/payroll/runs/{month}/generate            {include_bonus}
POST   /api/payroll/runs/{month}/finalize | /pay | /reopen
DELETE /api/payroll/runs/{month}                     delete a draft
PUT    /api/payroll/payslips/{id}                    {ot_hours, additions, other_deduction, remarks}
GET    /api/payroll/payslips/{id}                    one payslip (own payslip allowed once finalized)
GET    /api/payroll/my                               own payslips
GET    /api/payroll/runs/{month}/export?type=register|bank|pf   CSV
"""
import math

from ..core import audit, db, rbac
from ..core.http import ApiError, Response, route
from ..core.utils import MONTH_RX, Calendar, get_settings, money, month_bounds, now

SLIP_SELECT = "SELECT p.*, r.month, r.status AS run_status FROM payslips p JOIN payroll_runs r ON r.id = p.run_id"


def _month(req):
    m = req.params.get("month", "")
    if not MONTH_RX.match(m):
        raise ApiError(400, "Month must be YYYY-MM")
    return m


def payroll_employees(conn, month):
    start, end, _ = month_bounds(month)
    return db.q(conn, """SELECT e.*, d.name AS department, g.title AS designation FROM employees e
                           LEFT JOIN departments d ON d.id = e.dept_id LEFT JOIN designations g ON g.id = e.designation_id
                          WHERE e.join_date <= ? AND (e.exit_date IS NULL OR e.exit_date >= ?)
                            AND (e.status IN ('Active','On Notice') OR e.exit_date IS NOT NULL)
                          ORDER BY e.code""", (end, start))


def loan_deduction(conn, emp_id, month, exclude_run=None):
    total, detail = 0.0, []
    for ln in db.q(conn, "SELECT * FROM loans WHERE emp_id = ? AND status = 'Active' AND start_month <= ?", (emp_id, month)):
        paid = db.scalar(conn, "SELECT COALESCE(SUM(amount),0) FROM loan_repayments WHERE loan_id = ? AND (run_id IS NULL OR run_id != ?)",
                         (ln["id"], exclude_run or -1))
        outstanding = max(0.0, ln["principal"] - paid)
        amt = min(ln["installment"], outstanding)
        if amt > 0:
            total += amt
            detail.append((ln["id"], amt))
    return money(total), detail


def compute(conn, s, cal, emp, month, include_bonus, adj=None, run_id=None):
    adj = adj or {}
    start, end, n_days = month_bounds(month)
    first = max(start, emp["join_date"])
    last = min(end, emp["exit_date"]) if emp.get("exit_date") else end
    pay_days = max(0, (int(last[8:]) - int(first[8:]) + 1)) if first <= last else 0
    full = float(emp["gross_salary"] or 0)
    gross = full * pay_days / n_days
    basic, house, medical = gross * s["basic_pct"] / 100, gross * s["house_rent_pct"] / 100, gross * s["medical_pct"] / 100
    conveyance = gross - basic - house - medical
    basic_full = full * s["basic_pct"] / 100

    att = db.q(conn, "SELECT status, COUNT(*) AS n FROM attendance WHERE emp_id = ? AND date BETWEEN ? AND ? GROUP BY status",
               (emp["id"], first, last)) if pay_days else []
    counts = {r["status"]: r["n"] for r in att}
    unpaid = 0
    for lr in db.q(conn, """SELECT r.from_date, r.to_date, r.days FROM leave_requests r JOIN leave_types t ON t.id = r.leave_type_id
                             WHERE r.emp_id = ? AND r.status = 'Approved' AND t.paid = 0 AND r.from_date <= ? AND r.to_date >= ?""",
                    (emp["id"], last, first)):
        # min() keeps a half-day unpaid leave (days = 0.5) from being deducted as a full day
        unpaid += min(len(cal.workdays(max(first, lr["from_date"]), min(last, lr["to_date"]))), lr["days"])
    late = counts.get("L", 0)
    late_lwp = math.floor(late / s["late_per_lwp_day"]) if s["late_per_lwp_day"] else 0
    lwp = counts.get("A", 0) + counts.get("HD", 0) * 0.5 + unpaid + late_lwp

    ot_hours = float(adj.get("ot_hours") or 0)
    ot = basic_full / s["ot_divisor_hours"] * s["ot_multiplier"] * ot_hours
    bonus = basic_full * s["festival_bonus_pct"] / 100 if include_bonus and pay_days else 0
    additions = float(adj.get("additions") or 0)
    pf = basic * s["pf_employee_pct"] / 100 if emp.get("pf_member") else 0
    pf_er = basic * s["pf_employer_pct"] / 100 if emp.get("pf_member") else 0
    tax = gross * s["tax_pct"] / 100 if full >= s["tax_min_gross"] else 0
    lwp_ded = min(gross, basic_full / s["lwp_divisor_days"] * lwp)
    loan, _ = loan_deduction(conn, emp["id"], month, run_id)
    other = float(adj.get("other_deduction") or 0)
    earnings = gross + ot + bonus + additions
    deductions = pf + tax + lwp_ded + loan + other
    return {
        "emp_id": emp["id"], "emp_code": emp["code"], "emp_name": emp["full_name"], "department": emp.get("department"),
        "designation": emp.get("designation"), "bank_name": emp.get("bank_name"), "bank_account": emp.get("bank_account"),
        "tin": emp.get("tin"), "full_gross": money(full), "gross": money(gross), "basic": money(basic), "house_rent": money(house),
        "medical": money(medical), "conveyance": money(conveyance), "pay_days": pay_days, "month_days": n_days,
        "ot_hours": ot_hours, "ot_amount": money(ot), "bonus": money(bonus), "additions": money(additions),
        "earnings": money(earnings), "lwp_days": lwp, "late_count": late, "pf": money(pf), "pf_employer": money(pf_er),
        "tax": money(tax), "lwp_deduction": money(lwp_ded), "loan_deduction": loan, "other_deduction": money(other),
        "deductions": money(deductions), "net": money(max(0, earnings - deductions)), "remarks": adj.get("remarks"),
    }


def _totals(rows):
    keys = ("gross", "earnings", "deductions", "net", "pf", "pf_employer", "tax", "ot_amount", "bonus", "loan_deduction", "lwp_deduction")
    return {k: money(sum(r.get(k) or 0 for r in rows)) for k in keys} | {"count": len(rows)}


def _run(conn, month):
    return db.one(conn, "SELECT * FROM payroll_runs WHERE month = ?", (month,))


@route("GET", "/api/payroll/runs", "payroll.view")
def list_runs(req):
    runs = db.q(req.db, "SELECT * FROM payroll_runs ORDER BY month DESC")
    for r in runs:
        r.update(_totals(db.q(req.db, "SELECT * FROM payslips WHERE run_id = ?", (r["id"],))))
    return {"items": runs}


@route("GET", "/api/payroll/runs/{month}", "payroll.view")
def get_run(req):
    month = _month(req)
    run = _run(req.db, month)
    if run:
        rows = db.q(req.db, "SELECT * FROM payslips WHERE run_id = ? ORDER BY emp_code", (run["id"],))
    else:
        s, cal = get_settings(req.db), Calendar(req.db)
        rows = [compute(req.db, s, cal, e, month, False) for e in payroll_employees(req.db, month)]
        run = {"month": month, "status": "Not generated", "include_bonus": 0}
    return {"run": run, "items": rows, "totals": _totals(rows)}


@route("POST", "/api/payroll/runs/{month}/generate", "payroll.manage")
def generate(req):
    month = _month(req)
    run = _run(req.db, month)
    if run and run["status"] != "Draft":
        raise ApiError(409, f"Payroll for {month} is {run['status'].lower()}. Reopen it before regenerating.")
    include_bonus = 1 if req.body.get("include_bonus", run["include_bonus"] if run else 0) else 0
    if run:
        adjustments = {r["emp_id"]: r for r in db.q(req.db, "SELECT emp_id, ot_hours, additions, other_deduction, remarks FROM payslips WHERE run_id = ?", (run["id"],))}
        req.db.execute("DELETE FROM payslips WHERE run_id = ?", (run["id"],))
        db.update(req.db, "payroll_runs", run["id"], {"include_bonus": include_bonus})
        run_id = run["id"]
    else:
        adjustments = {}
        run_id = db.insert(req.db, "payroll_runs", {"month": month, "status": "Draft", "include_bonus": include_bonus,
                                                    "created_by": req.user["username"], "created_at": now()})
    s, cal = get_settings(req.db), Calendar(req.db)
    n = 0
    for e in payroll_employees(req.db, month):
        row = compute(req.db, s, cal, e, month, include_bonus, adjustments.get(e["id"]), run_id)
        row["run_id"] = run_id
        db.insert(req.db, "payslips", row)
        n += 1
    audit.log(req, "update", "payroll_runs", run_id, f"Generated payroll {month} for {n} employee(s)")
    return get_run(req)


@route("PUT", "/api/payroll/payslips/{id}", "payroll.manage")
def adjust(req):
    slip = db.one(req.db, SLIP_SELECT + " WHERE p.id = ?", (req.int_param(),))
    if not slip:
        raise ApiError(404, "Payslip not found")
    if slip["run_status"] != "Draft":
        raise ApiError(409, "This payroll is locked. Reopen it to make changes.")
    adj = {k: slip[k] for k in ("ot_hours", "additions", "other_deduction", "remarks")}
    for k in adj:
        if k in req.body:
            adj[k] = req.body[k] if k == "remarks" else float(req.body[k] or 0)
    emp = db.one(req.db, """SELECT e.*, d.name AS department, g.title AS designation FROM employees e
                             LEFT JOIN departments d ON d.id = e.dept_id LEFT JOIN designations g ON g.id = e.designation_id WHERE e.id = ?""", (slip["emp_id"],))
    run = _run(req.db, slip["month"])
    row = compute(req.db, get_settings(req.db), Calendar(req.db), emp, slip["month"], run["include_bonus"], adj, run["id"])
    db.update(req.db, "payslips", slip["id"], row)
    audit.log(req, "update", "payslips", slip["id"], f"Adjusted payslip {slip['month']} {slip['emp_code']}", adj)
    return db.one(req.db, "SELECT * FROM payslips WHERE id = ?", (slip["id"],))


@route("POST", "/api/payroll/runs/{month}/finalize", "payroll.manage")
def finalize(req):
    month = _month(req)
    run = _run(req.db, month)
    if not run or run["status"] != "Draft":
        raise ApiError(409, "Only a draft payroll can be finalized.")
    for slip in db.q(req.db, "SELECT emp_id, loan_deduction FROM payslips WHERE run_id = ? AND loan_deduction > 0", (run["id"],)):
        _, detail = loan_deduction(req.db, slip["emp_id"], month, run["id"])
        for loan_id, amt in detail:
            db.insert(req.db, "loan_repayments", {"loan_id": loan_id, "month": month, "amount": amt, "run_id": run["id"], "note": "Payroll deduction"})
            ln = db.one(req.db, "SELECT principal FROM loans WHERE id = ?", (loan_id,))
            paid = db.scalar(req.db, "SELECT SUM(amount) FROM loan_repayments WHERE loan_id = ?", (loan_id,))
            if paid >= ln["principal"] - 0.5:
                req.db.execute("UPDATE loans SET status = 'Closed' WHERE id = ?", (loan_id,))
    db.update(req.db, "payroll_runs", run["id"], {"status": "Finalized", "finalized_by": req.user["username"], "finalized_at": now()})
    audit.log(req, "update", "payroll_runs", run["id"], f"Finalized payroll {month}")
    return get_run(req)


@route("POST", "/api/payroll/runs/{month}/pay", "payroll.manage")
def mark_paid(req):
    month = _month(req)
    run = _run(req.db, month)
    if not run or run["status"] != "Finalized":
        raise ApiError(409, "Finalize the payroll before marking it as paid.")
    db.update(req.db, "payroll_runs", run["id"], {"status": "Paid", "paid_at": now()})
    audit.log(req, "update", "payroll_runs", run["id"], f"Marked payroll {month} as paid")
    return get_run(req)


@route("POST", "/api/payroll/runs/{month}/reopen", "payroll.manage")
def reopen(req):
    month = _month(req)
    run = _run(req.db, month)
    if not run or run["status"] != "Finalized":
        raise ApiError(409, "Only a finalized (not yet paid) payroll can be reopened.")
    for r in db.q(req.db, "SELECT DISTINCT loan_id FROM loan_repayments WHERE run_id = ?", (run["id"],)):
        req.db.execute("UPDATE loans SET status = 'Active' WHERE id = ? AND status = 'Closed'", (r["loan_id"],))
    req.db.execute("DELETE FROM loan_repayments WHERE run_id = ?", (run["id"],))
    db.update(req.db, "payroll_runs", run["id"], {"status": "Draft", "finalized_by": None, "finalized_at": None})
    audit.log(req, "update", "payroll_runs", run["id"], f"Reopened payroll {month}")
    return get_run(req)


@route("DELETE", "/api/payroll/runs/{month}", "payroll.manage")
def delete_run(req):
    month = _month(req)
    run = _run(req.db, month)
    if not run or run["status"] != "Draft":
        raise ApiError(409, "Only a draft payroll can be deleted.")
    req.db.execute("DELETE FROM payroll_runs WHERE id = ?", (run["id"],))
    audit.log(req, "delete", "payroll_runs", run["id"], f"Deleted draft payroll {month}")
    return {"ok": True}


@route("GET", "/api/payroll/payslips/{id}", ["payroll.view", "self.payroll"])
def get_slip(req):
    slip = db.one(req.db, SLIP_SELECT + " WHERE p.id = ?", (req.int_param(),))
    if not slip:
        raise ApiError(404, "Payslip not found")
    if not rbac.has(req.user, "payroll.view"):
        if slip["emp_id"] != req.user.get("emp_id") or slip["run_status"] == "Draft":
            raise ApiError(403, "This payslip is not available.")
    return slip


@route("GET", "/api/payroll/my", "self.payroll")
def my_slips(req):
    return {"items": db.q(req.db, SLIP_SELECT + " WHERE p.emp_id = ? AND r.status != 'Draft' ORDER BY r.month DESC",
                          (req.user.get("emp_id") or -1,))}


@route("GET", "/api/payroll/runs/{month}/export", "payroll.view")
def export(req):
    month = _month(req)
    rows = get_run(req)["items"]
    kind = req.q("type", "register")
    if kind == "bank":
        return Response.csv(f"bank-advice-{month}.csv", [["SL", "Employee ID", "Account name", "Bank", "Account number", "Net amount (BDT)"]] +
                            [[i + 1, r["emp_code"], r["emp_name"], r["bank_name"], r["bank_account"], round(r["net"])] for i, r in enumerate(rows)])
    if kind == "pf":
        return Response.csv(f"pf-contribution-{month}.csv", [["Employee ID", "Name", "Basic", "Employee PF", "Employer PF", "Total"]] +
                            [[r["emp_code"], r["emp_name"], round(r["basic"]), round(r["pf"]), round(r["pf_employer"]), round(r["pf"] + r["pf_employer"])] for r in rows if r["pf"]])
    cols = ["emp_code", "emp_name", "department", "designation", "full_gross", "pay_days", "gross", "basic", "house_rent", "medical",
            "conveyance", "ot_hours", "ot_amount", "bonus", "additions", "earnings", "late_count", "lwp_days", "pf", "tax",
            "lwp_deduction", "loan_deduction", "other_deduction", "deductions", "net", "pf_employer"]
    return Response.csv(f"payroll-register-{month}.csv", [[c.replace("_", " ").title() for c in cols]] + [[r.get(c) for c in cols] for r in rows])
