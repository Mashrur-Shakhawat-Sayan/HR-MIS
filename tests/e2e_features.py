"""Browser end-to-end feature test.

Exercises every screen and action as every role against a running server, and reports any
browser error, failed API call or error toast.

    1. python run.py --reset-demo --no-browser --port 8765      (in another window)
    2. pip install playwright && playwright install chromium     (once)
    3. python tests/e2e_features.py [--base http://127.0.0.1:8765] [--shots folder]

Selectors use data-act / #f_<field> attributes, so the test survives visual redesigns.
"""
import argparse
import os
import re
import sys
import tempfile
import time
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8765")
ap.add_argument("--shots", default="")
ap.add_argument("--headed", action="store_true")
args = ap.parse_args()
BASE = args.base
SHOTS = args.shots
if SHOTS:
    os.makedirs(SHOTS, exist_ok=True)

ACCOUNTS = {"admin": "Admin@123", "hr.manager": "Hr@12345", "hr.officer": "Hr@12345", "payroll": "Pay@12345",
            "manager": "Mgr@12345", "employee": "Emp@12345"}
problems, passed = [], []
EXPECTED_STATUS = set()   # (path-fragment, status) pairs a step deliberately triggers


class Session:
    def __init__(self, browser, user, viewport=(1440, 900)):
        self.user = user
        self.ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, timezone_id="Asia/Dhaka", accept_downloads=True)
        self.page = self.ctx.new_page()
        self.page.on("pageerror", lambda e: problems.append((user, "JS error", str(e))))
        self.page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and problems.append((user, "console", m.text)))
        self.page.on("response", self._resp)
        self.ctx.on("page", lambda p: p.on("pageerror", lambda e: problems.append((user, "popup JS error", str(e)))))

    def _resp(self, r):
        if "/api/" in r.url and r.status >= 400:
            path = r.url.split(BASE)[-1]
            if any(frag in path and st == r.status for frag, st in EXPECTED_STATUS):
                return
            try:
                body = r.text()[:200]
            except Exception:
                body = ""
            problems.append((self.user, f"HTTP {r.status}", f"{r.request.method} {path} {body}"))

    # -------------------------------------------------------- helpers
    def login(self, password=None):
        p = self.page
        p.goto(BASE)
        p.fill("input[name=username]", self.user)
        p.fill("input[name=password]", password or ACCOUNTS[self.user])
        p.click("button[type=submit]")
        p.wait_for_selector("#nav a", timeout=10000)
        self.idle()
        return self

    def idle(self, ms=350):
        self.page.wait_for_timeout(ms)
        try:
            self.page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass

    def go(self, hash_):
        self.page.evaluate(f"location.hash = '{hash_}'")
        self.idle(450)
        txt = self.page.inner_text("#main")
        if "Could not load" in txt:
            problems.append((self.user, "page failed", f"{hash_}: {txt[:160]}"))
        return txt

    def act(self, name, index=0, within="body", **data):
        sel = f'{within} [data-act="{name}"]' + "".join(f'[data-{k}="{v}"]' for k, v in data.items())
        loc = self.page.locator(sel)
        if index == "last":
            loc = loc.last
        else:
            loc = loc.nth(index)
        loc.scroll_into_view_if_needed(timeout=5000)
        loc.click(timeout=5000)
        self.idle()

    def tab(self, label):
        self.page.locator("#main .tabs button", has_text=label).first.click()
        self.idle(450)

    def modal_open(self):
        return self.page.locator("#modal.open").count() > 0

    def fill(self, **fields):
        for k, v in fields.items():
            el = self.page.locator(f"#modal #f_{k}")
            tag = el.evaluate("e => e.tagName + ':' + (e.type || '')")
            if tag.startswith("SELECT"):
                if isinstance(v, int):
                    el.select_option(index=v)
                else:
                    try:
                        el.select_option(value=str(v))
                    except Exception:
                        el.select_option(label=str(v))
            elif tag.endswith("checkbox"):
                el.set_checked(bool(v))
            else:
                el.fill(str(v))
            el.dispatch_event("change")
        self.idle(150)

    def save(self, expect_close=True):
        self.page.locator('#modal [data-act="modal:save"]').click()
        self.idle(600)
        bad = self.bad_toasts()
        if expect_close and self.modal_open():
            problems.append((self.user, "modal did not close", bad or self.page.inner_text("#modal")[:200]))
            self.page.keyboard.press("Escape")
        return bad

    def confirm(self):
        self.page.wait_for_selector("#modal.open")
        self.page.locator('#modal [data-act="modal:save"]').click()
        self.idle(600)

    def bad_toasts(self):
        msgs = self.page.eval_on_selector_all("#toasts div.bad", "els => els.map(e => e.textContent)")
        self.page.evaluate("document.querySelectorAll('#toasts div').forEach(e => e.remove())")
        return msgs

    def check_toasts(self, label):
        for m in self.bad_toasts():
            problems.append((self.user, f"error toast during {label}", m))

    def download(self, name, index=0, **data):
        with self.page.expect_download(timeout=10000) as d:
            self.act(name, index, **data)
        f = d.value
        path = f.path()
        size = os.path.getsize(path) if path else 0
        if size < 10:
            problems.append((self.user, "empty download", f"{name} → {f.suggested_filename}"))
        return f.suggested_filename, size

    def popup(self, name, index=0, **data):
        with self.ctx.expect_page(timeout=10000) as pp:
            self.act(name, index, **data)
        w = pp.value
        w.wait_for_load_state()
        w.wait_for_timeout(600)
        html = w.content()
        w.close()
        return html

    def shot(self, name):
        if SHOTS:
            self.page.screenshot(path=os.path.join(SHOTS, f"{name}.png"))

    def close(self):
        self.ctx.close()


