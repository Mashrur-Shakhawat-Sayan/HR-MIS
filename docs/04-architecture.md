# 04 · Architecture

## Goals that shaped the design

1. **Runs anywhere with nothing to install** beyond Python: no pip, no Node, no database server, no internet.
2. **Clear compartments.** Each business domain is one backend module and one frontend page, connected only through a documented JSON API.
3. **Secure by default:** role-based permissions on every endpoint, data scoping, an audit trail, hashed passwords and a strict CSP.
4. **Easy to grow:** the same API can later sit on PostgreSQL and a production server (see [11-roadmap.md](11-roadmap.md)).

## Layers

```text
 Browser (any device)
 ┌──────────────────────────────────────────────────────────────────────┐
 │ index.html + css/app.css                                             │
 │ js/app.js ─ navigation, routing, permission-aware menu               │
 │ js/core/  api.js (fetch + token) · ui.js (forms, tables, modal)      │
 │           crud.js (generic list/form) · charts.js (SVG)              │
 │ js/pages/ one module per screen  ── calls ──┐                        │
 └─────────────────────────────────────────────┼────────────────────────┘
                                   HTTP JSON   │  Authorization: Bearer <token>
 Python server (run.py)                        ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ core/http.py   router · request/response · static files · errors     │
 │ core/security  sessions, password hashing, login throttling          │
 │ core/rbac      roles → permissions, team scoping                     │
 │ core/resource  generic CRUD endpoints from a field list              │
 │ core/audit     who / what / when log                                 │
 │ core/utils     settings, working-day calendar, validation            │
 ├──────────────────────────────────────────────────────────────────────┤
 │ modules/  auth · organization · employees · lifecycle · attendance   │
 │           leave · payroll · loans · claims · talent · admin          │
 │           dashboard · reports · system                               │
 ├──────────────────────────────────────────────────────────────────────┤
 │ core/db.py → SQLite (data/hrmis.db, WAL) · data/uploads · backups    │
 └──────────────────────────────────────────────────────────────────────┘
```

## Request lifecycle

1. `Handler._dispatch` first reads the whole request body (so an endpoint that ignores it can't leave bytes on a keep-alive connection), then splits `/api/*` (API) from everything else (static files from `frontend/`, with an SPA fallback to `index.html`).
2. `Router.match` finds the handler. `{id}` path parameters only match digits, so `/api/employees/lookup` never collides with `/api/employees/{id}`.
3. A **new SQLite connection** is opened for the request (`req.db`), with foreign keys on and a 15-second busy timeout.
4. Daily jobs run if this is the first request of the day (`utils.run_daily`). `security.authenticate` resolves the bearer token to a user plus permissions; `rbac.has_any` checks the route's permission.
5. The handler runs. Data scoping (own record, own team, everyone) is applied inside the module with `rbac.scope_emp_ids`.
6. On success the transaction is **committed**; on any error it is **rolled back**. `ApiError` becomes a JSON error, an `IntegrityError` becomes a friendly 409, and anything else becomes a 500 with a traceback printed in the console.
7. Security headers are added to every response: CSP `script-src 'self'`, `X-Frame-Options: DENY`, `nosniff` and a same-origin referrer policy.

## Generic resources

Most lists (units, departments, holidays, claims, jobs, assets, …) are declared in a few lines:

```python
Resource("assets", "assets",
         [Field("tag", required=True), Field("name", required=True), Field("emp_id", "fk"), ...],
         view_perm="assets.view", manage_perm="assets.manage",
         select="SELECT t.*, e.full_name FROM assets t LEFT JOIN employees e ON e.id = t.emp_id",
         search=("t.tag", "t.name"), filters=("t.status",), order="t.tag")
```

This produces list / read / create / update / delete endpoints with validation, search, filters, pagination and audit logging.
Hooks (`before_save`, `after_save`, `before_delete`) carry the business rules. For example, claims force `status = Pending` for self-service users, and reviews compute the score and enforce team scope.

Complex domains (employees, attendance, leave, payroll) use hand-written endpoints in their module.

## Frontend conventions

- **Design system** (`css/app.css`): colour, type and radius tokens on `:root`, redefined for dark mode (`[data-theme=dark]` or the OS setting). Bottle green = navigation and primary actions; marigold = needs attention only; red = destructive or problem only. Fonts are bundled in `frontend/fonts/`; icons are inline SVG from `js/core/icons.js` (`ic('pencil')`).

- **No inline JavaScript.** Markup uses `data-act="module:action"` (click), `data-change` and `data-input`; handlers register with `on('module:action', fn)`. This is what lets the server send a strict CSP.
- Each page exports `render(main, ctx)`, where `ctx` holds the user, `can(perm)`, `setTitle()` and `refreshNav()`. Pages keep their own state object (`S`) and re-render themselves.
- Forms are declared as field lists (`{k, l, t, req, o, w}`) and built by `formHTML` / `readForm`. Lookup field types (`emp`, `dept`, `unit`, `desig`, `leave`, `job`) fill themselves from cached API calls.
- The UI hides what a role cannot do, but **the server enforces every rule**. The UI is never trusted.

## Data & files

| Path | Content |
|---|---|
| `data/hrmis.db` (+ `-wal`, `-shm`) | all records |
| `data/uploads/` | employee documents, stored under random names; original names are kept in `emp_documents` |
| `data/backups/` | server-side backups and pre-reset snapshots |

The schema (`backend/db/schema.sql`) is idempotent and runs at every start. Payslips store a **snapshot** of name, designation, department and bank details, so historic payslips never change when an employee's record does.

## Adding a new module (example: "Shifts")

1. **Schema:** add `CREATE TABLE IF NOT EXISTS shifts (...)` to `schema.sql`.
2. **Permissions:** add `shifts.view` / `shifts.manage` to `PERMISSIONS` in `core/rbac.py` and grant them to roles.
3. **Backend:** create `backend/modules/shifts.py` with a `Resource(...)` and any custom `@route` handlers, then import it in `modules/__init__.py`.
4. **Frontend:** create `frontend/js/pages/shifts.js` exporting `render(main, ctx)` (often a single `crudView`) and add a line to `ROUTES` in `js/app.js`.
5. **Docs:** run `python tools/gen_docs.py`, add a section to `05-modules.md`, and add tests in `tests/test_api.py`.

## Design decisions

| Decision | Why | Trade-off |
|---|---|---|
| Python stdlib server (`ThreadingHTTPServer`) | Zero install, easy to audit | Fine for tens of concurrent users; use a WSGI/ASGI server for more (roadmap) |
| SQLite in WAL mode | Single file, zero admin, transactional, easy backup | One writer at a time; PostgreSQL for group-wide scale |
| Bearer token in `sessionStorage` | Not sent automatically, so CSRF does not apply; cleared when the tab closes | Re-login per browser session |
| Server-side scoping | A line manager's API calls can't return other teams' data, whatever the UI does | Slightly more code per module |
| Vanilla JS modules, no build | Works offline, nothing to compile, readable | Less tooling than React; the API boundary makes a later rewrite easy |
