"""Talent: recruitment (jobs & candidate pipeline), performance reviews, training.

Endpoints
---------
/api/jobs, /api/candidates             generic CRUD (recruitment.*)
POST /api/candidates/{id}/stage        {stage}
/api/reviews                           generic CRUD (performance.*; line managers see their team)
/api/trainings                         generic CRUD (training.*)
GET  /api/trainings/{id}/participants
PUT  /api/trainings/{id}/participants  {participants:[{emp_id, attended}]}
"""
from ..core import audit, db, rbac
from ..core.http import ApiError, route
from ..core.resource import Resource
from ..core.utils import Field, today

STAGES = ["Applied", "Screening", "Interview", "Offer", "Hired", "Rejected"]

# ---------------------------------------------------------------- recruitment
Resource("jobs", "jobs",
         [Field("title", required=True, label="Position"), Field("dept_id", "fk", label="Department"),
          Field("unit_id", "fk", label="Business unit"), Field("vacancies", "int", default=1),
          Field("emp_type", choices=["Permanent", "Contract", "Intern", "Part-time"], default="Permanent"),
          Field("salary_range"), Field("posted_on", "date"), Field("deadline", "date"),
          Field("status", choices=["Open", "On Hold", "Closed"], default="Open"), Field("description")],
         "recruitment.view", "recruitment.manage",
         select="""SELECT t.*, d.name AS department, u.name AS unit_name,
                          (SELECT COUNT(*) FROM candidates c WHERE c.job_id = t.id) AS applicants,
                          (SELECT COUNT(*) FROM candidates c WHERE c.job_id = t.id AND c.stage = 'Hired') AS hired
                     FROM jobs t LEFT JOIN departments d ON d.id = t.dept_id LEFT JOIN business_units u ON u.id = t.unit_id""",
         search=("t.title", "d.name"), filters=("t.status",), order="t.status = 'Open' DESC, t.posted_on DESC", label="Job opening")

candidates = Resource("candidates", "candidates",
                      [Field("job_id", "fk", label="Position"), Field("name", required=True), Field("phone"), Field("email"),
                       Field("source", choices=["Bdjobs", "LinkedIn", "Referral", "Walk-in", "Campus", "Company website", "Other"]),
                       Field("expected_salary", "real"), Field("stage", choices=STAGES, default="Applied"),
                       Field("rating", "int"), Field("interview_date", "date"), Field("notes")],
                      "recruitment.view", "recruitment.manage", timestamps=True,
                      select="""SELECT t.*, j.title AS job_title, j.dept_id, j.unit_id, j.emp_type FROM candidates t
                                  LEFT JOIN jobs j ON j.id = t.job_id""",
                      search=("t.name", "t.email", "t.phone", "j.title"), filters=("t.job_id", "t.stage"),
                      order="t.id DESC", label="Candidate")


@route("POST", "/api/candidates/{id}/stage", "recruitment.manage")
def move(req):
    row = candidates.fetch(req, req.int_param())
    stage = req.body.get("stage")
    if stage not in STAGES:
        raise ApiError(400, "Unknown stage")
    db.update(req.db, "candidates", row["id"], {"stage": stage})
    audit.log(req, "update", "candidates", row["id"], f"Moved {row['name']} to {stage}")
    return candidates.fetch(req, row["id"])


# ---------------------------------------------------------------- performance
SCORES = ("quality", "productivity", "teamwork", "punctuality", "initiative")


def _score(req, data, existing):
    merged = {**(existing or {}), **data}
    vals = [merged.get(k) for k in SCORES]
    for v in vals:
        if v is not None and not 1 <= v <= 5:
            raise ApiError(400, "Scores must be between 1 and 5")
    vals = [v for v in vals if v is not None]
    data["score"] = round(sum(vals) / len(vals), 2) if vals else None
    target = merged.get("emp_id")
    if not rbac.has(req.user, "performance.view_all") and target not in rbac.team_ids(req.db, req.user):
        raise ApiError(403, "You can only review your direct reports.")
    if existing is None and not data.get("reviewer_id"):
        data["reviewer_id"] = req.user.get("emp_id")


Resource("reviews", "reviews",
         [Field("emp_id", "fk", required=True, label="Employee"), Field("reviewer_id", "fk", label="Reviewer"),
          Field("period", required=True)] + [Field(k, "int") for k in SCORES] +
         [Field("goals"), Field("comments"), Field("status", choices=["Draft", "Submitted", "Acknowledged"], default="Draft")],
         "performance.view", "performance.manage", timestamps=True,
         select="""SELECT t.*, e.full_name, e.code, d.name AS department, r.full_name AS reviewer_name FROM reviews t
                     JOIN employees e ON e.id = t.emp_id LEFT JOIN departments d ON d.id = e.dept_id
                     LEFT JOIN employees r ON r.id = t.reviewer_id""",
         search=("e.full_name", "e.code", "t.period"), filters=("t.emp_id", "t.period", "t.status"),
         order="t.id DESC", label="Review", scope_perm="performance.view_all", before_save=_score)


# ---------------------------------------------------------------- training
trainings = Resource("trainings", "trainings",
                     [Field("title", required=True, label="Program"),
                      Field("category", choices=["Technical", "Compliance", "Leadership", "Soft Skills", "Onboarding", "Safety"]),
                      Field("trainer"), Field("start_date", "date", label="Date"), Field("hours", "real"), Field("venue"),
                      Field("mode", choices=["Classroom", "Online", "On-the-job"]), Field("cost", "real"),
                      Field("status", choices=["Scheduled", "Completed", "Cancelled"], default="Scheduled"), Field("description")],
                     "training.view", "training.manage",
                     select="""SELECT t.*, (SELECT COUNT(*) FROM training_participants p WHERE p.training_id = t.id) AS participants,
                                      (SELECT COUNT(*) FROM training_participants p WHERE p.training_id = t.id AND p.attended = 1) AS attended
                                 FROM trainings t""",
                     search=("t.title", "t.trainer", "t.category"), filters=("t.status", "t.category"),
                     order="t.start_date DESC", label="Training")


@route("GET", "/api/trainings/{id}/participants", "training.view")
def participants(req):
    return {"items": db.q(req.db, """SELECT p.emp_id, p.attended, e.full_name, e.code, d.name AS department
                                       FROM training_participants p JOIN employees e ON e.id = p.emp_id
                                       LEFT JOIN departments d ON d.id = e.dept_id WHERE p.training_id = ? ORDER BY e.full_name""",
                          (req.int_param(),))}


@route("PUT", "/api/trainings/{id}/participants", "training.manage")
def set_participants(req):
    tid = req.int_param()
    trainings.fetch(req, tid)
    req.db.execute("DELETE FROM training_participants WHERE training_id = ?", (tid,))
    rows = req.body.get("participants", [])
    for p in rows:
        req.db.execute("INSERT OR IGNORE INTO training_participants (training_id, emp_id, attended) VALUES (?,?,?)",
                       (tid, int(p["emp_id"]), 1 if p.get("attended") else 0))
    audit.log(req, "update", "trainings", tid, f"Set {len(rows)} participant(s)")
    return {"ok": True}