def step(label):
    def deco(fn):
        def run(s, *a):
            before = len(problems)
            try:
                fn(s, *a)
            except Exception as e:  # keep going, record the failure
                problems.append((s.user, f"step crashed: {label}", f"{type(e).__name__}: {str(e).splitlines()[0][:220]}"))
                try:
                    s.page.keyboard.press("Escape")
                except Exception:
                    pass
            s.check_toasts(label)
            (passed.append(label) if len(problems) == before else None)
            print(("  ✓ " if len(problems) == before else "  ✗ ") + f"[{s.user}] {label}", flush=True)
        return run
    return deco


def next_workday(offset):
    d = date.today() + timedelta(days=offset)
    while d.weekday() in (4, 5):
        d += timedelta(days=1)
    return d.isoformat()


TMPFILE = os.path.join(tempfile.gettempdir(), "hrmis-test-doc.pdf")
with open(TMPFILE, "wb") as f:
    f.write(b"%PDF-1.4\n% HR-MIS e2e test document\n%%EOF\n")


# ============================================================ HR manager
@step("dashboard widgets & approvals")
def t_dashboard(s):
    txt = s.go("#/dashboard")
    for w in ("Active employees", "Approvals", "Headcount by department", "Notice board"):
        if w.lower() not in txt.lower():
            problems.append((s.user, "dashboard missing widget", w))
    s.shot("dashboard")


@step("organization: units / departments / designations CRUD + chart")
def t_org(s):
    s.go("#/organization")
    s.tab("Business units")
    s.act("crud:edit")
    s.fill(name="Sonar Tori Tissue", code="STT", location="Narayanganj")
    s.save()
    assert "Sonar Tori Tissue" in s.page.inner_text("#main")
    s.page.locator("#main tr", has_text="Sonar Tori Tissue").locator('[data-act="crud:edit"]').click()
    s.idle()
    s.fill(location="Narayanganj plant")
    s.save()
    s.tab("Departments")
    s.act("crud:edit")
    s.fill(name="Research & Development", unit_id=1, cost_center="CC-900")
    s.save()
    s.tab("Designations")
    s.act("crud:edit")
    s.fill(title="Principal Engineer", grade="M5A", level=5)
    s.save()
    s.page.locator("#main tr", has_text="Principal Engineer").locator('[data-act="crud:del"]').click()
    s.confirm()
    if "Principal Engineer" in s.page.inner_text("#main"):
        problems.append((s.user, "delete did not remove row", "designation"))
    s.tab("Business units")
    s.page.locator("#main tr", has_text="Sonar Tori Tissue").locator('[data-act="crud:del"]').click()
    s.confirm()
    s.tab("Organisation chart")
    if "Tanvir" not in s.page.inner_text("#main") and "Executive Director" not in s.page.inner_text("#main"):
        problems.append((s.user, "org chart empty", ""))


