# 08 · Roles & permissions

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

| Permission | Meaning | System Administrator | HR Manager | HR Officer | Payroll Officer | Line Manager | Employee |
|---|---|---|---|---|---|---|---|
| `dashboard.view` | See the organisation dashboard | ✓ | ✓ | ✓ | ✓ | ✓ |  |
| `employees.view` | View the employee directory and profiles | ✓ | ✓ | ✓ | ✓ |  |  |
| `employees.manage` | Create, edit and archive employees | ✓ | ✓ | ✓ |  |  |  |
| `employees.salary` | See salary and bank details | ✓ | ✓ |  | ✓ |  |  |
| `employees.documents` | Upload and download employee documents | ✓ | ✓ | ✓ |  |  |  |
| `org.view` | View business units, departments and designations | ✓ | ✓ | ✓ | ✓ | ✓ |  |
| `org.manage` | Maintain the organisation structure | ✓ | ✓ |  |  |  |  |
| `lifecycle.view` | View promotions, transfers, onboarding and disciplinary records | ✓ | ✓ | ✓ |  |  |  |
| `lifecycle.manage` | Record promotions, transfers, increments, exits and disciplinary actions | ✓ | ✓ | ✓ |  |  |  |
| `attendance.view_all` | View attendance of all employees | ✓ | ✓ | ✓ | ✓ |  |  |
| `attendance.manage` | Mark, edit and import attendance | ✓ | ✓ | ✓ |  |  |  |
| `leave.view_all` | View leave of all employees | ✓ | ✓ | ✓ | ✓ |  |  |
| `leave.approve` | Approve or reject leave (team only for line managers) | ✓ | ✓ |  |  | ✓ |  |
| `leave.manage` | Apply leave on behalf of others; maintain leave types and opening balances | ✓ | ✓ | ✓ |  |  |  |
| `payroll.view` | View payroll runs and payslips of all employees | ✓ | ✓ |  | ✓ |  |  |
| `payroll.manage` | Generate, adjust, finalize and pay payroll | ✓ | ✓ |  | ✓ |  |  |
| `loans.view` | View loans and salary advances | ✓ | ✓ |  | ✓ |  |  |
| `loans.manage` | Issue and maintain loans and salary advances | ✓ | ✓ |  | ✓ |  |  |
| `claims.view_all` | View all expense claims | ✓ | ✓ |  | ✓ |  |  |
| `claims.approve` | Approve, reject and pay expense claims | ✓ | ✓ |  | ✓ | ✓ |  |
| `recruitment.view` | View jobs and candidates | ✓ | ✓ | ✓ |  |  |  |
| `recruitment.manage` | Manage jobs and the candidate pipeline | ✓ | ✓ | ✓ |  |  |  |
| `performance.view` | View performance reviews (own team for line managers) | ✓ | ✓ | ✓ |  | ✓ |  |
| `performance.view_all` | View performance reviews of all employees | ✓ | ✓ | ✓ |  |  |  |
| `performance.manage` | Create and edit performance reviews | ✓ | ✓ |  |  | ✓ |  |
| `training.view` | View training programs | ✓ | ✓ | ✓ |  | ✓ |  |
| `training.manage` | Manage training programs and participants | ✓ | ✓ | ✓ |  |  |  |
| `assets.view` | View the asset register | ✓ | ✓ | ✓ |  |  |  |
| `assets.manage` | Issue, return and maintain assets | ✓ | ✓ | ✓ |  |  |  |
| `holidays.manage` | Maintain the holiday calendar | ✓ | ✓ | ✓ |  |  |  |
| `notices.manage` | Post and edit notices | ✓ | ✓ | ✓ |  |  |  |
| `reports.view` | Run and export reports | ✓ | ✓ | ✓ | ✓ |  |  |
| `settings.manage` | Change company settings and policies; download backups | ✓ | ✓ |  |  |  |  |
| `users.manage` | Manage user accounts and roles | ✓ |  |  |  |  |  |
| `audit.view` | View the audit trail | ✓ | ✓ |  |  |  |  |
| `team.view` | See and act on direct reports (line managers) | ✓ | ✓ |  |  | ✓ |  |
| `self.attendance` | Clock in/out and see own attendance | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `self.leave` | Apply for and see own leave | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `self.payroll` | See own payslips | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `self.claims` | Submit and see own expense claims | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `self.profile` | See and update own profile | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## Changing roles

- **Give someone a role:** Users and roles → Edit → Role. It applies on their next request; no sign-out needed.
- **Create a new role** (for example *Recruiter*): add an entry to `ROLES` in `backend/core/rbac.py`, then restart HR-MIS:

```python
"recruiter": {"label": "Recruiter", "perms": SELF | {"dashboard.view", "recruitment.view", "recruitment.manage", "org.view"}},
```

- **Add a permission:** add it to `PERMISSIONS`, grant it to roles, and reference it in the module's `route(…, perm)` or `Resource(view_perm=…, manage_perm=…)`. Then run `python tools/gen_docs.py`.

## Account security

- Passwords: PBKDF2-HMAC-SHA256, 200,000 iterations, per-user salt; at least 8 characters with letters and numbers.
- New and reset accounts must choose their own password at first sign-in. That dialog cannot be dismissed.
- 8 failed sign-ins within 15 minutes lock that username for 15 minutes.
- Sessions: random 256-bit tokens, stored only as SHA-256 hashes, expiring after 12 hours (configurable). Disabling a user or resetting their password ends all their sessions.
- Every sign-in and change is written to the **audit trail** with the user and IP address.
