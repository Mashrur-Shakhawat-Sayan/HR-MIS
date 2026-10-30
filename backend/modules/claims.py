"""Expense claims / reimbursements.

Employees submit their own claims (always Pending). Approvers (claims.approve)
decide; line managers only for their direct reports. Nobody approves their own claim.

Endpoints
---------
/api/claims                      list/create/update/delete (scoped to self + team unless claims.view_all)
POST /api/claims/{id}/decision   {status: Approved|Rejected|Paid}
"""
from ..core import audit, db, rbac
from ..core.http import ApiError, route
from ..core.resource import Resource
from ..core.utils import Field, now, today

CATEGORIES = ["Travel", "Food", "Fuel", "Mobile Bill", "Medical", "Accommodation", "Office Supplies", "Training", "Other"]


def _guard(req, data, existing):
    if rbac.has(req.user, "claims.view_all") and rbac.has(req.user, "claims.approve"):
        if existing is None:
            data["status"] = data.get("status") or "Pending"
            if not data.get("emp_id"):
                raise ApiError(400, "Employee is required")
        return
    # self-service rules
    if existing is not None and (existing["emp_id"] != req.user.get("emp_id") or existing["status"] != "Pending"):
        raise ApiError(403, "Only your own pending claims can be edited.")
    data["emp_id"] = req.user.get("emp_id")
    data["status"] = "Pending"
    if not data["emp_id"]:
        raise ApiError(400, "Your account is not linked to an employee record.")


def _guard_delete(req, row):
    if not rbac.has(req.user, "claims.view_all") and (row["emp_id"] != req.user.get("emp_id") or row["status"] != "Pending"):
        raise ApiError(403, "Only your own pending claims can be deleted.")


claims = Resource("claims", "claims",
                  [Field("emp_id", "fk", label="Employee"), Field("claim_date", "date", required=True, label="Date", default=None),
                   Field("category", choices=CATEGORIES, required=True), Field("amount", "real", required=True),
                   Field("description"), Field("status", choices=["Pending", "Approved", "Rejected", "Paid"])],
                  ["claims.view_all", "claims.approve", "self.claims"], ["claims.view_all", "self.claims"],
                  select="""SELECT t.*, e.full_name, e.code, e.manager_id, d.name AS department FROM claims t
                              JOIN employees e ON e.id = t.emp_id LEFT JOIN departments d ON d.id = e.dept_id""",
                  search=("e.full_name", "e.code", "t.category", "t.description"), filters=("t.emp_id", "t.status", "t.category"),
                  order="t.status = 'Pending' DESC, t.claim_date DESC", label="Claim", scope_perm="claims.view_all",
                  timestamps=True, before_save=_guard, before_delete=_guard_delete)


@route("POST", "/api/claims/{id}/decision", "claims.approve")
def decide(req):
    row = claims.fetch(req, req.int_param())
    status = req.body.get("status")
    if status not in ("Approved", "Rejected", "Paid"):
        raise ApiError(400, "Status must be Approved, Rejected or Paid")
    if row["emp_id"] == req.user.get("emp_id"):
        raise ApiError(403, "You cannot decide on your own claim.")
    if status == "Paid" and row["status"] != "Approved":
        raise ApiError(409, "Only approved claims can be marked as paid.")
    if status != "Paid" and row["status"] != "Pending":
        raise ApiError(409, f"This claim is already {row['status'].lower()}.")
    db.update(req.db, "claims", row["id"], {"status": status, "decided_by": req.user["username"], "decided_at": now()})
    audit.log(req, "update", "claims", row["id"], f"{status} claim of {row['full_name']} ({row['amount']:,.0f})")
    return claims.fetch(req, row["id"])
