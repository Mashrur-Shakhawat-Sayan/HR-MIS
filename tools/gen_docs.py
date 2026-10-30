"""Regenerate docs/06-api-reference.md, docs/07-database-schema.md and docs/08-roles-and-permissions.md from the code.

    python tools/gen_docs.py
"""
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend import modules  # noqa: E402,F401
from backend.core.http import router  # noqa: E402

GROUP = [("/api/auth", "Authentication"), ("/api/users", "Users"), ("/api/roles", "Users"), ("/api/dashboard", "Dashboard"),
         ("/api/employees", "Employees"), ("/api/documents", "Employees"), ("/api/me", "Self-service"),
         ("/api/units", "Organisation"), ("/api/departments", "Organisation"), ("/api/designations", "Organisation"), ("/api/org-chart", "Organisation"),
         ("/api/lifecycle", "Lifecycle"), ("/api/tasks", "Lifecycle"), ("/api/disciplinary", "Lifecycle"),
         ("/api/attendance", "Attendance"), ("/api/holidays", "Attendance"), ("/api/leave", "Leave"),
         ("/api/payroll", "Payroll"), ("/api/loans", "Loans"), ("/api/claims", "Claims"),
         ("/api/jobs", "Recruitment"), ("/api/candidates", "Recruitment"), ("/api/reviews", "Performance"), ("/api/trainings", "Training"),
         ("/api/assets", "Assets"), ("/api/notices", "Notices"), ("/api/reports", "Reports"), ("/api/settings", "System"),
         ("/api/audit", "System"), ("/api/system", "System")]


def group_of(path):
    for prefix, g in GROUP:
        if path.startswith(prefix):
            return g
    return "Other"


def api_doc():
    rows = {}
    for method, _, fn, perm, auth, pattern in router.routes:
        if pattern.startswith("/api/employees/{id}/events") or pattern.startswith("/api/employees/{id}/tasks"):
            g = "Lifecycle"
        else:
            g = group_of(pattern)
        p = "public" if not auth else ("any signed-in user" if not perm else " or ".join(f"`{x}`" for x in ([perm] if isinstance(perm, str) else perm)))
        rows.setdefault(g, []).append((pattern, method, p))
    out = ["# 06 · API reference", "",
           "_Generated from the code by `python tools/gen_docs.py` — do not edit by hand._", "",
           "All endpoints live under `/api`, accept and return JSON (UTF-8), and — except `POST /api/auth/login` — need the header",
           "`Authorization: Bearer <token>` obtained from the login call. Errors come back as `{\"error\": \"message\"}` with an HTTP status:",
           "`400` invalid input · `401` not signed in / session expired · `403` missing permission · `404` not found · `409` conflict (duplicate, locked, linked data) · `429` too many login attempts.", "",
           "Generic resources (marked ★) support `?q=` free-text search, `?<field>=` exact filters, `?limit=` and `?offset=`, and return `{items, total}`.", ""]
    generic = {"/api/units", "/api/departments", "/api/designations", "/api/holidays", "/api/leave-types", "/api/loans", "/api/claims", "/api/jobs",
               "/api/candidates", "/api/reviews", "/api/trainings", "/api/assets", "/api/notices", "/api/disciplinary"}
    order = []
    for _, g in GROUP:
        if g not in order:
            order.append(g)
    for g in order + ["Other"]:
        if g not in rows:
            continue
        out += [f"## {g}", "", "| Method | Path | Permission |", "|---|---|---|"]
        for pattern, method, p in sorted(rows[g], key=lambda r: (r[0], ["GET", "POST", "PUT", "DELETE"].index(r[1]))):
            star = " ★" if pattern in generic else ""
            out.append(f"| `{method}` | `{pattern}`{star} | {p} |")
        out.append("")
    out += ["## Example (PowerShell / curl)", "", "```bash",
            "# 1. sign in",
            "curl -s -X POST http://127.0.0.1:8000/api/auth/login -H \"Content-Type: application/json\" \\",
            "     -d '{\"username\":\"hr.manager\",\"password\":\"Hr@12345\"}'",
            "# → {\"token\": \"…\", \"user\": {…}}",
            "",
            "# 2. call an endpoint with the token",
            "curl -s http://127.0.0.1:8000/api/employees?dept_id=3 -H \"Authorization: Bearer <token>\"",
            "```", ""]
    return "\n".join(out)


