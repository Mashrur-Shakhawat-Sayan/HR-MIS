# 07 · Database schema

_Generated from `backend/db/schema.sql` by `python tools/gen_docs.py`._

Engine: SQLite 3 (file `data/hrmis.db`, WAL mode, foreign keys ON). Dates are ISO text `YYYY-MM-DD`, timestamps `YYYY-MM-DDTHH:MM:SS`, months `YYYY-MM`; money is REAL in BDT.

## Entity map

```
business_units 1─* departments 1─* employees *─1 designations
employees 1─* employees (manager_id)          employees 1─1 users
employees 1─* attendance | leave_requests | leave_adjustments | claims | loans | reviews | emp_events | emp_tasks | emp_documents | disciplinary
leave_types 1─* leave_requests                payroll_runs 1─* payslips *─1 employees
loans 1─* loan_repayments *─1 payroll_runs     jobs 1─* candidates
trainings *─* employees (training_participants) assets *─1 employees
```

## Organisation

### `business_units`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `name` | TEXT |  |  |  |
| `code` | TEXT | yes |  |  |
| `location` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |

Unique: (name)

### `departments`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `name` | TEXT |  |  |  |
| `unit_id` | INTEGER | yes |  | → business_units.id |
| `head_emp_id` | INTEGER | yes |  |  |
| `cost_center` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |

Unique: (name, unit_id)

### `designations`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `title` | TEXT |  |  |  |
| `grade` | TEXT | yes |  |  |
| `level` | INTEGER | yes |  |  |
| `created_at` | TEXT | yes |  |  |

Unique: (title)

## People

### `employees`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `code` | TEXT |  |  |  |
| `full_name` | TEXT |  |  |  |
| `gender` | TEXT | yes |  |  |
| `dob` | TEXT | yes |  |  |
| `marital_status` | TEXT | yes |  |  |
| `blood_group` | TEXT | yes |  |  |
| `phone` | TEXT | yes |  |  |
| `email` | TEXT | yes |  |  |
| `nid` | TEXT | yes |  |  |
| `tin` | TEXT | yes |  |  |
| `father_name` | TEXT | yes |  |  |
| `mother_name` | TEXT | yes |  |  |
| `present_address` | TEXT | yes |  |  |
| `permanent_address` | TEXT | yes |  |  |
| `emergency_name` | TEXT | yes |  |  |
| `emergency_phone` | TEXT | yes |  |  |
| `unit_id` | INTEGER | yes |  | → business_units.id |
| `dept_id` | INTEGER | yes |  | → departments.id |
| `designation_id` | INTEGER | yes |  | → designations.id |
| `grade` | TEXT | yes |  |  |
| `emp_type` | TEXT |  | 'Permanent' |  |
| `join_date` | TEXT |  |  |  |
| `confirm_date` | TEXT | yes |  |  |
| `manager_id` | INTEGER | yes |  | → employees.id |
| `status` | TEXT |  | 'Active' |  |
| `exit_date` | TEXT | yes |  |  |
| `exit_reason` | TEXT | yes |  |  |
| `gross_salary` | REAL |  | 0 |  |
| `bank_name` | TEXT | yes |  |  |
| `bank_account` | TEXT | yes |  |  |
| `pf_member` | INTEGER |  | 1 |  |
| `created_at` | TEXT | yes |  |  |
| `updated_at` | TEXT | yes |  |  |

Unique: (code)

### `emp_documents`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `title` | TEXT |  |  |  |
| `doc_type` | TEXT | yes |  |  |
| `filename` | TEXT |  |  |  |
| `stored_name` | TEXT |  |  |  |
| `size` | INTEGER | yes |  |  |
| `content_type` | TEXT | yes |  |  |
| `uploaded_by` | TEXT | yes |  |  |
| `uploaded_at` | TEXT | yes |  |  |

### `emp_events` — career history

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `event_type` | TEXT |  |  |  |
| `effective_date` | TEXT |  |  |  |
| `old_value` | TEXT | yes |  |  |
| `new_value` | TEXT | yes |  |  |
| `details` | TEXT | yes |  |  |
| `created_by` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |

### `emp_tasks` — onboarding / offboarding checklists

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `category` | TEXT |  | 'Onboarding' |  |
| `task` | TEXT |  |  |  |
| `owner` | TEXT | yes |  |  |
| `due_date` | TEXT | yes |  |  |
| `done` | INTEGER |  | 0 |  |
| `done_at` | TEXT | yes |  |  |

### `disciplinary`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `action_date` | TEXT |  |  |  |
| `action_type` | TEXT |  |  |  |
| `reason` | TEXT | yes |  |  |
| `issued_by` | TEXT | yes |  |  |
| `status` | TEXT |  | 'Open' |  |
| `resolution` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |

## Security & audit

### `users`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `username` | TEXT |  |  |  |
| `password_hash` | TEXT |  |  |  |
| `role` | TEXT |  | 'employee' |  |
| `emp_id` | INTEGER | yes |  | → employees.id |
| `is_active` | INTEGER |  | 1 |  |
| `must_change_pw` | INTEGER |  | 0 |  |
| `last_login` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |

