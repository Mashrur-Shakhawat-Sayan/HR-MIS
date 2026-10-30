# 06 · API reference

_Generated from the code by `python tools/gen_docs.py` — do not edit by hand._

All endpoints live under `/api`, accept and return JSON (UTF-8), and — except `POST /api/auth/login` — need the header
`Authorization: Bearer <token>` obtained from the login call. Errors come back as `{"error": "message"}` with an HTTP status:
`400` invalid input · `401` not signed in / session expired · `403` missing permission · `404` not found · `409` conflict (duplicate, locked, linked data) · `429` too many login attempts.

Generic resources (marked ★) support `?q=` free-text search, `?<field>=` exact filters, `?limit=` and `?offset=`, and return `{items, total}`.

## Authentication

| Method | Path | Permission |
|---|---|---|
| `POST` | `/api/auth/change-password` | any signed-in user |
| `POST` | `/api/auth/login` | public |
| `POST` | `/api/auth/logout` | any signed-in user |
| `GET` | `/api/auth/me` | any signed-in user |

## Users

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/roles` | any signed-in user |
| `GET` | `/api/users` | `users.manage` |
| `POST` | `/api/users` | `users.manage` |
| `PUT` | `/api/users/{id}` | `users.manage` |
| `POST` | `/api/users/{id}/reset-password` | `users.manage` |

## Dashboard

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/dashboard` | any signed-in user |

## Employees

| Method | Path | Permission |
|---|---|---|
| `DELETE` | `/api/documents/{id}` | `employees.documents` |
| `GET` | `/api/documents/{id}/download` | any signed-in user |
| `GET` | `/api/employees` | `employees.view` or `team.view` |
| `POST` | `/api/employees` | `employees.manage` |
| `GET` | `/api/employees/lookup` | any signed-in user |
| `GET` | `/api/employees/next-code` | `employees.manage` |
| `GET` | `/api/employees/{id}` | any signed-in user |
| `PUT` | `/api/employees/{id}` | `employees.manage` |
| `DELETE` | `/api/employees/{id}` | `employees.manage` |
| `GET` | `/api/employees/{id}/documents` | any signed-in user |
| `POST` | `/api/employees/{id}/documents` | `employees.documents` |

## Self-service

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/me/profile` | `self.profile` |
| `PUT` | `/api/me/profile` | `self.profile` |

## Organisation

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/departments` ★ | `org.view` |
| `POST` | `/api/departments` ★ | `org.manage` |
| `GET` | `/api/departments/{id}` | `org.view` |
| `PUT` | `/api/departments/{id}` | `org.manage` |
| `DELETE` | `/api/departments/{id}` | `org.manage` |
| `GET` | `/api/designations` ★ | `org.view` |
| `POST` | `/api/designations` ★ | `org.manage` |
| `GET` | `/api/designations/{id}` | `org.view` |
| `PUT` | `/api/designations/{id}` | `org.manage` |
| `DELETE` | `/api/designations/{id}` | `org.manage` |
| `GET` | `/api/org-chart` | `org.view` |
| `GET` | `/api/units` ★ | `org.view` |
| `POST` | `/api/units` ★ | `org.manage` |
| `GET` | `/api/units/{id}` | `org.view` |
| `PUT` | `/api/units/{id}` | `org.manage` |
| `DELETE` | `/api/units/{id}` | `org.manage` |

