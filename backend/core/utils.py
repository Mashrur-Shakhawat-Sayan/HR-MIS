"""Shared helpers: settings, dates, working-day calendar, validation."""
import calendar
import json
import re
from datetime import date, datetime, timedelta

from .http import ApiError

# ---------------------------------------------------------------- settings
DEFAULT_SETTINGS = {
    "company_name": "Your Company",
    "company_short": "HR",
    "company_address": "",
    "company_phone": "",
    "company_email": "hr@example.com",
    "employee_code_prefix": "EMP-",
    "currency_symbol": "৳",
    "work_start": "09:00",
    "work_end": "18:00",
    "grace_minutes": 15,
    "weekend_days": [4, 5],            # Python weekday(): Mon=0 … Fri=4, Sat=5
    "late_per_lwp_day": 3,             # 3 late arrivals = 1 day leave-without-pay (0 = off)
    "basic_pct": 60,
    "house_rent_pct": 30,
    "medical_pct": 6,
    "pf_employee_pct": 10,
    "pf_employer_pct": 10,
    "tax_pct": 3,
    "tax_min_gross": 35000,
    "ot_multiplier": 2,
    "ot_divisor_hours": 208,
    "lwp_divisor_days": 30,
    "festival_bonus_pct": 100,
    "probation_months": 6,
    "fiscal_year_start_month": 7,
}


def get_settings(conn):
    s = dict(DEFAULT_SETTINGS)
    for row in conn.execute("SELECT key, value FROM settings").fetchall():
        try:
            s[row["key"]] = json.loads(row["value"])
        except ValueError:
            s[row["key"]] = row["value"]
    return s


def save_settings(conn, values):
    for k, v in values.items():
        if k in DEFAULT_SETTINGS:
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                         (k, json.dumps(v, ensure_ascii=False)))


# ---------------------------------------------------------------- dates
DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_RX = re.compile(r"^\d{4}-\d{2}$")
TIME_RX = re.compile(r"^\d{2}:\d{2}$")


def today():
    return date.today().isoformat()


def now():
    return datetime.now().isoformat(timespec="seconds")


def d(s):
    return date.fromisoformat(s)


def add_days(s, n):
    return (d(s) + timedelta(days=n)).isoformat()


def daterange(start, end):
    cur, last = d(start), d(end)
    while cur <= last:
        yield cur.isoformat()
        cur += timedelta(days=1)


def month_bounds(month):
    if not MONTH_RX.match(month or ""):
        raise ApiError(400, "Month must be in YYYY-MM format")
    y, m = map(int, month.split("-"))
    return f"{month}-01", f"{month}-{calendar.monthrange(y, m)[1]:02d}", calendar.monthrange(y, m)[1]


def current_month():
    return today()[:7]


def years_between(a, b):
    a, b = d(a), d(b)
    return b.year - a.year - ((b.month, b.day) < (a.month, a.day))


def t2m(t):
    if not t:
        return None
    h, m = t.split(":")[:2]
    return int(h) * 60 + int(m)


class Calendar:
    """Answers 'is this a working day?' using weekend settings and the holiday table."""

    def __init__(self, conn, settings=None):
        self.settings = settings or get_settings(conn)
        self.weekend = set(self.settings["weekend_days"])
        self.holidays = {r["date"]: r["name"] for r in conn.execute("SELECT date, name FROM holidays").fetchall()}

    def is_workday(self, s):
        return d(s).weekday() not in self.weekend and s not in self.holidays

    def workdays(self, start, end):
        return [x for x in daterange(start, end) if self.is_workday(x)] if start and end and start <= end else []

    def is_late(self, check_in):
        return bool(check_in) and t2m(check_in) > t2m(self.settings["work_start"]) + int(self.settings["grace_minutes"])


# ---------------------------------------------------------------- validation
class Field:
    """Declarative column definition used by generic resources and validators."""

    def __init__(self, name, type="text", required=False, choices=None, label=None, default=None):
        self.name, self.type, self.required, self.choices = name, type, required, choices
        self.label = label or name.replace("_", " ").capitalize()
        self.default = default


def clean(fields, data, partial=False):
    """Validate and coerce incoming data against a list of Field objects."""
    out = {}
    for f in fields:
        if f.name not in data:
            if not partial and f.required and f.default is None:
                raise ApiError(400, f"{f.label} is required")
            if not partial and f.default is not None:
                out[f.name] = f.default
            continue
        v = data[f.name]
        if isinstance(v, str):
            v = v.strip()
        if v in ("", None):
            if f.required:
                raise ApiError(400, f"{f.label} is required")
            out[f.name] = None
            continue
        try:
            if f.type == "int" or f.type == "fk":
                v = int(v)
            elif f.type == "real":
                v = round(float(v), 2)
            elif f.type == "bool":
                v = 1 if v in (True, 1, "1", "true", "yes", "on") else 0
            elif f.type == "date" and not DATE_RX.match(str(v)):
                raise ValueError
            elif f.type == "time" and not TIME_RX.match(str(v)):
                raise ValueError
            elif f.type == "month" and not MONTH_RX.match(str(v)):
                raise ValueError
            elif f.type == "text":
                v = str(v)[:4000]
        except (TypeError, ValueError):
            raise ApiError(400, f"{f.label} has an invalid value")
        if f.choices and v not in f.choices:
            raise ApiError(400, f"{f.label} must be one of: {', '.join(map(str, f.choices))}")
        out[f.name] = v
    return out


# ---------------------------------------------------------------- daily jobs
# Modules register functions here (e.g. lifecycle: move employees whose last working day has passed
# from "On Notice" to their final status). They run once per calendar day, on the first API request.
DAILY_JOBS = []
_last_daily_run = {"day": None}


def run_daily(conn, force=False):
    day = today()
    if not force and _last_daily_run["day"] == day:
        return
    _last_daily_run["day"] = day
    for job in DAILY_JOBS:
        job(conn)
    conn.commit()


def money(x):
    return round(float(x or 0), 2)