Unique: (username)

### `sessions`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `token_hash` | TEXT |  |  | primary key |
| `user_id` | INTEGER |  |  | → users.id |
| `created_at` | TEXT | yes |  |  |
| `expires_at` | TEXT | yes |  |  |
| `ip` | TEXT | yes |  |  |

Unique: (token_hash)

### `audit_log`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `ts` | TEXT |  |  |  |
| `user_id` | INTEGER | yes |  |  |
| `username` | TEXT | yes |  |  |
| `action` | TEXT |  |  |  |
| `entity` | TEXT | yes |  |  |
| `entity_id` | INTEGER | yes |  |  |
| `summary` | TEXT | yes |  |  |
| `details` | TEXT | yes |  |  |
| `ip` | TEXT | yes |  |  |

### `settings`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `key` | TEXT |  |  | primary key |
| `value` | TEXT |  |  |  |

Unique: (key)

### `meta`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `key` | TEXT |  |  | primary key |
| `value` | TEXT | yes |  |  |

Unique: (key)

## Time & leave

### `holidays`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `date` | TEXT |  |  |  |
| `name` | TEXT |  |  |  |
| `type` | TEXT | yes | 'National' |  |

Unique: (date)

### `attendance`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `date` | TEXT |  |  |  |
| `status` | TEXT |  |  |  |
| `check_in` | TEXT | yes |  |  |
| `check_out` | TEXT | yes |  |  |
| `source` | TEXT | yes | 'Manual' |  |
| `note` | TEXT | yes |  |  |

Unique: (emp_id, date)

### `leave_types`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `name` | TEXT |  |  |  |
| `days_per_year` | REAL |  | 0 |  |
| `gender` | TEXT |  | 'Any' |  |
| `paid` | INTEGER |  | 1 |  |
| `calendar_days` | INTEGER |  | 0 |  |
| `carry_forward` | INTEGER |  | 0 |  |
| `max_carry` | REAL | yes | 0 |  |
| `active` | INTEGER |  | 1 |  |
| `color` | TEXT | yes |  |  |

Unique: (name)

### `leave_requests`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `leave_type_id` | INTEGER |  |  | → leave_types.id |
| `from_date` | TEXT |  |  |  |
| `to_date` | TEXT |  |  |  |
| `days` | REAL |  |  |  |
| `reason` | TEXT | yes |  |  |
| `status` | TEXT |  | 'Pending' |  |
| `applied_at` | TEXT | yes |  |  |
| `applied_by` | TEXT | yes |  |  |
| `decided_by` | TEXT | yes |  |  |
| `decided_at` | TEXT | yes |  |  |
| `remarks` | TEXT | yes |  |  |

### `leave_adjustments` — opening balance / carry-forward / encashment

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `leave_type_id` | INTEGER |  |  | → leave_types.id |
| `year` | INTEGER |  |  |  |
| `days` | REAL |  |  |  |
| `note` | TEXT | yes |  |  |
| `created_by` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |

## Pay

### `payroll_runs`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `month` | TEXT |  |  |  |
| `status` | TEXT |  | 'Draft' |  |
| `include_bonus` | INTEGER |  | 0 |  |
| `notes` | TEXT | yes |  |  |
| `created_by` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |
| `finalized_by` | TEXT | yes |  |  |
| `finalized_at` | TEXT | yes |  |  |
| `paid_at` | TEXT | yes |  |  |

Unique: (month)

### `payslips`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `run_id` | INTEGER |  |  | → payroll_runs.id |
| `emp_id` | INTEGER |  |  | → employees.id |
| `emp_code` | TEXT | yes |  |  |
| `emp_name` | TEXT | yes |  |  |
| `department` | TEXT | yes |  |  |
| `designation` | TEXT | yes |  |  |
| `bank_name` | TEXT | yes |  |  |
| `bank_account` | TEXT | yes |  |  |
| `tin` | TEXT | yes |  |  |
| `full_gross` | REAL | yes |  |  |
| `gross` | REAL | yes |  |  |
| `basic` | REAL | yes |  |  |
| `house_rent` | REAL | yes |  |  |
| `medical` | REAL | yes |  |  |
| `conveyance` | REAL | yes |  |  |
| `pay_days` | INTEGER | yes |  |  |
| `month_days` | INTEGER | yes |  |  |
| `ot_hours` | REAL | yes | 0 |  |
| `ot_amount` | REAL | yes | 0 |  |
| `bonus` | REAL | yes | 0 |  |
| `additions` | REAL | yes | 0 |  |
| `earnings` | REAL | yes |  |  |
| `lwp_days` | REAL | yes | 0 |  |
| `late_count` | INTEGER | yes | 0 |  |
| `pf` | REAL | yes | 0 |  |
| `pf_employer` | REAL | yes | 0 |  |
| `tax` | REAL | yes | 0 |  |
| `lwp_deduction` | REAL | yes | 0 |  |
| `loan_deduction` | REAL | yes | 0 |  |
| `other_deduction` | REAL | yes | 0 |  |
| `deductions` | REAL | yes |  |  |
| `net` | REAL | yes |  |  |
| `remarks` | TEXT | yes |  |  |