@step("employees: search, filters, export")
def t_emp_list(s):
    s.go("#/employees")
    s.page.fill('#main [data-input="emp:search"]', "Rahman")
    s.idle(700)
    rows = s.page.locator("#main tbody tr").count()
    if rows == 0:
        problems.append((s.user, "employee search returned nothing", "Rahman"))
    s.page.fill('#main [data-input="emp:search"]', "")
    s.idle(600)
    s.page.locator('#main select[data-k="emp_type"]').select_option("Probation")
    s.idle(600)
    s.page.locator('#main select[data-k="emp_type"]').select_option("")
    s.idle(500)
    s.download("emp:csv")
    s.shot("employees")


@step("employees: create with login, edit, profile tabs, ID card")
def t_emp_create(s):
    s.go("#/employees")
    s.act("emp:new")
    s.fill(full_name="Test Joiner One", gender="Female", dob="1996-04-12", phone="01711000000", email="joiner@example.com",
           blood_group="B+", nid="1990123456789", unit_id=1, dept_id=3, designation_id=8, emp_type="Probation",
           join_date=date.today().isoformat(), manager_id=1, gross_salary=42000, bank_name="BRAC Bank", bank_account="1234567890",
           present_address="Badda, Dhaka")
    if s.page.locator("#mkLogin").count():
        s.page.check("#mkLogin")
    s.save()
    s.idle(700)
    if s.modal_open():  # login credentials dialog
        txt = s.page.inner_text("#modal")
        m = re.search(r"Temporary password\s*(\S+)", txt)
        s.state["login"] = ("st-" + re.search(r"ST-(\d+)", s.page.inner_text("#main")).group(1), m.group(1) if m else None)
        s.page.keyboard.press("Escape")
        s.idle()
    if "Test Joiner One" not in s.page.inner_text("#main"):
        problems.append((s.user, "new employee profile not shown", s.page.url))
    s.state["emp_url"] = s.page.url
    for label in ("Job & pay", "Leave & attendance", "Career history", "Checklists", "Documents", "Overview"):
        s.tab(label)
    s.act("emp:edit")
    s.fill(marital_status="Married", emergency_name="Spouse", emergency_phone="01811000000")
    s.save()
    html = s.popup("emp:idcard")
    if "Test Joiner One" not in html:
        problems.append((s.user, "ID card missing name", ""))


@step("employees: documents upload/download/delete, checklist")
def t_emp_docs(s):
    s.page.goto(s.state["emp_url"])
    s.idle(600)
    s.tab("Documents")
    s.act("emp:upload")
    s.fill(title="NID copy", doc_type="NID")
    s.page.set_input_files("#docFile", TMPFILE)
    s.save()
    if "NID copy" not in s.page.inner_text("#main"):
        problems.append((s.user, "uploaded document not listed", ""))
    s.download("emp:dl")
    s.act("emp:deldoc")
    s.confirm()
    s.tab("Checklists")
    boxes = s.page.locator('#main [data-change="emp:tick"]')
    if boxes.count() < 8:
        problems.append((s.user, "onboarding checklist missing", str(boxes.count())))
    boxes.first.check()
    s.idle(600)
    s.act("emp:task")
    s.fill(category="Onboarding", task="Issue parking sticker", owner="Admin")
    s.save()


