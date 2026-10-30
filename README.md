# HR-MIS — Human Resource Management Information System

**Version 1.1.1** · see [CHANGELOG.md](CHANGELOG.md) for what changed.

A complete, self-hosted HR system for any group of companies or large organisation, demonstrated with **Sonar Tori Group**, a fictional Bangladeshi conglomerate.
It runs on a single Windows PC or an office server, opens in any modern browser, and needs nothing but **Python 3.10+**.
There are no packages to install, no internet connection is required and no data leaves your machine.

| Area | What you get |
|---|---|
| **People** | Employee master data (30+ fields), documents, career history, onboarding/offboarding checklists, disciplinary register, org chart, ID cards |
| **Organisation** | Business units (sister concerns), departments with heads and cost centres, designations and grades |
| **Time & leave** | Daily attendance with automatic late marking, monthly register, device CSV import, self check-in, holiday calendar, six leave types with balances, carry-forward and an approval workflow |
| **Compensation** | Bangladesh-style payroll (basic / house rent / medical / conveyance, overtime, festival bonus, PF, TDS, leave-without-pay, loan recovery), payslips with amount in words, bank advice, PF statement, loans & salary advances, expense claims |
| **Talent** | Job openings, candidate pipeline board with one-click onboarding, five-factor performance reviews, training programs with participants and attendance |
| **Administration** | Asset register (issue/return), notice board, 17 standard reports with CSV export, users & roles, permission matrix, full audit trail, settings, one-click backups |
| **Self-service** | Every employee gets *My workspace*: profile, check-in/out, attendance, leave applications, payslips, loan requests and expense claims |
| **Interface** | Light and dark themes, Ctrl + K search for any page or employee, bundled fonts and icons (works fully offline), phone-friendly layout, keyboard focus and reduced-motion support |
| **Security** | Six roles with 41 permissions, line managers limited to their own team, salary fields hidden from non-payroll staff, PBKDF2 password hashing, login throttling, strict Content-Security-Policy, audit of every change |

## Who it's for

Any organisation with several companies under one group, or one large company with many departments. Examples are conglomerates such as
**Meghna Group (MGI, the maker of Fresh)**, **Akij Group** or **United Group**, a large single company such as **Grameenphone**,
or a mid-sized firm with a single office. Business units, departments, designations and grades, leave types, holidays,
office hours, payroll percentages and the employee ID prefix are all configured inside the app, so it fits a new company
without changing any code. The defaults follow Bangladesh practice (Labour Act 2006 leave, BDT, Friday–Saturday weekend).

The demo data uses **Sonar Tori Group**, a fictional conglomerate with a head office and five sister concerns (paper, cement,
LP gas, food & beverage and steel), 36 employees and two months of history. A fresh install (`--empty`) starts with no
company data at all. Company names in this README are only examples of the kind of organisation HR-MIS suits; the
project is not affiliated with or endorsed by any of them.

---

## Quick start (Windows)

1. Install **Python 3.10 or newer** from <https://www.python.org/downloads/>. On the first installer screen, tick **"Add python.exe to PATH"**.
2. Double-click **`start.bat`** in this folder.
3. Your browser opens at **http://127.0.0.1:8000**. Sign in with one of the demo accounts below.

The first start creates `data/hrmis.db` and fills it with a demo organisation: 36 employees across 6 business units, two months of attendance, leave, claims, loans, recruitment, reviews, training, assets and one paid payroll month.

```text
python run.py                 start (demo data on first run)
python run.py --empty         first run with no demo data (admin account only)
python run.py --reset-demo    back up the current database, then reload fresh demo data
python run.py --lan           let other PCs on the office network connect
python run.py --port 9000     use a different port
```

macOS / Linux: `./start.sh` or `python3 run.py`.

### Demo accounts

| Username | Password | Role | Try this |
|---|---|---|---|
| `admin` | `Admin@123` | System Administrator | Users & roles, settings, audit trail, backups |
| `hr.manager` | `Hr@12345` | HR Manager | Everything HR, including payroll and salaries |
| `hr.officer` | `Hr@12345` | HR Officer | Employees, attendance, leave, recruitment (salaries hidden) |
| `payroll` | `Pay@12345` | Payroll Officer | Generate → finalize → pay payroll, loans, claims |
| `manager` | `Mgr@12345` | Line Manager (IT) | Approve the team's leave and claims, review the team (sees only their own team) |
| `employee` | `Emp@12345` | Employee | My Workspace: check in, apply for leave, view payslips |

