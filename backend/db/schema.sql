-- =====================================================================
-- HR-MIS database schema (SQLite)
-- All statements are idempotent (IF NOT EXISTS) so this runs on every start.
-- Dates are ISO text: YYYY-MM-DD; timestamps YYYY-MM-DDTHH:MM:SS; months YYYY-MM.
-- Money is stored as REAL in BDT.
-- =====================================================================

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- ---------------------------------------------------------------- organisation
CREATE TABLE IF NOT EXISTS business_units (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, code TEXT, location TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS departments (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, unit_id INTEGER REFERENCES business_units(id),
  head_emp_id INTEGER, cost_center TEXT, created_at TEXT,
  UNIQUE(name, unit_id)
);
CREATE TABLE IF NOT EXISTS designations (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL UNIQUE, grade TEXT, level INTEGER, created_at TEXT
);

-- ---------------------------------------------------------------- people
CREATE TABLE IF NOT EXISTS employees (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL,
  gender TEXT, dob TEXT, marital_status TEXT, blood_group TEXT,
  phone TEXT, email TEXT, nid TEXT, tin TEXT, father_name TEXT, mother_name TEXT,
  present_address TEXT, permanent_address TEXT, emergency_name TEXT, emergency_phone TEXT,
  unit_id INTEGER REFERENCES business_units(id),
  dept_id INTEGER REFERENCES departments(id),
  designation_id INTEGER REFERENCES designations(id),
  grade TEXT,
  emp_type TEXT NOT NULL DEFAULT 'Permanent',      -- Permanent | Probation | Contract | Intern | Part-time
  join_date TEXT NOT NULL, confirm_date TEXT,
  manager_id INTEGER REFERENCES employees(id),
  status TEXT NOT NULL DEFAULT 'Active',          -- Active | On Notice | Resigned | Terminated | Retired
  exit_date TEXT, exit_reason TEXT,
  gross_salary REAL NOT NULL DEFAULT 0,
  bank_name TEXT, bank_account TEXT, pf_member INTEGER NOT NULL DEFAULT 1,
  created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_emp_dept ON employees(dept_id);
CREATE INDEX IF NOT EXISTS ix_emp_status ON employees(status);
CREATE INDEX IF NOT EXISTS ix_emp_manager ON employees(manager_id);

CREATE TABLE IF NOT EXISTS emp_documents (
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  title TEXT NOT NULL, doc_type TEXT, filename TEXT NOT NULL, stored_name TEXT NOT NULL,
  size INTEGER, content_type TEXT, uploaded_by TEXT, uploaded_at TEXT
);
CREATE TABLE IF NOT EXISTS emp_events (                -- career history
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,                          -- Joining | Confirmation | Promotion | Transfer | Increment | Resignation | Termination | Retirement | Re-hire
  effective_date TEXT NOT NULL, old_value TEXT, new_value TEXT, details TEXT,
  created_by TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS emp_tasks (                 -- onboarding / offboarding checklists
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  category TEXT NOT NULL DEFAULT 'Onboarding', task TEXT NOT NULL, owner TEXT, due_date TEXT,
  done INTEGER NOT NULL DEFAULT 0, done_at TEXT
);
CREATE TABLE IF NOT EXISTS disciplinary (
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  action_date TEXT NOT NULL, action_type TEXT NOT NULL, reason TEXT, issued_by TEXT,
  status TEXT NOT NULL DEFAULT 'Open', resolution TEXT, created_at TEXT
);

-- ---------------------------------------------------------------- security
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'employee', emp_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
  is_active INTEGER NOT NULL DEFAULT 1, must_change_pw INTEGER NOT NULL DEFAULT 0,
  last_login TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT, expires_at TEXT, ip TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, user_id INTEGER, username TEXT, action TEXT NOT NULL,
  entity TEXT, entity_id INTEGER, summary TEXT, details TEXT, ip TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_log(ts);

-- ---------------------------------------------------------------- time
CREATE TABLE IF NOT EXISTS holidays (
  id INTEGER PRIMARY KEY, date TEXT NOT NULL UNIQUE, name TEXT NOT NULL, type TEXT DEFAULT 'National'
);
CREATE TABLE IF NOT EXISTS attendance (
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  date TEXT NOT NULL, status TEXT NOT NULL,           -- P present | L late | HD half day | A absent | LV leave | WFH | OD on duty
  check_in TEXT, check_out TEXT, source TEXT DEFAULT 'Manual', note TEXT,
  UNIQUE(emp_id, date)
);
CREATE INDEX IF NOT EXISTS ix_att_date ON attendance(date);

CREATE TABLE IF NOT EXISTS leave_types (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, days_per_year REAL NOT NULL DEFAULT 0,
  gender TEXT NOT NULL DEFAULT 'Any', paid INTEGER NOT NULL DEFAULT 1, calendar_days INTEGER NOT NULL DEFAULT 0,
  carry_forward INTEGER NOT NULL DEFAULT 0, max_carry REAL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, color TEXT
);
CREATE TABLE IF NOT EXISTS leave_requests (
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  leave_type_id INTEGER NOT NULL REFERENCES leave_types(id),
  from_date TEXT NOT NULL, to_date TEXT NOT NULL, days REAL NOT NULL, reason TEXT,
  status TEXT NOT NULL DEFAULT 'Pending',            -- Pending | Approved | Rejected | Cancelled
  applied_at TEXT, applied_by TEXT, decided_by TEXT, decided_at TEXT, remarks TEXT
);
CREATE INDEX IF NOT EXISTS ix_leave_emp ON leave_requests(emp_id);
CREATE TABLE IF NOT EXISTS leave_adjustments (         -- opening balance / carry-forward / encashment
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  leave_type_id INTEGER NOT NULL REFERENCES leave_types(id), year INTEGER NOT NULL,
  days REAL NOT NULL, note TEXT, created_by TEXT, created_at TEXT
);

-- ---------------------------------------------------------------- pay
CREATE TABLE IF NOT EXISTS payroll_runs (
  id INTEGER PRIMARY KEY, month TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'Draft',  -- Draft | Finalized | Paid
  include_bonus INTEGER NOT NULL DEFAULT 0, notes TEXT,
  created_by TEXT, created_at TEXT, finalized_by TEXT, finalized_at TEXT, paid_at TEXT
);
CREATE TABLE IF NOT EXISTS payslips (
  id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
  emp_id INTEGER NOT NULL REFERENCES employees(id),
  emp_code TEXT, emp_name TEXT, department TEXT, designation TEXT, bank_name TEXT, bank_account TEXT, tin TEXT,
  full_gross REAL, gross REAL, basic REAL, house_rent REAL, medical REAL, conveyance REAL,
  pay_days INTEGER, month_days INTEGER,
  ot_hours REAL DEFAULT 0, ot_amount REAL DEFAULT 0, bonus REAL DEFAULT 0, additions REAL DEFAULT 0, earnings REAL,
  lwp_days REAL DEFAULT 0, late_count INTEGER DEFAULT 0, pf REAL DEFAULT 0, pf_employer REAL DEFAULT 0, tax REAL DEFAULT 0,
  lwp_deduction REAL DEFAULT 0, loan_deduction REAL DEFAULT 0, other_deduction REAL DEFAULT 0,
  deductions REAL, net REAL, remarks TEXT,
  UNIQUE(run_id, emp_id)
);
CREATE TABLE IF NOT EXISTS loans (
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id),
  loan_type TEXT NOT NULL, principal REAL NOT NULL, installment REAL NOT NULL, start_month TEXT NOT NULL,
  issued_on TEXT, purpose TEXT, status TEXT NOT NULL DEFAULT 'Active',   -- Pending | Active | Closed | Rejected
  approved_by TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS loan_repayments (
  id INTEGER PRIMARY KEY, loan_id INTEGER NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
  month TEXT NOT NULL, amount REAL NOT NULL, run_id INTEGER REFERENCES payroll_runs(id) ON DELETE CASCADE, note TEXT
);
CREATE TABLE IF NOT EXISTS claims (
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id),
  claim_date TEXT NOT NULL, category TEXT NOT NULL, amount REAL NOT NULL, description TEXT,
  status TEXT NOT NULL DEFAULT 'Pending',              -- Pending | Approved | Rejected | Paid
  decided_by TEXT, decided_at TEXT, created_at TEXT
);

-- ---------------------------------------------------------------- talent
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, dept_id INTEGER REFERENCES departments(id),
  unit_id INTEGER REFERENCES business_units(id), vacancies INTEGER DEFAULT 1, emp_type TEXT,
  salary_range TEXT, posted_on TEXT, deadline TEXT, status TEXT NOT NULL DEFAULT 'Open', description TEXT
);
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY, job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL, name TEXT NOT NULL,
  phone TEXT, email TEXT, source TEXT, expected_salary REAL, stage TEXT NOT NULL DEFAULT 'Applied',
  rating INTEGER, interview_date TEXT, notes TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY, emp_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  reviewer_id INTEGER REFERENCES employees(id), period TEXT NOT NULL,
  quality INTEGER, productivity INTEGER, teamwork INTEGER, punctuality INTEGER, initiative INTEGER,
  score REAL, goals TEXT, comments TEXT, status TEXT NOT NULL DEFAULT 'Draft', created_at TEXT
);
CREATE TABLE IF NOT EXISTS trainings (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT, trainer TEXT, start_date TEXT,
  hours REAL, venue TEXT, mode TEXT, cost REAL, status TEXT NOT NULL DEFAULT 'Scheduled', description TEXT
);
CREATE TABLE IF NOT EXISTS training_participants (
  training_id INTEGER NOT NULL REFERENCES trainings(id) ON DELETE CASCADE,
  emp_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  attended INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (training_id, emp_id)
);

-- ---------------------------------------------------------------- administration
CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY, tag TEXT NOT NULL UNIQUE, name TEXT NOT NULL, category TEXT, serial TEXT,
  emp_id INTEGER REFERENCES employees(id) ON DELETE SET NULL, issued_on TEXT, value REAL,
  condition TEXT DEFAULT 'Good', status TEXT NOT NULL DEFAULT 'In Stock', notes TEXT
);
CREATE TABLE IF NOT EXISTS notices (
  id INTEGER PRIMARY KEY, posted_on TEXT NOT NULL, title TEXT NOT NULL, body TEXT, audience TEXT DEFAULT 'All Employees',
  priority TEXT DEFAULT 'Normal', expires_on TEXT, created_by TEXT
);