@step("lifecycle events: promotion, transfer, increment, confirmation, resignation")
def t_events(s):
    s.page.goto(s.state["emp_url"])
    s.idle(600)
    for kind, fields in [("Promotion", {"designation_id": 7}), ("Transfer", {"dept_id": 2}), ("Increment", {"increment_pct": 10}),
                         ("Confirmation", {}), ("Resignation", {"exit_date": (date.today() + timedelta(days=30)).isoformat()})]:
        s.act("emp:event")
        s.fill(event_type=kind)
        s.idle(300)
        if fields:
            s.fill(**fields)
        s.save()
    s.tab("Career history")
    txt = s.page.inner_text("#main")
    for kind in ("Promotion", "Transfer", "Increment", "Confirmation", "Resignation"):
        if kind not in txt:
            problems.append((s.user, "event missing from history", kind))
    if "On Notice" not in txt:
        problems.append((s.user, "resignation did not set On Notice", ""))


@step("lifecycle page: events, checklists, confirmations, disciplinary CRUD")
def t_lifecycle(s):
    s.go("#/lifecycle")
    s.tab("Onboarding")
    s.tab("Confirmations due")
    s.tab("Disciplinary")
    s.act("crud:edit")
    s.fill(emp_id=3, action_date=date.today().isoformat(), action_type="Written Warning", reason="Test", issued_by="HR")
    s.save()
    s.page.locator("#main tr", has_text="Written Warning").locator('[data-act="crud:edit"]').click()
    s.idle()
    s.fill(status="Closed", resolution="Resolved")
    s.save()
    s.page.locator("#main tr", has_text="Written Warning").locator('[data-act="crud:del"]').click()
    s.confirm()
    s.tab("Career events")
    s.page.locator('#main select[data-change="lc:type"]').select_option("Promotion")
    s.idle()


@step("attendance: daily edit/save, mark all, register, export, import")
def t_attendance(s):
    s.go("#/attendance")
    day = next_workday(-8 if date.today().weekday() not in (4, 5) else -7)
    s.page.fill('#main input[data-change="att:date"]', day)
    s.page.dispatch_event('#main input[data-change="att:date"]', "change")
    s.idle(700)
    row = s.page.locator("#main tr[data-emp]").nth(1)
    row.locator('[data-f="status"]').select_option("A")
    row.locator('[data-f="note"]').fill("No call no show")
    row.locator('[data-f="note"]').dispatch_event("change")
    s.act("att:save")
    if "A" != s.page.locator("#main tr[data-emp]").nth(1).locator('[data-f="status"]').input_value():
        problems.append((s.user, "attendance status not saved", day))
    s.act("att:day", d="1")
    s.act("att:all")
    s.tab("Monthly register")
    s.act("att:mon", d="-1")
    s.download("att:csv")
    s.tab("Import from device")
    s.page.fill("#impText", f"employee_id,date,check_in,check_out\nST-1003,{day},08:52,18:01\nST-0000,{day},09:00,18:00")
    s.act("att:import")
    res = s.page.inner_text("#impResult")
    if "Imported 1" not in res:
        problems.append((s.user, "import result unexpected", res[:120]))
    s.shot("attendance")


@step("leave: approve, reject with reason, apply on behalf, cancel")
def t_leave(s):
    s.go("#/leave")
    if s.page.locator('#main [data-act="lv:decide"]').count() < 2:
        problems.append((s.user, "no pending leave to decide", ""))
    s.act("lv:decide", d="Approved")
    s.act("lv:decide", d="Rejected")
    s.page.fill("#rejWhy", "Peak season")
    s.save()
    s.act("lv:apply")
    s.fill(emp_id=5, leave_type_id="1", from_date=next_workday(30), to_date=next_workday(30), reason="Family event", approve=True)
    s.idle(500)
    s.save()
    s.page.locator('#main select[data-change="lv:status"]').select_option("Approved")
    s.idle(600)
    s.act("lv:cancel")
    s.confirm()
    s.page.locator('#main select[data-change="lv:status"]').select_option("All")
    s.idle()
    s.download("lv:csv")


