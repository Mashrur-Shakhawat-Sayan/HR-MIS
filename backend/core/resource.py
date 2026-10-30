"""Generic CRUD resources.

A `Resource` turns a table definition into five REST endpoints:

    GET    /api/<name>          list   (?q= search, ?<filter>= exact match, ?limit=&offset=)
    GET    /api/<name>/{id}     read
    POST   /api/<name>          create
    PUT    /api/<name>/{id}     update (partial)
    DELETE /api/<name>/{id}     delete

Modules customise behaviour with hooks instead of re-writing routes.
Every write is recorded in the audit trail.
"""
from . import audit, db, rbac
from .http import ApiError, route
from .utils import clean, now


class Resource:
    def __init__(self, name, table, fields, view_perm, manage_perm, *, select=None, search=(), filters=(),
                 order="t.id DESC", label=None, scope_perm=None, scope_col="t.emp_id",
                 before_save=None, after_save=None, before_delete=None, timestamps=False, extra_where=None):
        self.name, self.table, self.fields = name, table, fields
        self.view_perm, self.manage_perm = view_perm, manage_perm
        self.select = select or f"SELECT t.* FROM {table} t"
        self.search, self.filters, self.order = search, filters, order
        self.label = label or name.rstrip("s").replace("-", " ").capitalize()
        self.scope_perm, self.scope_col = scope_perm, scope_col
        self.before_save, self.after_save, self.before_delete = before_save, after_save, before_delete
        self.timestamps = timestamps
        self.extra_where = extra_where
        self._register()

    # ------------------------------------------------------------ queries
    def _where(self, req, extra=None):
        where, params = [], []
        if self.scope_perm:
            ids = rbac.scope_emp_ids(req.db, req.user, self.scope_perm)
            if ids is not None:
                where.append(f"{self.scope_col} IN ({','.join('?' * len(ids)) or 'NULL'})")
                params += ids
        if self.extra_where:
            extra_sql = self.extra_where(req)
            if extra_sql:
                where.append(extra_sql[0])
                params += extra_sql[1]
        term = req.q("q")
        if term and self.search:
            where.append("(" + " OR ".join(f"{c} LIKE ?" for c in self.search) + ")")
            params += [f"%{term}%"] * len(self.search)
        for f in self.filters:
            v = req.q(f.split(".")[-1])
            if v is not None:
                where.append(f"{f} = ?")
                params.append(v)
        if extra:
            where.append(extra[0])
            params += extra[1]
        return (" WHERE " + " AND ".join(where)) if where else "", params

    def fetch(self, req, row_id):
        where, params = self._where(req, ("t.id = ?", [row_id]))
        row = db.one(req.db, f"{self.select}{where}", params)
        if not row:
            raise ApiError(404, f"{self.label} not found")
        return row

    # ------------------------------------------------------------ routes
    def _register(self):
        base = f"/api/{self.name}"
        route("GET", base, self.view_perm)(self.list)
        route("GET", base + "/{id}", self.view_perm)(lambda req: self.fetch(req, req.int_param()))
        route("POST", base, self.manage_perm)(self.create)
        route("PUT", base + "/{id}", self.manage_perm)(self.update)
        route("DELETE", base + "/{id}", self.manage_perm)(self.delete)

    def list(self, req):
        where, params = self._where(req)
        limit = min(int(req.q("limit", 1000)), 5000)
        offset = int(req.q("offset", 0))
        total = db.scalar(req.db, f"SELECT COUNT(*) FROM ({self.select}{where})", params)
        rows = db.q(req.db, f"{self.select}{where} ORDER BY {self.order} LIMIT ? OFFSET ?", params + [limit, offset])
        return {"items": rows, "total": total}

    def create(self, req):
        data = clean(self.fields, req.body)
        if self.before_save:
            self.before_save(req, data, None)
        if self.timestamps:
            data["created_at"] = now()
        new_id = db.insert(req.db, self.table, data)
        row = self.fetch(req, new_id)
        if self.after_save:
            self.after_save(req, row, None)
        audit.log(req, "create", self.table, new_id, f"Created {self.label.lower()}", data)
        return row

    def update(self, req):
        row_id = req.int_param()
        existing = self.fetch(req, row_id)
        data = clean(self.fields, req.body, partial=True)
        if self.before_save:
            self.before_save(req, data, existing)
        db.update(req.db, self.table, row_id, data)
        row = self.fetch(req, row_id)
        if self.after_save:
            self.after_save(req, row, existing)
        changed = {k: v for k, v in data.items() if existing.get(k) != v}
        audit.log(req, "update", self.table, row_id, f"Updated {self.label.lower()}", changed)
        return row

    def delete(self, req):
        row_id = req.int_param()
        existing = self.fetch(req, row_id)
        if self.before_delete:
            self.before_delete(req, existing)
        req.db.execute(f"DELETE FROM {db.ident(self.table)} WHERE id = ?", (row_id,))
        audit.log(req, "delete", self.table, row_id, f"Deleted {self.label.lower()}", existing)
        return {"ok": True}
