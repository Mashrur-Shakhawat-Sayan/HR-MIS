#!/usr/bin/env python3
"""HR-MIS launcher.

    python run.py                    start on http://127.0.0.1:8000 (creates the database with demo data on first run)
    python run.py --empty            first run without demo data (only the admin account)
    python run.py --reset-demo       DELETE the database and start again with fresh demo data
    python run.py --port 9000        use another port
    python run.py --lan              allow other PCs on the office network to connect
    python run.py --no-browser       do not open the browser automatically
"""
import argparse
import os
import shutil
import socket
import sys
import threading
import webbrowser
from datetime import datetime

if sys.version_info < (3, 10):
    sys.exit("HR-MIS needs Python 3.10 or newer. Download it from https://www.python.org/downloads/")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:  # never crash on consoles that cannot print box-drawing characters
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

from backend import config  # noqa: E402
from backend import modules  # noqa: E402,F401  (registers all API routes)
from backend.core import db  # noqa: E402
from backend.core.http import serve  # noqa: E402
from backend.db import seed  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="HR-MIS server")
    ap.add_argument("--host", default=config.HOST)
    ap.add_argument("--port", type=int, default=config.PORT)
    ap.add_argument("--lan", action="store_true", help="listen on all network interfaces (0.0.0.0)")
    ap.add_argument("--empty", action="store_true", help="first run without demo data")
    ap.add_argument("--reset-demo", action="store_true", help="delete the database and reload demo data")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    host = "0.0.0.0" if args.lan else args.host

    if args.reset_demo and os.path.exists(config.DB_PATH):
        os.makedirs(config.BACKUP_DIR, exist_ok=True)
        keep = os.path.join(config.BACKUP_DIR, f"before-reset-{datetime.now():%Y%m%d-%H%M%S}.db")
        shutil.copy2(config.DB_PATH, keep)
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(config.DB_PATH + suffix)
            except OSError:
                pass
        print(f"  Previous database saved to {keep}")

    first_run = db.init_database()
    if first_run:
        conn = db.connect()
        try:
            seed.seed_base(conn)
            if not args.empty:
                print("  Loading demo data (Sonar Tori Group, a fictional company) …")
                seed.seed_demo(conn)
            conn.commit()
        finally:
            conn.close()

    conn = db.connect()
    try:
        from backend.core.utils import run_daily
        run_daily(conn, force=True)  # e.g. finalise exits whose last working day has passed
    finally:
        conn.close()

    try:
        httpd = serve(host, args.port)
    except OSError:
        sys.exit(f"Port {args.port} is already in use. Is HR-MIS already running? Try: python run.py --port {args.port + 1}")

    url = f"http://127.0.0.1:{args.port}"
    line = "─" * 62
    print(f"\n  {line}\n   {config.APP_NAME} {config.VERSION} is running")
    print(f"   Open:  {url}")
    if args.lan:
        try:
            ip = socket.gethostbyname(socket.gethostname())
            print(f"   Office network:  http://{ip}:{args.port}")
        except OSError:
            pass
    print(f"   Data:  {config.DB_PATH}")
    if first_run:
        print("\n   Sign in as  admin / Admin@123" + ("" if args.empty else "  (more demo logins in README.md)"))
        print("   Change this password after signing in.")
    print(f"   Press Ctrl+C to stop.\n  {line}\n")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  HR-MIS stopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