@step("leave: balances, who's away, types CRUD, adjustments")
def t_leave_admin(s):
    s.go("#/leave")
    s.tab("Balances")
    s.download("lv:balcsv")
    s.tab("Who's away")
    s.act("lv:mon", d="-1")
    s.tab("Leave types")
    s.act("crud:edit")
    s.fill(name="Study", days_per_year=5, gender="Any", paid=True)
    s.save()
    s.page.locator("#main tr", has_text="Study").locator('[data-act="crud:edit"]').click()
    s.idle()
    s.fill(days_per_year=6)
    s.save()
    s.page.locator("#main tr", has_text="Study").locator('[data-act="crud:del"]').click()
    s.confirm()
    s.tab("Opening balances")
    s.act("lv:adj")
    s.fill(emp_id=4, leave_type_id="3", year=date.today().year, days=5, note="Carry forward")
    s.save()
    s.act("lv:deladj", "last")


@step("holidays CRUD")
def t_holidays(s):
    s.go("#/holidays")
    s.act("crud:edit")
    s.fill(date=f"{date.today().year}-12-31", name="Company year-end", type="Company")
    s.save()
    s.page.locator("#main tr", has_text="Company year-end").locator('[data-act="crud:edit"]').click()
    s.idle()
    s.fill(name="Company year-end holiday")
    s.save()
    s.page.locator("#main tr", has_text="Company year-end holiday").locator('[data-act="crud:del"]').click()
    s.confirm()
    EXPECTED_STATUS.add(("/api/holidays", 409))
    s.act("crud:edit")
    s.fill(date=f"{date.today().year}-12-16", name="Duplicate", type="National")
    bad = s.save(expect_close=False)
    if not bad:
        problems.append((s.user, "duplicate holiday not rejected", ""))
    s.page.keyboard.press("Escape")
    s.idle()


@step("recruitment: jobs, candidates, pipeline moves, onboard")
def t_recruit(s):
    s.go("#/recruitment")
    s.tab("Job openings")
    s.act("crud:edit")
    s.fill(title="Data Analyst", dept_id=3, unit_id=1, vacancies=1, salary_range="60,000–75,000", deadline=next_workday(20), status="Open")
    s.save()
    s.tab("Candidate pipeline")
    s.act("rec:add")
    s.fill(name="Test Candidate", job_id=1, phone="01700000000", source="LinkedIn", expected_salary=65000, rating=4)
    s.save()
    for _ in range(4):
        s.page.locator(".kc", has_text="Test Candidate").locator('[data-act="rec:move"][title="Move forward"]').click()
        s.idle(500)
    s.page.locator(".kc", has_text="Test Candidate").locator('[data-act="rec:hire"]').click()
    s.idle()
    s.fill(designation_id=8, join_date=date.today().isoformat())
    s.save()
    if "Test Candidate" not in s.page.inner_text("#main"):
        problems.append((s.user, "onboarded candidate profile not opened", ""))
    s.go("#/recruitment")
    s.tab("All candidates")
    s.page.locator('#main select[data-change="crud:filter"]').first.select_option("Hired")
    s.idle()
    s.shot("recruitment")


@step("performance: create & edit review")
def t_perf(s):
    s.go("#/performance")
    s.act("crud:edit")
    s.fill(emp_id=6, period="2026 H2", quality=4, productivity=5, teamwork=4, punctuality=3, initiative=4, status="Submitted", comments="Good")
    s.save()
    s.page.locator("#main tr", has_text="2026 H2").first.locator('[data-act="crud:edit"]').click()
    s.idle()
    s.fill(initiative=5)
    s.save()


@step("training: CRUD + participants")
def t_training(s):
    s.go("#/training")
    s.act("crud:edit")
    s.fill(title="Excel Pivot Tables", category="Technical", trainer="IT", start_date=next_workday(10), hours=4, mode="Online", cost=5000)
    s.save()
    s.page.locator("#main tr", has_text="Excel Pivot Tables").locator('[data-act="trn:people"]').click()
    s.idle()
    s.page.locator("#modal .trn-in").nth(0).check()
    s.page.locator("#modal .trn-in").nth(1).check()
    s.page.locator("#modal .trn-att").nth(0).check()
    s.save()
    if "Excel Pivot Tables" not in s.page.inner_text("#main"):
        problems.append((s.user, "training not listed", ""))