Unique: (run_id, emp_id)

### `loans`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `loan_type` | TEXT |  |  |  |
| `principal` | REAL |  |  |  |
| `installment` | REAL |  |  |  |
| `start_month` | TEXT |  |  |  |
| `issued_on` | TEXT | yes |  |  |
| `purpose` | TEXT | yes |  |  |
| `status` | TEXT |  | 'Active' |  |
| `approved_by` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |

### `loan_repayments`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `loan_id` | INTEGER |  |  | → loans.id |
| `month` | TEXT |  |  |  |
| `amount` | REAL |  |  |  |
| `run_id` | INTEGER | yes |  | → payroll_runs.id |
| `note` | TEXT | yes |  |  |

### `claims`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `claim_date` | TEXT |  |  |  |
| `category` | TEXT |  |  |  |
| `amount` | REAL |  |  |  |
| `description` | TEXT | yes |  |  |
| `status` | TEXT |  | 'Pending' |  |
| `decided_by` | TEXT | yes |  |  |
| `decided_at` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |

## Talent

### `jobs`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `title` | TEXT |  |  |  |
| `dept_id` | INTEGER | yes |  | → departments.id |
| `unit_id` | INTEGER | yes |  | → business_units.id |
| `vacancies` | INTEGER | yes | 1 |  |
| `emp_type` | TEXT | yes |  |  |
| `salary_range` | TEXT | yes |  |  |
| `posted_on` | TEXT | yes |  |  |
| `deadline` | TEXT | yes |  |  |
| `status` | TEXT |  | 'Open' |  |
| `description` | TEXT | yes |  |  |

### `candidates`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `job_id` | INTEGER | yes |  | → jobs.id |
| `name` | TEXT |  |  |  |
| `phone` | TEXT | yes |  |  |
| `email` | TEXT | yes |  |  |
| `source` | TEXT | yes |  |  |
| `expected_salary` | REAL | yes |  |  |
| `stage` | TEXT |  | 'Applied' |  |
| `rating` | INTEGER | yes |  |  |
| `interview_date` | TEXT | yes |  |  |
| `notes` | TEXT | yes |  |  |
| `created_at` | TEXT | yes |  |  |

### `reviews`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `emp_id` | INTEGER |  |  | → employees.id |
| `reviewer_id` | INTEGER | yes |  | → employees.id |
| `period` | TEXT |  |  |  |
| `quality` | INTEGER | yes |  |  |
| `productivity` | INTEGER | yes |  |  |
| `teamwork` | INTEGER | yes |  |  |
| `punctuality` | INTEGER | yes |  |  |
| `initiative` | INTEGER | yes |  |  |
| `score` | REAL | yes |  |  |
| `goals` | TEXT | yes |  |  |
| `comments` | TEXT | yes |  |  |
| `status` | TEXT |  | 'Draft' |  |
| `created_at` | TEXT | yes |  |  |

### `trainings`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `title` | TEXT |  |  |  |
| `category` | TEXT | yes |  |  |
| `trainer` | TEXT | yes |  |  |
| `start_date` | TEXT | yes |  |  |
| `hours` | REAL | yes |  |  |
| `venue` | TEXT | yes |  |  |
| `mode` | TEXT | yes |  |  |
| `cost` | REAL | yes |  |  |
| `status` | TEXT |  | 'Scheduled' |  |
| `description` | TEXT | yes |  |  |

### `training_participants`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `training_id` | INTEGER |  |  | primary key; → trainings.id |
| `emp_id` | INTEGER |  |  | primary key; → employees.id |
| `attended` | INTEGER |  | 0 |  |

Unique: (training_id, emp_id)

## Administration

### `assets`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `tag` | TEXT |  |  |  |
| `name` | TEXT |  |  |  |
| `category` | TEXT | yes |  |  |
| `serial` | TEXT | yes |  |  |
| `emp_id` | INTEGER | yes |  | → employees.id |
| `issued_on` | TEXT | yes |  |  |
| `value` | REAL | yes |  |  |
| `condition` | TEXT | yes | 'Good' |  |
| `status` | TEXT |  | 'In Stock' |  |
| `notes` | TEXT | yes |  |  |

Unique: (tag)

### `notices`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER |  |  | primary key |
| `posted_on` | TEXT |  |  |  |
| `title` | TEXT |  |  |  |
| `body` | TEXT | yes |  |  |
| `audience` | TEXT | yes | 'All Employees' |  |
| `priority` | TEXT | yes | 'Normal' |  |
| `expires_on` | TEXT | yes |  |  |
| `created_by` | TEXT | yes |  |  |