def schema_doc():
    conn = sqlite3.connect(":memory:")
    with open(os.path.join(ROOT, "backend", "db", "schema.sql"), encoding="utf-8") as f:
        sql = f.read()
    conn.executescript(sql)
    comments = {}
    for line in sql.splitlines():
        m = re.match(r"CREATE TABLE IF NOT EXISTS (\w+) \(\s*(?:--\s*(.*))?", line.strip())
        if m and m.group(2):
            comments[m.group(1)] = m.group(2)
    out = ["# 07 · Database schema", "", "_Generated from `backend/db/schema.sql` by `python tools/gen_docs.py`._", "",
           "Engine: SQLite 3 (file `data/hrmis.db`, WAL mode, foreign keys ON). Dates are ISO text `YYYY-MM-DD`, timestamps `YYYY-MM-DDTHH:MM:SS`, months `YYYY-MM`; money is REAL in BDT.", "",
           "## Entity map", "", "```",
           "business_units 1─* departments 1─* employees *─1 designations",
           "employees 1─* employees (manager_id)          employees 1─1 users",
           "employees 1─* attendance | leave_requests | leave_adjustments | claims | loans | reviews | emp_events | emp_tasks | emp_documents | disciplinary",
           "leave_types 1─* leave_requests                payroll_runs 1─* payslips *─1 employees",
           "loans 1─* loan_repayments *─1 payroll_runs     jobs 1─* candidates",
           "trainings *─* employees (training_participants) assets *─1 employees",
           "```", ""]
    groups = [("Organisation", ["business_units", "departments", "designations"]),
              ("People", ["employees", "emp_documents", "emp_events", "emp_tasks", "disciplinary"]),
              ("Security & audit", ["users", "sessions", "audit_log", "settings", "meta"]),
              ("Time & leave", ["holidays", "attendance", "leave_types", "leave_requests", "leave_adjustments"]),
              ("Pay", ["payroll_runs", "payslips", "loans", "loan_repayments", "claims"]),
              ("Talent", ["jobs", "candidates", "reviews", "trainings", "training_participants"]),
              ("Administration", ["assets", "notices"])]
    for g, tables in groups:
        out += [f"## {g}", ""]
        for t in tables:
            cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
            fks = {r[3]: f"{r[2]}.{r[4]}" for r in conn.execute(f"PRAGMA foreign_key_list({t})").fetchall()}
            uniq = []
            for idx in conn.execute(f"PRAGMA index_list({t})").fetchall():
                if idx[2]:
                    uniq.append(", ".join(c[2] for c in conn.execute(f"PRAGMA index_info('{idx[1]}')").fetchall()))
            out += [f"### `{t}`" + (f" — {comments[t]}" if t in comments else ""), "", "| Column | Type | Null | Default | Notes |", "|---|---|---|---|---|"]
            for cid, name, typ, notnull, dflt, pk in cols:
                notes = []
                if pk:
                    notes.append("primary key")
                if name in fks:
                    notes.append(f"→ {fks[name]}")
                out.append(f"| `{name}` | {typ or ''} | {'' if notnull or pk else 'yes'} | {dflt or ''} | {'; '.join(notes)} |")
            if uniq:
                out.append("")
                out.append("Unique: " + " · ".join(f"({u})" for u in uniq))
            out.append("")
    return "\n".join(out)