@step("assets: CRUD, issue, return")
def t_assets(s):
    s.go("#/assets")
    s.act("crud:edit")
    s.fill(tag="IT-LT-9999", name="Test Laptop", category="Laptop", value=90000, status="In Stock")
    s.save()
    s.page.locator("#main tr", has_text="IT-LT-9999").locator('[data-act="ast:issue"]').click()
    s.idle()
    s.fill(emp_id=7)
    s.save()
    s.page.locator("#main tr", has_text="IT-LT-9999").locator('[data-act="ast:return"]').click()
    s.idle()
    s.fill(condition="Fair")
    s.save()
    s.page.locator("#main tr", has_text="IT-LT-9999").locator('[data-act="crud:del"]').click()
    s.confirm()


@step("notices CRUD")
def t_notices(s):
    s.go("#/notices")
    s.act("crud:edit")
    s.fill(title="Fire drill on Sunday", priority="Important", body="Assemble at the car park at 11:00.")
    s.save()
    s.page.locator("#main tr", has_text="Fire drill").locator('[data-act="crud:edit"]').click()
    s.idle()
    s.fill(audience="Head Office")
    s.save()


@step("reports: every report, parameters, CSV, print")
def t_reports(s):
    s.go("#/reports")
    keys = s.page.eval_on_selector_all('#main [data-act="rep:pick"]', "els => els.map(e => e.dataset.k)")
    if len(keys) < 15:
        problems.append((s.user, "report catalogue short", str(len(keys))))
    for k in keys:
        s.page.locator(f'#main [data-act="rep:pick"][data-k="{k}"]').click()
        s.idle(450)
        if "Loading" in s.page.inner_text("#repBody"):
            problems.append((s.user, "report stuck loading", k))
    s.page.locator('#main [data-act="rep:pick"][data-k="attendance-summary"]').click()
    s.idle()
    s.page.fill('#repBody input[type=month]', (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m"))
    s.page.dispatch_event('#repBody input[type=month]', "change")
    s.idle()
    s.download("rep:csv")
    html = s.popup("rep:print")
    if "<table" not in html:
        problems.append((s.user, "printed report has no table", ""))
    s.shot("reports")


# ============================================================ payroll officer
@step("payroll: generate w/ bonus, adjust, payslip, print, exports, finalize, pay, reopen")
def t_payroll(s):
    s.go("#/payroll")
    s.act("pay:month", d="1")
    s.act("pay:month", d="-1")
    if s.page.locator("#payBonus").count():
        s.page.check("#payBonus")
    s.act("pay:gen")
    if "Draft" not in s.page.inner_text("#main"):
        problems.append((s.user, "payroll not in draft after generate", ""))
    inp = s.page.locator('#main input[data-change="pay:adj"][data-k="ot_hours"]').nth(2)
    inp.fill("12")
    inp.dispatch_event("change")
    s.idle(800)
    inp = s.page.locator('#main input[data-change="pay:adj"][data-k="other_deduction"]').nth(3)
    inp.fill("500")
    inp.dispatch_event("change")
    s.idle(800)
    s.act("pay:slip", 2)
    if "Overtime" not in s.page.inner_text("#modal"):
        problems.append((s.user, "payslip missing overtime line", ""))
    html = s.popup("pay:print1")
    if "Taka" not in html:
        problems.append((s.user, "printed payslip missing amount in words", ""))
    s.page.keyboard.press("Escape")
    s.idle()
    for t in ("register", "bank", "pf"):
        s.download("pay:csv", t=t)
    s.popup("pay:printall")
    s.act("pay:step", s="finalize")
    s.confirm()
    if "Finalized" not in s.page.inner_text("#main"):
        problems.append((s.user, "payroll not finalized", ""))
    s.act("pay:step", s="reopen")
    s.confirm()
    s.act("pay:gen")
    s.act("pay:step", s="finalize")
    s.confirm()
    s.act("pay:step", s="pay")
    s.confirm()
    if "Paid" not in s.page.inner_text("#main"):
        problems.append((s.user, "payroll not paid", ""))
    s.act("pay:month", d="1")
    s.act("pay:gen")
    s.act("pay:delete")
    s.confirm()
    s.shot("payroll")


@step("loans: create, approve request, history, manual repayment")
def t_loans(s):
    s.go("#/loans")
    s.act("crud:edit")
    s.fill(emp_id=8, loan_type="Salary Advance", principal=10000, installment=2500, start_month=date.today().strftime("%Y-%m"))
    s.save()
    if s.page.locator('#main [data-act="loan:set"][data-s="Active"]').count():
        s.act("loan:set", s="Active")
    s.act("loan:hist")
    s.act("loan:pay")
    s.fill(amount=2500)
    s.save()


@step("claims: approve, reject, mark paid")
def t_claims(s):
    s.go("#/claims")
    if s.page.locator('#main [data-act="clm:set"][data-s="Approved"]').count():
        s.act("clm:set", s="Approved")
    if s.page.locator('#main [data-act="clm:set"][data-s="Rejected"]').count():
        s.act("clm:set", s="Rejected")
    s.page.locator('#main select[data-change="crud:filter"]').first.select_option("Approved")
    s.idle()
    if s.page.locator('#main [data-act="clm:set"][data-s="Paid"]').count():
        s.act("clm:set", s="Paid")


# ============================================================ admin
@step("users: create, edit role, reset password, permission matrix")
def t_users(s):
    s.go("#/users")
    s.act("usr:new")
    s.fill(username="test.user", role="hr_officer", emp_id=12, password="Welcome123")
    s.save()
    s.page.locator("#main tr", has_text="test.user").locator('[data-act="usr:edit"]').click()
    s.idle()
    s.fill(role="manager")
    s.save()
    s.page.locator("#main tr", has_text="test.user").locator('[data-act="usr:pw"]').click()
    s.idle()
    s.fill(password="Reset1234")
    s.save()
    s.tab("Roles")
    if "✓" not in s.page.inner_text("#main") and s.page.locator("#main .t td svg, #main .t td b").count() == 0:
        problems.append((s.user, "permission matrix empty", ""))


@step("audit trail filters & details")
def t_audit(s):
    s.go("#/audit")
    s.page.locator('#main select[data-k="action"]').select_option("create")
    s.idle()
    if s.page.locator('#main [data-act="aud:show"]').count():
        s.act("aud:show")
        s.page.keyboard.press("Escape")


@step("settings: save, backup download, server backup")
def t_settings(s):
    s.go("#/settings")
    s.page.fill('#main [data-k="grace_minutes"]', "10")
    s.act("set:save")
    s.download("set:dl")
    s.act("set:srv")


@step("forced password change for new user + logout/login")
def t_pwchange(s, browser):
    s2 = Session(browser, "test.user").login("Reset1234")
    s2.page.wait_for_selector("#modal.open", timeout=5000)
    s2.page.fill("#f_current_password", "Reset1234")
    s2.page.fill("#f_new_password", "BrandNew123")
    s2.page.fill("#f_confirm", "BrandNew123")
    s2.save()
    s2.act("app:usermenu")
    s2.act("app:logout")
    if not s2.page.locator("#loginForm").is_visible():
        problems.append(("test.user", "logout did not show sign-in", ""))
    s2.login("BrandNew123")
    s2.close()


# ============================================================ manager
@step("manager: dashboard approvals, team scope, review")
def t_manager(s):
    s.go("#/dashboard")
    if s.page.locator('#main [data-act="dash:leave"]').count():
        s.act("dash:leave", d="Approved")
    s.go("#/employees")
    n = s.page.locator("#main tbody tr").count()
    if n > 10:
        problems.append((s.user, "manager sees employees outside the team", f"{n} rows"))
    s.go("#/attendance")
    s.go("#/leave")
    s.go("#/claims")
    s.go("#/performance")
    s.shot("manager_dashboard")


# ============================================================ employee
@step("employee: check in/out, leave apply/cancel, payslip, loan request, claims CRUD, profile")
def t_employee(s):
    s.go("#/me/attendance")
    if s.page.locator('#main [data-act="me:clock"][data-a="in"]').count():
        s.act("me:clock", a="in")
    if s.page.locator('#main [data-act="me:clock"][data-a="out"]').count():
        s.act("me:clock", a="out")
    s.act("me:month", d="-1")
    s.go("#/me/leave")
    s.act("me:apply")
    s.fill(leave_type_id="2", from_date=next_workday(45), to_date=next_workday(45), reason="Dental appointment")
    s.idle(500)
    if "working day" not in s.page.inner_text("#lvInfo"):
        problems.append((s.user, "leave preview not shown", s.page.inner_text("#lvInfo")))
    s.save()
    s.act("me:cancel", "last")
    s.confirm()
    s.go("#/me/pay")
    s.act("me:slip")
    s.page.keyboard.press("Escape")
    s.idle()
    s.popup("me:print")
    s.act("me:loan")
    s.fill(loan_type="Salary Advance", principal=8000, installment=2000)
    s.save()
    s.go("#/me/claims")
    s.act("me:claim")
    s.fill(category="Travel", amount=750, description="CNG to client office")
    s.save()
    s.page.locator("#main tr", has_text="CNG to client").locator('[data-act="me:claim"]').click()
    s.idle()
    s.fill(amount=800)
    s.save()
    s.page.locator("#main tr", has_text="CNG to client").locator('[data-act="me:delclaim"]').click()
    s.confirm()
    s.go("#/me/profile")
    s.act("me:edit")
    s.fill(phone="01999000000")
    s.save()
    s.go("#/holidays")
    s.go("#/notices")
    s.shot("employee_dashboard")


@step("security: employee blocked from admin pages")
def t_block(s):
    for h in ("#/payroll", "#/users", "#/settings", "#/employees"):
        s.page.evaluate(f"location.hash = '{h}'")
        s.idle(400)
        if not s.page.evaluate("location.hash").startswith("#/dashboard"):
            problems.append((s.user, "employee reached restricted page", h))


@step("mobile layout: no horizontal scroll, menu opens")
def t_mobile(s):
    for h in ("#/dashboard", "#/employees", "#/payroll", "#/attendance"):
        s.go(h)
        w = s.page.evaluate("document.documentElement.scrollWidth")
        if w > 395:
            problems.append((s.user, "horizontal scroll on mobile", f"{h} width {w}"))
    s.page.click("#menuBtn")
    s.idle()
    if "nav-open" not in (s.page.get_attribute("body", "class") or ""):
        problems.append((s.user, "mobile menu did not open", ""))
    s.shot("mobile_menu")


def main():
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        print("HR manager")
        s = Session(browser, "hr.manager").login()
        s.state = {}
        for t in (t_dashboard, t_org, t_emp_list, t_emp_create, t_emp_docs, t_events, t_lifecycle, t_attendance, t_leave,
                  t_leave_admin, t_holidays, t_recruit, t_perf, t_training, t_assets, t_notices, t_reports):
            t(s)
        s.close()
        print("Payroll officer")
        s = Session(browser, "payroll").login()
        for t in (t_payroll, t_loans, t_claims):
            t(s)
        s.close()
        print("Administrator")
        s = Session(browser, "admin").login()
        for t in (t_users, t_audit, t_settings):
            t(s)
        t_pwchange(s, browser)
        s.close()
        print("Line manager")
        s = Session(browser, "manager").login()
        t_manager(s)
        s.close()
        print("HR officer")
        s = Session(browser, "hr.officer").login()
        for h in ("#/employees", "#/attendance", "#/leave", "#/recruitment", "#/training", "#/assets", "#/reports", "#/lifecycle"):
            s.go(h)
        s.go("#/employees/3")
        if "Gross salary" in s.page.inner_text("#main"):
            problems.append(("hr.officer", "salary visible to HR officer", ""))
        s.close()
        print("Employee")
        s = Session(browser, "employee").login()
        t_employee(s)
        t_block(s)
        s.close()
        s = Session(browser, "manager", viewport=(390, 844)).login()
        t_mobile(s)
        s.close()
        browser.close()
    print(f"\n{len(passed)} steps passed, {len(problems)} problem(s) in {time.time() - t0:.0f}s")
    for pr in problems:
        print(" -", " | ".join(map(str, pr)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
