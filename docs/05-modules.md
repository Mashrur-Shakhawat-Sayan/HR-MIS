# 05 · Module reference

Each module has one backend file (`backend/modules/`) and usually one screen (`frontend/js/pages/`).
Each backend file starts with a docstring listing its endpoints. The full list with permissions is in [06-api-reference.md](06-api-reference.md).

| Module | Backend | Frontend | Tables | Key permissions |
|---|---|---|---|---|
| Authentication & users | `auth.py` | `app.js`, `users.js` | users, sessions | `users.manage` |
| Organisation | `organization.py` | `organization.js` | business_units, departments, designations | `org.view`, `org.manage` |
| Employees | `employees.py` | `employees.js` | employees, emp_documents | `employees.view/manage/salary/documents` |
| Lifecycle | `lifecycle.py` | `lifecycle.js`, profile tabs | emp_events, emp_tasks, disciplinary | `lifecycle.view/manage` |
| Attendance & holidays | `attendance.py` | `attendance.js`, `holidays.js` | attendance, holidays | `attendance.view_all/manage`, `holidays.manage` |
| Leave | `leave.py` | `leave.js`, `me.js` | leave_types, leave_requests, leave_adjustments | `leave.view_all/approve/manage` |
| Payroll | `payroll.py` | `payroll.js` | payroll_runs, payslips | `payroll.view/manage` |
| Loans | `loans.py` | `loans.js` | loans, loan_repayments | `loans.view/manage` |
| Claims | `claims.py` | `claims.js` | claims | `claims.view_all/approve` |
| Talent | `talent.py` | `recruitment.js`, `performance.js`, `training.js` | jobs, candidates, reviews, trainings, training_participants | `recruitment.*`, `performance.*`, `training.*` |
| Administration | `admin.py` | `assets.js`, `notices.js` | assets, notices | `assets.*`, `notices.manage` |
| Dashboard | `dashboard.py` | `dashboard.js` | (reads all) | adapts to permissions |
| Reports | `reports.py` | `reports.js` | (reads all) | `reports.view` + per-report permission |
| System | `system.py` | `settings.js`, `audit.js` | settings, audit_log | `settings.manage`, `audit.view` |
| Self-service | (spread across modules) | `me.js` | — | `self.*` |

---

## Employees
- **Codes** are `prefix + number`; `next_code` takes the highest numeric suffix plus one. A code can be typed manually.
- **Redaction:** `gross_salary`, bank fields, `pf_member`, `tin` and `nid` are removed from responses unless the user has `employees.salary` or is viewing their own record. Writes to those fields without the permission are silently ignored.
- **Create** also writes a *Joining* event, an 8-item onboarding checklist and, if asked, a login with a random temporary password (shown once).
- **Update** compares old and new designation, department, unit and gross salary, and writes career events automatically.
- **Delete** is refused once payslips exist (archive instead). Otherwise related attendance, leave, claims, loans and documents are removed.
- **Documents** are uploaded as base64 JSON (max 15 MB request). Files are stored under random names in `data/uploads/`. Download needs `employees.documents` or ownership.

## Lifecycle
`POST /api/employees/{id}/events` applies the change *and* records it (see the table in the user guide).
Exit events with a future last day set the status to **On Notice**; the employee still appears in attendance and payroll up to that date.
A **daily job** (`apply_due_exits`, registered in `core/utils.DAILY_JOBS` and run on the first request each day and at start-up) then sets the final status (Resigned / Terminated / Retired, from the latest exit event) and disables the person's login.
Transfers and employee edits refuse a manager that would create a reporting loop (`check_reporting_line`).
`confirmations-due` uses *Settings → probation months*.

## Attendance
- One row per employee per day (`UNIQUE(emp_id, date)`), upserted.
- Who is listed on a date: joined on or before it, and either no exit date or an exit date on or after it (`eligible()`). Payroll uses the same rule for the month.
- Future dates accept only leave, work from home or on duty; "mark the rest present" is refused for them.
- `upsert()` rules: a check-in without a status means Present; Present or Late is recalculated from the check-in time; Absent and Leave clear the times; an empty status deletes the row.
- `monthly_stats()` (used by the register, reports and dashboard) counts statuses and the working days an employee was employed, from joining to exit and up to today. Attendance % counts P, L, WFH, OD and LV as attended, and HD as half.
- **Import:** CSV `employee_id,date,check_in,check_out[,status]`. A header line is skipped, unknown IDs are reported per line, and the source is stored as `Import`.

## Leave
- Day count: working days (excluding weekend days from Settings and holidays) or calendar days when the type says so; half-day = 0.5.
- **Balance** = `days_per_year + adjustments − approved (this year)`. Pending days are shown separately and counted when checking a new request.
- Gender-restricted types (Maternity → Female, Paternity → Male) are hidden and refused for others.
- Approval writes `LV` rows into attendance for each working day; cancel or reject removes them (only rows still marked `LV`).
- Line managers (`leave.approve` without `leave.view_all`) can decide only for employees whose `manager_id` is themselves.

## Payroll
See [09-payroll-and-policy-rules.md](09-payroll-and-policy-rules.md) for every formula.
- `compute()` is a pure calculation; `generate` stores one payslip per payable employee and keeps any OT, additions and deductions already entered.
- Payable = joined on or before the month end, and either no exit date or an exit date on or after the month start. Half-day unpaid leave counts as half a day of LWP.
- Finalize records `loan_repayments` (closing fully repaid loans); reopen reverses them.
- Self-service users only see payslips from **Finalized** or **Paid** runs.

## Loans
`outstanding = principal − Σ repayments`. Payroll deducts `min(installment, outstanding)` for every active loan whose `start_month ≤ payroll month`.
Employee requests arrive as **Pending** and must be approved (set to Active) by `loans.manage`.

## Claims
Users without both `claims.view_all` and `claims.approve` can only create or edit their own claims, which are always Pending. Decisions go through `POST /api/claims/{id}/decision`.
*Paid* is allowed only after *Approved*.

## Talent
- **Recruitment:** `jobs` and `candidates` are generic resources; `POST /api/candidates/{id}/stage` moves a card. *Onboard* opens the employee form prefilled (frontend).
- **Performance:** score = average of the five factors that are filled in; without `performance.view_all`, reviews are limited to direct reports for both reading and writing.
- **Training:** participants are replaced in one call (`PUT /api/trainings/{id}/participants`).

## Dashboard
One call, `/api/dashboard`, returns only the widgets the caller may see. Personal data is always present for linked users; organisation KPIs need `dashboard.view`; payroll figures need `payroll.view` or `employees.salary`; recruitment needs `recruitment.view`.

## Reports
Each report is a function registered with `@report(key, title, group, needs=…, params=[…])` that returns `(columns, rows)`.
`GET /api/reports/{key}?format=csv` streams the same data as CSV with a UTF-8 BOM, so Excel opens it correctly. To add a report, write one function in `reports.py`; it appears in the UI automatically.

## System
Settings are stored as JSON in `settings(key, value)` and merged over `DEFAULT_SETTINGS` (`core/utils.py`). Unknown keys are ignored and numbers are validated.
Backups use SQLite's online backup API, so they are consistent even while people are working.
