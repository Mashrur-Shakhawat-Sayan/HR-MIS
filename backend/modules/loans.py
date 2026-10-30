"""Loans and salary advances.

Installments are deducted automatically by payroll (see payroll.py) and
recorded as repayments when the payroll is finalized. A loan closes itself
when fully repaid.

Endpoints
---------
/api/loans                       generic CRUD (loans.view / loans.manage) — includes repaid & outstanding
GET  /api/loans/{id}/repayments
POST /api/loans/{id}/repayments  manual repayment {month, amount, note}
GET  /api/loans/my               own loans (self-service)
POST /api/loans/request          employee requests an advance {loan_type, principal, installment, start_month, purpose}
"""
from ..core import audit, db
from ..core.http import ApiError, route
from ..core.resource import Resource
from ..core.utils import MONTH_RX, Field, now, today

TYPES = ["Salary Advance", "Personal Loan", "House Building Loan", "Vehicle Loan", "Medical Loan", "Other"]
SELECT = """SELECT t.*, e.full_name, e.code,
                   COALESCE((SELECT SUM(amount) FROM loan_repayments r WHERE r.loan_id = t.id), 0) AS repaid,
                   t.principal - COALESCE((SELECT SUM(amount) FROM loan_repayments r WHERE r.loan_id = t.id), 0) AS outstanding
              FROM loans t JOIN employees e ON e.id = t.emp_id"""


def _defaults(req, data, existing):
    if existing is None:
        data.setdefault("issued_on", today())
        data["approved_by"] = req.user["username"]
    if data.get("installment") and data.get("principal") and data["installment"] > data["principal"]:
        raise ApiError(400, "Installment cannot be larger than the loan amount")


Resource("loans", "loans",
         [Field("emp_id", "fk", required=True, label="Employee"), Field("loan_type", choices=TYPES, required=True, label="Type"),
          Field("principal", "real", required=True, label="Amount"), Field("installment", "real", required=True),
          Field("start_month", "month", required=True, label="First deduction month"), Field("issued_on", "date"),
          Field("purpose"), Field("status", choices=["Pending", "Active", "Closed", "Rejected"], default="Active")],
         "loans.view", "loans.manage", select=SELECT, search=("e.full_name", "e.code", "t.loan_type"),
         filters=("t.emp_id", "t.status"), order="t.status = 'Active' DESC, t.id DESC", label="Loan",
         timestamps=True, before_save=_defaults)


@route("GET", "/api/loans/{id}/repayments", "loans.view")
def repayments(req):
    return {"items": db.q(req.db, "SELECT * FROM loan_repayments WHERE loan_id = ? ORDER BY month", (req.int_param(),))}


@route("POST", "/api/loans/{id}/repayments", "loans.manage")
def add_repayment(req):
    loan_id = req.int_param()
    month = req.body.get("month") or today()[:7]
    if not MONTH_RX.match(month):
        raise ApiError(400, "Month must be YYYY-MM")
    amount = float(req.body.get("amount") or 0)
    if amount <= 0:
        raise ApiError(400, "Enter an amount")
    db.insert(req.db, "loan_repayments", {"loan_id": loan_id, "month": month, "amount": amount, "note": req.body.get("note") or "Manual repayment"})
    ln = db.one(req.db, SELECT + " WHERE t.id = ?", (loan_id,))
    if ln and ln["outstanding"] <= 0.5:
        req.db.execute("UPDATE loans SET status = 'Closed' WHERE id = ?", (loan_id,))
    audit.log(req, "create", "loan_repayments", loan_id, f"Manual repayment {amount:,.0f}")
    return {"ok": True}


@route("GET", "/api/loans/my", "self.payroll")
def my_loans(req):
    return {"items": db.q(req.db, SELECT + " WHERE t.emp_id = ? ORDER BY t.id DESC", (req.user.get("emp_id") or -1,))}


@route("POST", "/api/loans/request", "self.payroll")
def request_loan(req):
    b = req.body
    if not req.user.get("emp_id"):
        raise ApiError(404, "Your account is not linked to an employee record.")
    try:
        principal, installment = float(b["principal"]), float(b["installment"])
    except (KeyError, ValueError, TypeError):
        raise ApiError(400, "Enter the amount and monthly installment")
    if b.get("loan_type") not in TYPES or not MONTH_RX.match(b.get("start_month") or ""):
        raise ApiError(400, "Choose a loan type and first deduction month")
    lid = db.insert(req.db, "loans", {"emp_id": req.user["emp_id"], "loan_type": b["loan_type"], "principal": principal,
                                      "installment": min(installment, principal), "start_month": b["start_month"],
                                      "purpose": b.get("purpose"), "status": "Pending", "created_at": now()})
    audit.log(req, "create", "loans", lid, f"Requested {b['loan_type']} of {principal:,.0f}")
    return {"id": lid}
