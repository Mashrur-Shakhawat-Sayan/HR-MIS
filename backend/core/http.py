"""Minimal HTTP framework built on http.server.

* `route()` registers an API handler for a method + path pattern
  (e.g. ``/api/employees/{id}``) together with the permission it needs.
* Every API request gets its own SQLite connection (``req.db``) that is
  committed when the handler returns and rolled back on any error.
* Files under ``frontend/`` are served as static assets.
"""
import csv
import io
import json
import mimetypes
import os
import re
import sqlite3
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .. import config
from . import db as dbmod
from . import rbac, security


class ApiError(Exception):
    """Raise inside a handler to return a clean JSON error to the client."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Response:
    def __init__(self, body=b"", status=200, content_type="application/json; charset=utf-8", headers=None):
        self.body = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.status = status
        self.content_type = content_type
        self.headers = headers or {}

    @classmethod
    def json(cls, data, status=200):
        return cls(json.dumps(data, default=str, ensure_ascii=False), status)

    @classmethod
    def file(cls, data, filename, content_type="application/octet-stream"):
        ascii_name = re.sub(r"[^A-Za-z0-9.\- ]", "_", filename) or "download"
        utf8_name = urllib.parse.quote(filename, safe="")
        return cls(data, 200, content_type,
                   {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"})

    @classmethod
    def csv(cls, filename, rows):
        def safe(v):
            # Text starting with = + - @ would be run as a formula by Excel; prefix it so it stays text.
            if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
                return "'" + v
            return v
        buf = io.StringIO()
        csv.writer(buf).writerows([[safe(c) for c in row] for row in rows])
        return cls.file(("﻿" + buf.getvalue()).encode("utf-8"), filename, "text/csv; charset=utf-8")


def read_body(handler):
    """Always consume the request body, even when the endpoint ignores it.

    With HTTP/1.1 keep-alive an unread body would stay in the socket and be parsed as the start of the
    next request on the same connection (which then fails with 501). Oversized bodies are not read;
    the connection is closed instead. Returns the raw bytes, or None when the body is too large.
    """
    try:
        length = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        length = 0
    if length > config.MAX_BODY_BYTES:
        handler.close_connection = True
        return None
    return handler.rfile.read(length) if length > 0 else b""


class Request:
    def __init__(self, handler, method, path, query, params, raw=b""):
        self.method = method
        self.path = path
        self.query = query
        self.params = params
        self.headers = handler.headers
        self.ip = handler.client_address[0]
        self._handler = handler
        self._body = None
        self.user = None
        self.db = None
        self._raw = raw

    @property
    def body(self):
        if self._body is None:
            if self._raw is None:
                raise ApiError(413, "Request is too large (limit 15 MB)")
            try:
                self._body = json.loads(self._raw.decode("utf-8")) if self._raw else {}
            except ValueError:
                raise ApiError(400, "Invalid JSON body")
            if not isinstance(self._body, dict):
                raise ApiError(400, "JSON body must be an object")
        return self._body

    def q(self, key, default=None):
        v = self.query.get(key)
        return default if v in (None, "") else v

    def int_param(self, key="id"):
        try:
            return int(self.params[key])
        except (KeyError, ValueError):
            raise ApiError(400, f"Invalid {key}")


class Router:
    def __init__(self):
        self.routes = []

    def add(self, method, pattern, fn, perm=None, auth=True):
        # {id} and {*_id} only match digits, so /api/x/lookup never collides with /api/x/{id}
        def param(m):
            name = m.group(1)
            return f"(?P<{name}>\\d+)" if name == "id" or name.endswith("_id") else f"(?P<{name}>[^/]+)"
        regex = "^" + re.sub(r"\{(\w+)\}", param, pattern) + "$"
        self.routes.append((method, re.compile(regex), fn, perm, auth, pattern))

    def match(self, method, path):
        allowed = False
        for m, rx, fn, perm, auth, _ in self.routes:
            mt = rx.match(path)
            if mt:
                if m == method:
                    return fn, mt.groupdict(), perm, auth
                allowed = True
        return ("METHOD", None, None, None) if allowed else None


router = Router()


def route(method, pattern, perm=None, auth=True):
    """Decorator: register an API handler. `perm` may be a string or a list (any-of)."""
    def deco(fn):
        router.add(method, pattern, fn, perm, auth)
        return fn
    return deco


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; frame-ancestors 'none'",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "HR-MIS"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep the console quiet; errors are printed separately
        pass

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    # ------------------------------------------------------------------
    def _dispatch(self, method):
        parts = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parts.path)
        query = dict(urllib.parse.parse_qsl(parts.query))
        if path.startswith("/api/"):
            raw = read_body(self)  # always drain first, whatever happens next
            self._send(self._api(method, path, query, raw))
        elif method == "GET":
            read_body(self)
            self._send(self._static(path))
        else:
            read_body(self)
            self._send(Response.json({"error": "Not found"}, 404))

    def _api(self, method, path, query, raw=b""):
        found = router.match(method, path)
        if not found:
            return Response.json({"error": "Endpoint not found"}, 404)
        fn, params, perm, auth = found
        if fn == "METHOD":
            return Response.json({"error": "Method not allowed"}, 405)
        req = Request(self, method, path, query, params, raw)
        conn = dbmod.connect()
        req.db = conn
        try:
            from .utils import run_daily  # local import: utils imports ApiError from this module
            run_daily(conn)
            if auth:
                req.user = security.authenticate(conn, self.headers.get("Authorization", ""))
                if not req.user:
                    raise ApiError(401, "Your session has expired. Please sign in again.")
                if perm and not rbac.has_any(req.user, perm):
                    raise ApiError(403, "You do not have permission to do this.")
            result = fn(req)
            conn.commit()
            return result if isinstance(result, Response) else Response.json(result)
        except ApiError as e:
            conn.rollback()
            return Response.json({"error": e.message}, e.status)
        except sqlite3.IntegrityError as e:
            conn.rollback()
            msg = str(e)
            if "UNIQUE" in msg:
                field = msg.split(".")[-1]
                return Response.json({"error": f"A record with this {field.replace('_', ' ')} already exists."}, 409)
            if "FOREIGN KEY" in msg:
                return Response.json({"error": "This record is linked to other records and cannot be changed or deleted."}, 409)
            return Response.json({"error": "Data integrity error: " + msg}, 409)
        except Exception:
            conn.rollback()
            traceback.print_exc()
            return Response.json({"error": "Unexpected server error. See the server console for details."}, 500)
        finally:
            conn.close()

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        root = os.path.normpath(config.FRONTEND_DIR)
        full = os.path.normpath(os.path.join(root, path.lstrip("/\\")))
        inside = os.path.commonpath([root, full]) == root if os.path.splitdrive(full)[0] == os.path.splitdrive(root)[0] else False
        if not inside or not os.path.isfile(full):
            full = os.path.join(config.FRONTEND_DIR, "index.html")  # SPA fallback
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            return Response(f.read(), 200, ctype, {"Cache-Control": "no-cache"})

    def _send(self, resp):
        try:
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.content_type)
            self.send_header("Content-Length", str(len(resp.body)))
            for k, v in {**SECURITY_HEADERS, **resp.headers}.items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(resp.body)
        except (BrokenPipeError, ConnectionResetError):
            pass


def serve(host, port):
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    return httpd
