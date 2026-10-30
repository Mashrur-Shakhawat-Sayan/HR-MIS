"""Application configuration.

All values can be overridden with environment variables so the same code
runs on a laptop, an office server or inside a container.
"""
import os

APP_NAME = "HR-MIS"
VERSION = "1.1.1"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
SCHEMA_FILE = os.path.join(BASE_DIR, "backend", "db", "schema.sql")

DATA_DIR = os.environ.get("HRMIS_DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.environ.get("HRMIS_DB", os.path.join(DATA_DIR, "hrmis.db"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

# 127.0.0.1 = only this PC. Use 0.0.0.0 to let other PCs on the office LAN connect.
HOST = os.environ.get("HRMIS_HOST", "127.0.0.1")
PORT = int(os.environ.get("HRMIS_PORT", "8000"))

SESSION_HOURS = int(os.environ.get("HRMIS_SESSION_HOURS", "12"))
MAX_BODY_BYTES = 15 * 1024 * 1024          # 15 MB (document uploads)
MAX_LOGIN_ATTEMPTS = 8                     # per username per 15 minutes
