# 11 · Roadmap to enterprise scale

Version 1.0 is a complete HR system for one company or a mid-sized group running on a single server.
A multi-billion-taka group with tens of thousands of employees, many sister concerns and plant sites needs the additions below.
They are listed in a sensible order; each builds on the module and API boundaries that already exist.

## Phase 1 — Production platform (scale & availability)

| Item | Why | Approach |
|---|---|---|
| PostgreSQL | many concurrent writers, replication, point-in-time recovery | `core/db.py` is the only place that talks to SQLite: swap in `psycopg` and translate `schema.sql` (types, `ON CONFLICT` already compatible) |
| Production web server | hundreds of concurrent users | wrap the router as WSGI/ASGI (gunicorn / uvicorn behind nginx), or port modules to FastAPI one by one; the URL contract stays the same |
| Single sign-on | one company login | SAML / OpenID Connect with Microsoft Entra ID or Google Workspace; map groups to HR-MIS roles |
| HTTPS, backups, monitoring | operations standard | reverse proxy with TLS, nightly `pg_dump` and WAL archiving, health endpoint, centralised logs |
| File storage | documents at scale | move `data/uploads` to object storage (S3-compatible / SharePoint) with virus scanning |

## Phase 2 — Group structure & compliance

- **Multi-company / legal entities:** a `company_id` on units, employees and payroll; per-company settings, payroll calendars, bank accounts and payslip branding; consolidated group reports.
- **Bangladesh income-tax engine:** annual projection, slabs and threshold by gender/age category, investment rebate, monthly TDS spreading, year-end salary certificate. Plugs into `payroll.compute()`.
- **Final settlement:** pending salary, earned-leave encashment, gratuity, PF employer share vesting, notice-pay and loan recovery, with a printable settlement sheet.
- **Gratuity & PF trust ledgers:** member statements, interest allocation, loans against PF.
- **Wage-board / worker grades:** separate structures for factory workers, piece rates and attendance bonus.
- **Statutory reports:** factory register formats, DIFE inspection reports, labour-law leave registers.

## Phase 3 — Time at plant scale

- **Shifts and rosters:** rotating, night and split shifts; shift-wise late and OT rules; weekly-off rotation.
- **Direct biometric integration:** scheduled pull from ZKTeco / Suprema devices instead of CSV import.
- **Overtime approvals:** pre-approval, caps and OT budgets per department.
- **Geo-fenced mobile check-in** for field sales.

## Phase 4 — Employee experience

- **Mobile app** (PWA first) for check-in, leave, payslips, approvals and notices.
- **Notifications:** email, SMS (local gateways) and push for approvals, payslip release, birthdays and expiring documents.
- **Multi-level approval chains:** e.g. supervisor → department head → HR, configurable per leave type, claim amount or loan size.
- **Bangla interface:** all labels are already in the frontend page files, ready for a translation layer.
- **Employee documents with e-signature:** appointment letters, policy acknowledgements.

## Phase 5 — Talent & analytics

- **Recruitment portal:** public career page, application forms, CV parsing, interview scheduling, offer letters.
- **Goals / OKRs**, 360° feedback, calibration and the link from ratings to increments.
- **Learning:** course catalogue, e-learning links, certification expiry tracking (safety, licences).
- **Succession planning** and a skills matrix.
- **Analytics:** attrition prediction, absenteeism hot-spots, overtime cost trends, diversity dashboards; a read-only warehouse feed (Power BI).

## Phase 6 — Integrations

- ERP / accounting: payroll journal export to Tally, SAP or Oracle; cost-centre allocation.
- Banks: direct salary-file formats (BEFTN / bank-specific CSV), payment status import.
- Directory: auto-provision and deprovision email and system accounts from joiner and leaver events.
- Open API with per-application tokens and webhooks for joiner, leaver, leave-approved and payroll-finalized events.

---

### What already supports this growth
- Clean **module boundaries** (one backend file and one page per domain) and a fully documented **JSON API**.
- **RBAC with data scoping** and an **audit trail** built into the core rather than bolted on.
- **Payslip snapshots**, so historic payroll stays correct when records change.
- **Automated tests** for every critical workflow, so refactors such as the PostgreSQL move can be verified.
