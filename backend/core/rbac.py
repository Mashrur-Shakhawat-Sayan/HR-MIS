"""Role-based access control.

Permissions are strings of the form ``<module>.<action>``. Each role maps to a
set of permissions; ``*`` means everything. Data scoping (e.g. a line manager
seeing only their team) is handled by `scope_emp_ids`.
"""

PERMISSIONS = {
    "dashboard.view": "See the organisation dashboard",
    "employees.view": "View the employee directory and profiles",
    "employees.manage": "Create, edit and archive employees",
    "employees.salary": "See salary and bank details",
    "employees.documents": "Upload and download employee documents",
    "org.view": "View business units, departments and designations",
    "org.manage": "Maintain the organisation structure",
    "lifecycle.view": "View promotions, transfers, onboarding and disciplinary records",
    "lifecycle.manage": "Record promotions, transfers, increments, exits and disciplinary actions",
    "attendance.view_all": "View attendance of all employees",
    "attendance.manage": "Mark, edit and import attendance",
    "leave.view_all": "View leave of all employees",
    "leave.approve": "Approve or reject leave (team only for line managers)",
    "leave.manage": "Apply leave on behalf of others; maintain leave types and opening balances",
    "payroll.view": "View payroll runs and payslips of all employees",
    "payroll.manage": "Generate, adjust, finalize and pay payroll",
    "loans.view": "View loans and salary advances",
    "loans.manage": "Issue and maintain loans and salary advances",
    "claims.view_all": "View all expense claims",
    "claims.approve": "Approve, reject and pay expense claims",
    "recruitment.view": "View jobs and candidates",
    "recruitment.manage": "Manage jobs and the candidate pipeline",
    "performance.view": "View performance reviews (own team for line managers)",
    "performance.view_all": "View performance reviews of all employees",
    "performance.manage": "Create and edit performance reviews",
    "training.view": "View training programs",
    "training.manage": "Manage training programs and participants",
    "assets.view": "View the asset register",
    "assets.manage": "Issue, return and maintain assets",
    "holidays.manage": "Maintain the holiday calendar",
    "notices.manage": "Post and edit notices",
    "reports.view": "Run and export reports",
    "settings.manage": "Change company settings and policies; download backups",
    "users.manage": "Manage user accounts and roles",
    "audit.view": "View the audit trail",
    "team.view": "See and act on direct reports (line managers)",
    # self-service (every employee)
    "self.attendance": "Clock in/out and see own attendance",
    "self.leave": "Apply for and see own leave",
    "self.payroll": "See own payslips",
    "self.claims": "Submit and see own expense claims",
    "self.profile": "See and update own profile",
}

SELF = {"self.attendance", "self.leave", "self.payroll", "self.claims", "self.profile"}

ROLES = {
    "admin": {"label": "System Administrator", "perms": {"*"}},
    "hr_manager": {"label": "HR Manager", "perms": set(PERMISSIONS) - {"users.manage"}},
    "hr_officer": {"label": "HR Officer", "perms": SELF | {
        "dashboard.view", "employees.view", "employees.manage", "employees.documents", "org.view",
        "lifecycle.view", "lifecycle.manage", "attendance.view_all", "attendance.manage",
        "leave.view_all", "leave.manage", "recruitment.view", "recruitment.manage",
        "training.view", "training.manage", "assets.view", "assets.manage", "holidays.manage",
        "notices.manage", "performance.view", "performance.view_all", "reports.view"}},
    "payroll_officer": {"label": "Payroll Officer", "perms": SELF | {
        "dashboard.view", "employees.view", "employees.salary", "org.view", "attendance.view_all",
        "leave.view_all", "payroll.view", "payroll.manage", "loans.view", "loans.manage",
        "claims.view_all", "claims.approve", "reports.view"}},
    "manager": {"label": "Line Manager", "perms": SELF | {
        "dashboard.view", "team.view", "leave.approve", "claims.approve", "performance.view",
        "performance.manage", "org.view", "training.view"}},
    "employee": {"label": "Employee", "perms": set(SELF)},
}


def permissions_for(role):
    perms = ROLES.get(role, ROLES["employee"])["perms"]
    return set(PERMISSIONS) if "*" in perms else set(perms)


def has(user, perm):
    return bool(user) and perm in user["permissions"]


def has_any(user, perms):
    if isinstance(perms, str):
        perms = [perms]
    return any(has(user, p) for p in perms)


def team_ids(conn, user):
    """Employee ids reporting directly to this user's employee record."""
    if not user.get("emp_id"):
        return []
    rows = conn.execute("SELECT id FROM employees WHERE manager_id = ? AND status IN ('Active','On Notice')",
                        (user["emp_id"],)).fetchall()
    return [r["id"] for r in rows]


def scope_emp_ids(conn, user, view_all_perm):
    """None = may see everyone; otherwise the list of employee ids the user may see."""
    if has(user, view_all_perm):
        return None
    ids = [user["emp_id"]] if user.get("emp_id") else []
    if has(user, "team.view"):
        ids += team_ids(conn, user)
    return ids


def can_see_employee(conn, user, emp_id, view_all_perm):
    scope = scope_emp_ids(conn, user, view_all_perm)
    return scope is None or int(emp_id) in scope
