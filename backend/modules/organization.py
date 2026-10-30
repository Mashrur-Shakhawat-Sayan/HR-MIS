"""Organisation structure: business units, departments, designations, org chart.

Endpoints: /api/units, /api/departments, /api/designations (generic CRUD), GET /api/org-chart
"""
from ..core import db
from ..core.http import ApiError, route
from ..core.resource import Resource
from ..core.utils import Field


def _no_staff(column):
    def check(req, row):
        n = db.scalar(req.db, f"SELECT COUNT(*) FROM employees WHERE {column} = ?", (row["id"],))
        if n:
            raise ApiError(409, f"{n} employee(s) are still assigned here. Move them first.")
    return check


Resource("units", "business_units",
         [Field("name", required=True), Field("code"), Field("location")],
         "org.view", "org.manage", timestamps=False,
         select="""SELECT t.*, (SELECT COUNT(*) FROM employees e WHERE e.unit_id = t.id AND e.status IN ('Active','On Notice')) AS headcount
                     FROM business_units t""",
         search=("t.name", "t.location"), order="t.name", label="Business unit", before_delete=_no_staff("unit_id"))

Resource("departments", "departments",
         [Field("name", required=True), Field("unit_id", "fk", label="Business unit"), Field("head_emp_id", "fk", label="Department head"),
          Field("cost_center")],
         "org.view", "org.manage",
         select="""SELECT t.*, u.name AS unit_name, h.full_name AS head_name,
                          (SELECT COUNT(*) FROM employees e WHERE e.dept_id = t.id AND e.status IN ('Active','On Notice')) AS headcount
                     FROM departments t LEFT JOIN business_units u ON u.id = t.unit_id
                     LEFT JOIN employees h ON h.id = t.head_emp_id""",
         search=("t.name", "u.name"), filters=("t.unit_id",), order="t.name", label="Department",
         before_delete=_no_staff("dept_id"))

Resource("designations", "designations",
         [Field("title", required=True), Field("grade"), Field("level", "int")],
         "org.view", "org.manage",
         select="""SELECT t.*, (SELECT COUNT(*) FROM employees e WHERE e.designation_id = t.id AND e.status IN ('Active','On Notice')) AS headcount
                     FROM designations t""",
         search=("t.title", "t.grade"), order="COALESCE(t.level, 99), t.title", label="Designation",
         before_delete=_no_staff("designation_id"))


@route("GET", "/api/org-chart", "org.view")
def org_chart(req):
    rows = db.q(req.db, """SELECT e.id, e.full_name, e.code, e.manager_id, g.title AS designation, d.name AS department
                             FROM employees e LEFT JOIN designations g ON g.id = e.designation_id
                             LEFT JOIN departments d ON d.id = e.dept_id
                            WHERE e.status IN ('Active','On Notice') ORDER BY COALESCE(g.level, 99), e.full_name""")
    ids = {r["id"] for r in rows}
    for r in rows:
        if r["manager_id"] not in ids:
            r["manager_id"] = None
    return {"items": rows}