## Lifecycle

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/disciplinary` ★ | `lifecycle.view` |
| `POST` | `/api/disciplinary` ★ | `lifecycle.manage` |
| `GET` | `/api/disciplinary/{id}` | `lifecycle.view` |
| `PUT` | `/api/disciplinary/{id}` | `lifecycle.manage` |
| `DELETE` | `/api/disciplinary/{id}` | `lifecycle.manage` |
| `POST` | `/api/employees/{id}/events` | `lifecycle.manage` |
| `POST` | `/api/employees/{id}/tasks` | `lifecycle.manage` |
| `GET` | `/api/lifecycle/confirmations-due` | `lifecycle.view` |
| `GET` | `/api/lifecycle/events` | `lifecycle.view` |
| `DELETE` | `/api/lifecycle/events/{id}` | `lifecycle.manage` |
| `GET` | `/api/lifecycle/tasks` | `lifecycle.view` |
| `PUT` | `/api/tasks/{id}` | `lifecycle.manage` |
| `DELETE` | `/api/tasks/{id}` | `lifecycle.manage` |

## Attendance

| Method | Path | Permission |
|---|---|---|
| `POST` | `/api/attendance/clock` | `self.attendance` |
| `GET` | `/api/attendance/daily` | `attendance.view_all` or `team.view` |
| `PUT` | `/api/attendance/daily` | `attendance.manage` |
| `GET` | `/api/attendance/export` | `attendance.view_all` or `team.view` |
| `POST` | `/api/attendance/import` | `attendance.manage` |
| `POST` | `/api/attendance/mark-all` | `attendance.manage` |
| `GET` | `/api/attendance/my` | `self.attendance` |
| `GET` | `/api/attendance/register` | `attendance.view_all` or `team.view` |
| `GET` | `/api/holidays` ★ | any signed-in user |
| `POST` | `/api/holidays` ★ | `holidays.manage` |
| `GET` | `/api/holidays/{id}` | any signed-in user |
| `PUT` | `/api/holidays/{id}` | `holidays.manage` |
| `DELETE` | `/api/holidays/{id}` | `holidays.manage` |

## Leave

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/leave-types` ★ | any signed-in user |
| `POST` | `/api/leave-types` ★ | `leave.manage` |
| `GET` | `/api/leave-types/{id}` | any signed-in user |
| `PUT` | `/api/leave-types/{id}` | `leave.manage` |
| `DELETE` | `/api/leave-types/{id}` | `leave.manage` |
| `GET` | `/api/leave/adjustments` | `leave.view_all` |
| `POST` | `/api/leave/adjustments` | `leave.manage` |
| `DELETE` | `/api/leave/adjustments/{id}` | `leave.manage` |
| `GET` | `/api/leave/balances` | `leave.view_all` or `self.leave` |
| `GET` | `/api/leave/calendar` | `leave.view_all` or `leave.approve` or `self.leave` |
| `GET` | `/api/leave/preview` | `self.leave` or `leave.manage` |
| `GET` | `/api/leave/requests` | `leave.view_all` or `leave.approve` or `self.leave` |
| `POST` | `/api/leave/requests` | `self.leave` or `leave.manage` |
| `POST` | `/api/leave/requests/{id}/cancel` | `self.leave` or `leave.manage` |
| `POST` | `/api/leave/requests/{id}/decision` | `leave.approve` |

## Payroll

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/payroll/my` | `self.payroll` |
| `GET` | `/api/payroll/payslips/{id}` | `payroll.view` or `self.payroll` |
| `PUT` | `/api/payroll/payslips/{id}` | `payroll.manage` |
| `GET` | `/api/payroll/runs` | `payroll.view` |
| `GET` | `/api/payroll/runs/{month}` | `payroll.view` |
| `DELETE` | `/api/payroll/runs/{month}` | `payroll.manage` |
| `GET` | `/api/payroll/runs/{month}/export` | `payroll.view` |
| `POST` | `/api/payroll/runs/{month}/finalize` | `payroll.manage` |
| `POST` | `/api/payroll/runs/{month}/generate` | `payroll.manage` |
| `POST` | `/api/payroll/runs/{month}/pay` | `payroll.manage` |
| `POST` | `/api/payroll/runs/{month}/reopen` | `payroll.manage` |

## Loans

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/loans` ★ | `loans.view` |
| `POST` | `/api/loans` ★ | `loans.manage` |
| `GET` | `/api/loans/my` | `self.payroll` |
| `POST` | `/api/loans/request` | `self.payroll` |
| `GET` | `/api/loans/{id}` | `loans.view` |
| `PUT` | `/api/loans/{id}` | `loans.manage` |
| `DELETE` | `/api/loans/{id}` | `loans.manage` |
| `GET` | `/api/loans/{id}/repayments` | `loans.view` |
| `POST` | `/api/loans/{id}/repayments` | `loans.manage` |