def roles_doc():
    from backend.core import rbac
    roles = list(rbac.ROLES)
    head = "| Permission | Meaning | " + " | ".join(rbac.ROLES[r]["label"] for r in roles) + " |\n|---|---|" + "---|" * len(roles)
    rows = [f"| `{p}` | {desc} | " + " | ".join("✓" if p in rbac.permissions_for(r) else "" for r in roles) + " |" for p, desc in rbac.PERMISSIONS.items()]
    return f"""# 08 · Roles & permissions

_The permission matrix below is generated from `backend/core/rbac.py` by `python tools/gen_docs.py`._

Access is controlled in two layers, both enforced **on the server**:

1. **Permissions.** Every API endpoint declares the permission(s) it needs; a request without one of them gets `403`.
2. **Data scope.** For people data, the server also limits *whose* records are returned:

| Scope | Who | Rule |
|---|---|---|
| Everyone | users holding the module's `*.view_all` (or `employees.view` for the directory) | no filter |
| Self and team | line managers (`team.view`) | own record plus employees whose *reporting manager* is them |
| Self only | everyone else | own employee record |

Further hard rules:
- Nobody approves their **own** leave or claim, and line managers decide only for their **direct reports**.
- Self-service claims are always created as *Pending*; employees see payslips only once payroll is **finalized**.
- Salary, bank, NID and e-TIN fields are **removed** from responses for users without `employees.salary`.
- A manager assignment that would create a reporting loop is refused.
- Administrators cannot change their own role or disable themselves, and the last active administrator cannot be demoted or disabled.
- When an employee's last working day passes, their status becomes final (Resigned, Terminated or Retired) and their login is **disabled automatically**.

## Roles

| Role key | Label | Intended for |
|---|---|---|
| `admin` | System Administrator | IT or HRIS owner. Everything, including user accounts |
| `hr_manager` | HR Manager | Head of HR. Everything except managing user accounts |
| `hr_officer` | HR Officer | HR executives. People, time, leave, talent, assets and notices; **no salary or payroll** |
| `payroll_officer` | Payroll Officer | Payroll and accounts. Payroll, loans, claims and salaries; read access to people, attendance and leave |
| `manager` | Line Manager | Department or section heads. **Their own team only**: profiles, attendance, leave and claim approvals, reviews |
| `employee` | Employee | Everyone. Self-service only |

Every role also has the five `self.*` permissions, so anyone with a linked employee record gets **My workspace**.

## Permission matrix

{{head}}
{{rows}}

## Changing roles

- **Give someone a role:** Users and roles → Edit → Role. It applies on their next request; no sign-out needed.
- **Create a new role** (for example *Recruiter*): add an entry to `ROLES` in `backend/core/rbac.py`, then restart HR-MIS:

```python
"recruiter": {{{{"label": "Recruiter", "perms": SELF | {{{{"dashboard.view", "recruitment.view", "recruitment.manage", "org.view"}}}}}}}},
```

- **Add a permission:** add it to `PERMISSIONS`, grant it to roles, and reference it in the module's `route(…, perm)` or `Resource(view_perm=…, manage_perm=…)`. Then run `python tools/gen_docs.py`.

## Account security

- Passwords: PBKDF2-HMAC-SHA256, 200,000 iterations, per-user salt; at least 8 characters with letters and numbers.
- New and reset accounts must choose their own password at first sign-in. That dialog cannot be dismissed.
- 8 failed sign-ins within 15 minutes lock that username for 15 minutes.
- Sessions: random 256-bit tokens, stored only as SHA-256 hashes, expiring after 12 hours (configurable). Disabling a user or resetting their password ends all their sessions.
- Every sign-in and change is written to the **audit trail** with the user and IP address.
""".replace("{head}", head).replace("{rows}", "\n".join(rows)).replace("{{", "{").replace("}}", "}")


if __name__ == "__main__":
    with open(os.path.join(ROOT, "docs", "06-api-reference.md"), "w", encoding="utf-8") as f:
        f.write(api_doc())
    with open(os.path.join(ROOT, "docs", "07-database-schema.md"), "w", encoding="utf-8") as f:
        f.write(schema_doc())
    with open(os.path.join(ROOT, "docs", "08-roles-and-permissions.md"), "w", encoding="utf-8") as f:
        f.write(roles_doc())
    print("Wrote docs/06-api-reference.md, docs/07-database-schema.md and docs/08-roles-and-permissions.md")
