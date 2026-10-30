# 10 · Operations: backup, security, maintenance, go-live

## Backups

Everything is in the **`data/`** folder: `hrmis.db` (plus `-wal` / `-shm` while running), `uploads/` and `backups/`.

| Method | How | When |
|---|---|---|
| Download from the app | **Settings → Download backup** saves `hrmis-backup-YYYYMMDD-HHMM.db` | weekly, and before every payroll finalize |
| Server copy | **Settings → Save backup on server** writes to `data/backups/` | before big changes |
| Folder copy | Stop HR-MIS, then copy the whole `data/` folder (includes uploaded documents) | monthly, to an external drive or cloud |
| Scheduled | Windows Task Scheduler running `robocopy C:\HR-MIS\data D:\Backups\HR-MIS /MIR` nightly, while HR-MIS is stopped or after a server backup | daily (recommended) |

App backups use SQLite's online backup API, so they are consistent even while people are working.
**Uploaded documents are not inside the `.db` file.** Include `data/uploads/` in your folder backups.

### Restore
1. Stop HR-MIS (close the console or press Ctrl+C).
2. Rename the current `data/hrmis.db` to keep it, and delete `hrmis.db-wal` and `hrmis.db-shm` if they exist.
3. Copy the backup file to `data/hrmis.db`.
4. Start HR-MIS again.

## Security hardening

| Item | Default | Production advice |
|---|---|---|
| Network exposure | only this PC (`127.0.0.1`) | use `--lan` only on a trusted office network; **never** expose port 8000 directly to the internet |
| HTTPS | none (plain HTTP on localhost) | for LAN or remote access, terminate TLS at a reverse proxy (Caddy, nginx, IIS ARR) and forward to `127.0.0.1:8000` |
| Demo accounts | present in demo mode | start production with `--empty`, or disable / re-password every demo user |
| Admin password | `Admin@123` | change it immediately (Change password) |
| Sessions | 12 hours | shorten with `HRMIS_SESSION_HOURS=8` |
| File system | `data/` readable by the Windows user | restrict the folder to the service account and HR administrators; enable BitLocker on the drive |
| Audit | every change is logged | review **Audit Trail** monthly; the log is append-only through the app |
| Least privilege | six roles | give HR officers `hr_officer` (no salaries); keep `admin` for IT |

Example **Caddyfile** for HTTPS on the LAN:

```text
hr.yourcompany.local {
    tls internal
    reverse_proxy 127.0.0.1:8000
}
```

Built-in protections: parameterised SQL everywhere (no string-built queries with user input), identifier whitelisting,
JSON-only API, request size limit (15 MB), request bodies always drained so keep-alive connections can't be corrupted,
strict Content-Security-Policy (no inline scripts), `X-Frame-Options: DENY`, static files confined to `frontend/`,
CSV exports neutralise spreadsheet formulas, PBKDF2 password hashing, hashed session tokens, login throttling,
server-side permission and team-scope checks on every endpoint, automatic login removal for leavers, and
protection against an administrator locking everyone out.

## Maintenance

| Task | How |
|---|---|
| Update HR-MIS | Stop it, back up `data/`, replace every folder **except `data/`** with the new version, start it, then refresh the browser (Ctrl + F5). The schema upgrades itself (`CREATE … IF NOT EXISTS`). See CHANGELOG.md for what changed |
| Check health | Settings → *Backup & system* shows the version, database size and record counts |
| Database size | grows by about 1 MB per 100 employees per year, plus documents |
| Logs | errors print in the console window; activity is in the Audit Trail |
| Run tests | `py -m unittest discover tests -v` |
| Regenerate API / schema docs | `py tools\gen_docs.py` |
| Locked out | `py tools\reset_admin.py` (with HR-MIS stopped) |

## Go-live checklist

**Setup**
- [ ] Fresh start: copy the program to the server, run `py run.py --empty` (or delete `data/` first)
- [ ] Sign in as `admin` / `Admin@123` and **change the password**
- [ ] **Settings:** company name and short name, address, employee ID prefix, office hours, grace, weekend days, probation months
- [ ] **Settings → Payroll rules** confirmed with finance (see 09-payroll-and-policy-rules.md)
- [ ] **Holidays** for the current and next year (confirm lunar dates)
- [ ] **Leave types** match the HR policy

**Organisation & people**
- [ ] **Organization:** business units → departments → designations and grades
- [ ] **Employees:** enter or import every active employee (ID, name, joining date, unit, department, designation, manager, gross, bank)
- [ ] Department heads set (Organization → Departments), so new joiners get the right default manager
- [ ] **Leave → Opening balances** for leave already taken this year and carried-forward earned leave
- [ ] **Loans** already running, with the correct outstanding amount (enter the remaining principal)

**Access**
- [ ] **Users & Roles:** one account per HR and payroll user and per line manager, linked to their employee record
- [ ] Employee self-service accounts (optional; can be created at hire with *Create login*)
- [ ] Remove or disable any demo accounts

**Parallel run**
- [ ] Run one month's payroll in HR-MIS alongside the current method and reconcile net pay per employee
- [ ] Back up, then go live

## Bulk-loading existing employees

The quickest route for hundreds of records is a one-off script that reads your Excel export (saved as CSV) and posts to `POST /api/employees`.
`tests/test_api.py` shows how to sign in and call the API from Python. Columns map one-to-one to the fields in [07-database-schema.md](07-database-schema.md) (`employees` table).