## Claims

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/claims` ★ | `claims.view_all` or `claims.approve` or `self.claims` |
| `POST` | `/api/claims` ★ | `claims.view_all` or `self.claims` |
| `GET` | `/api/claims/{id}` | `claims.view_all` or `claims.approve` or `self.claims` |
| `PUT` | `/api/claims/{id}` | `claims.view_all` or `self.claims` |
| `DELETE` | `/api/claims/{id}` | `claims.view_all` or `self.claims` |
| `POST` | `/api/claims/{id}/decision` | `claims.approve` |

## Recruitment

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/candidates` ★ | `recruitment.view` |
| `POST` | `/api/candidates` ★ | `recruitment.manage` |
| `GET` | `/api/candidates/{id}` | `recruitment.view` |
| `PUT` | `/api/candidates/{id}` | `recruitment.manage` |
| `DELETE` | `/api/candidates/{id}` | `recruitment.manage` |
| `POST` | `/api/candidates/{id}/stage` | `recruitment.manage` |
| `GET` | `/api/jobs` ★ | `recruitment.view` |
| `POST` | `/api/jobs` ★ | `recruitment.manage` |
| `GET` | `/api/jobs/{id}` | `recruitment.view` |
| `PUT` | `/api/jobs/{id}` | `recruitment.manage` |
| `DELETE` | `/api/jobs/{id}` | `recruitment.manage` |

## Performance

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/reviews` ★ | `performance.view` |
| `POST` | `/api/reviews` ★ | `performance.manage` |
| `GET` | `/api/reviews/{id}` | `performance.view` |
| `PUT` | `/api/reviews/{id}` | `performance.manage` |
| `DELETE` | `/api/reviews/{id}` | `performance.manage` |

## Training

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/trainings` ★ | `training.view` |
| `POST` | `/api/trainings` ★ | `training.manage` |
| `GET` | `/api/trainings/{id}` | `training.view` |
| `PUT` | `/api/trainings/{id}` | `training.manage` |
| `DELETE` | `/api/trainings/{id}` | `training.manage` |
| `GET` | `/api/trainings/{id}/participants` | `training.view` |
| `PUT` | `/api/trainings/{id}/participants` | `training.manage` |

## Assets

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/assets` ★ | `assets.view` |
| `POST` | `/api/assets` ★ | `assets.manage` |
| `GET` | `/api/assets/{id}` | `assets.view` |
| `PUT` | `/api/assets/{id}` | `assets.manage` |
| `DELETE` | `/api/assets/{id}` | `assets.manage` |
| `POST` | `/api/assets/{id}/issue` | `assets.manage` |
| `POST` | `/api/assets/{id}/return` | `assets.manage` |

## Notices

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/notices` ★ | any signed-in user |
| `POST` | `/api/notices` ★ | `notices.manage` |
| `GET` | `/api/notices/{id}` | any signed-in user |
| `PUT` | `/api/notices/{id}` | `notices.manage` |
| `DELETE` | `/api/notices/{id}` | `notices.manage` |

## Reports

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/reports` | `reports.view` |
| `GET` | `/api/reports/{key}` | `reports.view` |

## System

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/audit` | `audit.view` |
| `GET` | `/api/settings` | `settings.manage` |
| `PUT` | `/api/settings` | `settings.manage` |
| `GET` | `/api/system/backup` | `settings.manage` |
| `POST` | `/api/system/backup` | `settings.manage` |
| `GET` | `/api/system/info` | `settings.manage` |

## Example (PowerShell / curl)

```bash
# 1. sign in
curl -s -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" \
     -d '{"username":"hr.manager","password":"Hr@12345"}'
# → {"token": "…", "user": {…}}

# 2. call an endpoint with the token
curl -s http://127.0.0.1:8000/api/employees?dept_id=3 -H "Authorization: Bearer <token>"
```