On the sign-in page, open **Demo accounts** and select a row to fill the form.

> **Before real use:** run `python run.py --empty` on a fresh copy, or change every password and disable the demo accounts. See [docs/10-operations.md](docs/10-operations.md#go-live-checklist).

---

## Documentation

| # | Document | For |
|---|---|---|
| 01 | [Overview & feature catalogue](docs/01-overview.md) | Everyone |
| 02 | [Installation & running](docs/02-installation.md) | IT / admin |
| 03 | [User guide (by role and task)](docs/03-user-guide.md) | HR, payroll, managers, employees |
| 04 | [Architecture](docs/04-architecture.md) | Developers |
| 05 | [Module reference](docs/05-modules.md) | Developers, power users |
| 06 | [API reference](docs/06-api-reference.md) | Developers, integrators |
| 07 | [Database schema](docs/07-database-schema.md) | Developers, DBAs |
| 08 | [Roles & permissions](docs/08-roles-and-permissions.md) | Admin, auditors |
| 09 | [Payroll & policy rules](docs/09-payroll-and-policy-rules.md) | HR, payroll, finance |
| 10 | [Operations: backup, security, go-live](docs/10-operations.md) | IT / admin |
| 11 | [Roadmap to enterprise scale](docs/11-roadmap.md) | Management, IT |

## Project layout

```text
HR-MIS/
├── run.py                    launcher (creates DB, seeds demo data, starts server, opens browser)
├── start.bat / start.sh      double-click launchers
├── backend/
│   ├── config.py             paths, host/port, session length (env-var overridable)
│   ├── core/                 framework: http router, db, security, rbac, audit, generic resources, utils
│   ├── db/                   schema.sql (30 tables) and seed.py (base + demo data)
│   └── modules/              one file per business domain — each documents its own endpoints
│       ├── auth.py  organization.py  employees.py  lifecycle.py  attendance.py  leave.py
│       ├── payroll.py  loans.py  claims.py  talent.py  admin.py  dashboard.py  reports.py  system.py
├── frontend/
│   ├── index.html            single-page app shell + sign-in screen
│   ├── css/app.css           design system (tokens, light/dark themes, components)
│   ├── fonts/                Instrument Sans + Bricolage Grotesque (SIL Open Font License)
│   └── js/
│       ├── app.js            navigation, routing, permissions, Ctrl+K search, theme switch
│       ├── theme.js          applies the saved theme before the page paints
│       ├── core/             api client, UI toolkit, icons, charts, generic CRUD view
│       └── pages/            one file per screen (24 pages)
├── tests/
│   ├── test_api.py           25 API tests: workflows, security, regressions
│   └── e2e_features.py       browser test that uses every feature as every role
├── tools/gen_docs.py         regenerates the API, schema and roles references
├── tools/reset_admin.py      emergency reset of the admin password
├── push-to-github.bat        one-click upload to GitHub (runs tools/push_to_github.ps1)
├── CHANGELOG.md              what changed in each version
├── docs/                     documentation (above)
└── data/                     created at runtime: hrmis.db, uploads/, backups/   ← back this up
```

## Tests

```bash
python -m unittest discover tests -v
```

The API tests start a private server on a temporary database. They cover sign-in, role security, employee creation, promotions, leave apply/approve/cancel, payroll generate → finalize → pay, claims, attendance import, every report, backups, settings validation and a regression test for every fixed bug.

The browser test signs in as each of the six roles and uses every screen and action. It fails on any browser error, failed server call or error message. It needs Playwright (`pip install playwright` then `playwright install chromium`):

```bash
python run.py --reset-demo --no-browser --port 8765      # in one window (uses demo data)
python tests/e2e_features.py                              # in another
```

## Upload to GitHub

Double-click **`push-to-github.bat`**. It opens a GitHub sign-in window, creates the private repository
`Mashrur-Shakhawat-Sayan/HR-MIS` if it does not exist yet, and uploads every file. The `data` folder (employee
records, salaries, uploaded documents) is never uploaded. Run it again whenever you want to upload changes. To use a different
account or repository name, edit the first lines of `tools/push_to_github.ps1`.

## Technology

Python 3 standard library only (`http.server`, `sqlite3`, `hashlib`), plus vanilla JavaScript ES modules with no build step and no CDN. Fonts and icons are bundled. That keeps it portable, auditable and free of supply-chain risk.
For a group-wide deployment with thousands of concurrent users, see [the roadmap](docs/11-roadmap.md): the module boundaries and API are designed to move to PostgreSQL and a production web server without changing the frontend.
