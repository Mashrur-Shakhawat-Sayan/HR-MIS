"""Administration: asset register and notice board.

Endpoints
---------
/api/assets                     generic CRUD (assets.*)
POST /api/assets/{id}/issue     {emp_id, issued_on}
POST /api/assets/{id}/return    {condition}
/api/notices                    generic CRUD (everyone can read; notices.manage to write)
"""
from ..core import audit, db, rbac
from ..core.http import ApiError, route
from ..core.resource import Resource
from ..core.utils import Field, today

assets = Resource("assets", "assets",
                  [Field("tag", required=True, label="Asset tag"), Field("name", required=True),
                   Field("category", choices=["Laptop", "Desktop", "Mobile Phone", "SIM", "Vehicle", "Furniture", "ID / Access Card", "Other"]),
                   Field("serial", label="Serial / reg. no."), Field("emp_id", "fk", label="Assigned to"), Field("issued_on", "date"),
                   Field("value", "real"), Field("condition", choices=["New", "Good", "Fair", "Damaged"], default="Good"),
                   Field("status", choices=["Assigned", "In Stock", "Under Repair", "Disposed"], default="In Stock"), Field("notes")],
                  "assets.view", "assets.manage",
                  select="SELECT t.*, e.full_name, e.code FROM assets t LEFT JOIN employees e ON e.id = t.emp_id",
                  search=("t.tag", "t.name", "t.serial", "e.full_name"), filters=("t.status", "t.category", "t.emp_id"),
                  order="t.tag", label="Asset")


@route("POST", "/api/assets/{id}/issue", "assets.manage")
def issue(req):
    row = assets.fetch(req, req.int_param())
    if not req.body.get("emp_id"):
        raise ApiError(400, "Choose an employee")
    db.update(req.db, "assets", row["id"], {"emp_id": int(req.body["emp_id"]), "issued_on": req.body.get("issued_on") or today(), "status": "Assigned"})
    audit.log(req, "update", "assets", row["id"], f"Issued {row['tag']}")
    return assets.fetch(req, row["id"])


@route("POST", "/api/assets/{id}/return", "assets.manage")
def give_back(req):
    row = assets.fetch(req, req.int_param())
    db.update(req.db, "assets", row["id"], {"emp_id": None, "issued_on": None, "status": "In Stock",
                                            "condition": req.body.get("condition") or row["condition"]})
    audit.log(req, "update", "assets", row["id"], f"Returned {row['tag']} from {row['full_name']}")
    return assets.fetch(req, row["id"])


def _notice_defaults(req, data, existing):
    if existing is None:
        data["posted_on"] = data.get("posted_on") or today()
        data["created_by"] = req.user["username"]


Resource("notices", "notices",
         [Field("posted_on", "date", label="Date"), Field("title", required=True), Field("body", label="Message"),
          Field("audience", default="All Employees"), Field("priority", choices=["Normal", "Important"], default="Normal"),
          Field("expires_on", "date")],
         None, "notices.manage", search=("t.title", "t.body"), order="t.posted_on DESC, t.id DESC", label="Notice",
         before_save=_notice_defaults,
         extra_where=lambda req: None if rbac.has(req.user, "notices.manage") else ("(t.expires_on IS NULL OR t.expires_on >= ?)", [today()]))
