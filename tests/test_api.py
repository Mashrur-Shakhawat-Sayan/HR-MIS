"""End-to-end API tests: workflows and role-based security.

Run from the project folder:   python -m unittest discover tests -v

The tests start their own HR-MIS server on a temporary database, so your real data is never touched.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="hrmis-test-")
os.environ["HRMIS_DATA_DIR"] = TMP
os.environ["HRMIS_DB"] = os.path.join(TMP, "test.db")
sys.path.insert(0, ROOT)

from backend import modules  # noqa: E402,F401
from backend.core import db  # noqa: E402
from backend.core.http import serve  # noqa: E402
from backend.db import seed  # noqa: E402

PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def login(user, pw):
    s, b = call("POST", "/api/auth/login", {"username": user, "password": pw})
    assert s == 200, b
    return b["token"]


class HRMISTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_database()
        conn = db.connect()
        seed.seed_base(conn)
        seed.seed_demo(conn)
        conn.commit()
        conn.close()
        cls.httpd = serve("127.0.0.1", PORT)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.admin = login("admin", "Admin@123")
        cls.hr = login("hr.manager", "Hr@12345")
        cls.payroll = login("payroll", "Pay@12345")
        cls.manager = login("manager", "Mgr@12345")
        cls.employee = login("employee", "Emp@12345")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(TMP, ignore_errors=True)

    # ---------------------------------------------------------- authentication
    def test_01_bad_login_and_no_token(self):
        self.assertEqual(call("POST", "/api/auth/login", {"username": "admin", "password": "wrong"})[0], 401)
        self.assertEqual(call("GET", "/api/employees")[0], 401)

    def test_02_me_has_permissions(self):
        s, me = call("GET", "/api/auth/me", token=self.employee)
        self.assertEqual(s, 200)
        self.assertIn("self.leave", me["permissions"])
        self.assertNotIn("payroll.view", me["permissions"])

    # ---------------------------------------------------------- RBAC
    def test_03_employee_cannot_reach_admin_data(self):
        for path in ("/api/employees", "/api/payroll/runs", "/api/users", "/api/settings", "/api/audit", "/api/reports"):
            self.assertEqual(call("GET", path, token=self.employee)[0], 403, path)

    def test_04_salary_hidden_without_permission(self):
        _, hr_view = call("GET", "/api/employees", token=login("hr.officer", "Hr@12345"))
        self.assertNotIn("gross_salary", hr_view["items"][0])
        _, pay_view = call("GET", "/api/employees", token=self.payroll)
        self.assertIn("gross_salary", pay_view["items"][0])

    def test_05_employee_sees_only_own_profile(self):
        _, me = call("GET", "/api/auth/me", token=self.employee)
        self.assertEqual(call("GET", f"/api/employees/{me['emp_id']}", token=self.employee)[0], 200)
        self.assertEqual(call("GET", "/api/employees/1", token=self.employee)[0], 403)

    # ---------------------------------------------------------- employees
    def test_10_create_employee_with_login(self):
        s, res = call("POST", "/api/employees", {"full_name": "Test Joiner", "gender": "Male", "join_date": date.today().isoformat(),
                                                 "emp_type": "Probation", "gross_salary": 40000, "create_login": True}, self.admin)
        self.assertEqual(s, 200, res)
        self.assertTrue(res["employee"]["code"].startswith("ST-"))
        tok = login(res["login"]["username"], res["login"]["temporary_password"])
        _, me = call("GET", "/api/auth/me", token=tok)
        self.assertTrue(me["must_change_pw"])
        _, prof = call("GET", f"/api/employees/{res['employee']['id']}", token=self.hr)
        self.assertEqual(len([t for t in prof["tasks"] if t["category"] == "Onboarding"]), 8)

    def test_11_promotion_updates_record_and_history(self):
        _, desig = call("GET", "/api/designations", token=self.hr)
        target = next(d for d in desig["items"] if d["title"] == "Senior Executive")
        s, _ = call("POST", "/api/employees/14/events", {"event_type": "Promotion", "designation_id": target["id"], "gross_salary": 52000}, self.hr)
        self.assertEqual(s, 200)
        _, e = call("GET", "/api/employees/14", token=self.hr)
        self.assertEqual(e["designation"], "Senior Executive")
        self.assertEqual(e["gross_salary"], 52000)
        self.assertEqual(e["events"][0]["event_type"], "Promotion")

    # ---------------------------------------------------------- leave workflow
    def test_20_leave_apply_approve_cancel(self):
        _, types = call("GET", "/api/leave-types", token=self.employee)
        casual = next(t for t in types["items"] if t["name"] == "Casual")
        d = date.today() + timedelta(days=20)
        while d.weekday() in (4, 5):
            d += timedelta(days=1)
        s, req = call("POST", "/api/leave/requests", {"leave_type_id": casual["id"], "from_date": d.isoformat(), "to_date": d.isoformat(), "reason": "test"}, self.employee)
        self.assertEqual(s, 200, req)
        self.assertEqual(req["status"], "Pending")
        # employee cannot approve own leave
        self.assertEqual(call("POST", f"/api/leave/requests/{req['id']}/decision", {"decision": "Approved"}, self.employee)[0], 403)
        # line manager approves (employee reports to the IT head)
        s, done = call("POST", f"/api/leave/requests/{req['id']}/decision", {"decision": "Approved"}, self.manager)
        self.assertEqual(s, 200, done)
        _, att = call("GET", f"/api/attendance/daily?date={d.isoformat()}", token=self.admin)
        row = next(r for r in att["rows"] if r["id"] == req["emp_id"])
        self.assertEqual(row["status"], "LV")
        self.assertEqual(call("POST", f"/api/leave/requests/{req['id']}/cancel", token=self.employee)[0], 200)
        _, att = call("GET", f"/api/attendance/daily?date={d.isoformat()}", token=self.admin)
        self.assertEqual(next(r for r in att["rows"] if r["id"] == req["emp_id"])["status"], "")

    def test_21_overlapping_leave_rejected(self):
        _, types = call("GET", "/api/leave-types", token=self.employee)
        sick = next(t for t in types["items"] if t["name"] == "Sick")
        d = date.today() + timedelta(days=40)
        while d.weekday() in (4, 5):
            d += timedelta(days=1)
        body = {"leave_type_id": sick["id"], "from_date": d.isoformat(), "to_date": d.isoformat()}
        self.assertEqual(call("POST", "/api/leave/requests", body, self.employee)[0], 200)
        self.assertEqual(call("POST", "/api/leave/requests", body, self.employee)[0], 409)

    def test_22_manager_cannot_approve_outside_team(self):
        _, reqs = call("GET", "/api/leave/requests?status=Pending", token=self.hr)
        outsider = next(r for r in reqs["items"] if r["department"] != "Information Technology")
        self.assertEqual(call("POST", f"/api/leave/requests/{outsider['id']}/decision", {"decision": "Approved"}, self.manager)[0], 403)

    # ---------------------------------------------------------- payroll
    def test_30_payroll_full_cycle(self):
        month = date.today().strftime("%Y-%m")
        s, run = call("POST", f"/api/payroll/runs/{month}/generate", {"include_bonus": True}, self.payroll)
        self.assertEqual(s, 200, run)
        self.assertGreater(run["totals"]["net"], 0)
        self.assertGreater(run["totals"]["bonus"], 0)
        slip = run["items"][0]
        s, adj = call("PUT", f"/api/payroll/payslips/{slip['id']}", {"ot_hours": 10}, self.payroll)
        self.assertGreater(adj["ot_amount"], 0)
        self.assertAlmostEqual(adj["earnings"] - adj["deductions"], adj["net"], delta=1)
        self.assertEqual(call("POST", f"/api/payroll/runs/{month}/finalize", token=self.payroll)[0], 200)
        self.assertEqual(call("PUT", f"/api/payroll/payslips/{slip['id']}", {"ot_hours": 1}, self.payroll)[0], 409)
        self.assertEqual(call("POST", f"/api/payroll/runs/{month}/pay", token=self.payroll)[0], 200)
        _, mine = call("GET", "/api/payroll/my", token=self.employee)
        self.assertTrue(any(p["month"] == month for p in mine["items"]))
        other = next(i for i in run["items"] if i["emp_code"] == "ST-1001")
        self.assertEqual(call("GET", f"/api/payroll/payslips/{other['id']}", token=self.employee)[0], 403)

    def test_31_salary_breakdown_adds_up(self):
        month = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        _, run = call("GET", f"/api/payroll/runs/{month}", token=self.payroll)
        for r in run["items"]:
            self.assertAlmostEqual(r["basic"] + r["house_rent"] + r["medical"] + r["conveyance"], r["gross"], delta=0.05)

    # ---------------------------------------------------------- claims
    def test_40_claims_self_service_and_approval(self):
        s, c = call("POST", "/api/claims", {"claim_date": date.today().isoformat(), "category": "Travel", "amount": 1500, "status": "Approved"}, self.employee)
        self.assertEqual(s, 200, c)
        self.assertEqual(c["status"], "Pending")  # employees cannot self-approve
        self.assertEqual(call("POST", f"/api/claims/{c['id']}/decision", {"status": "Approved"}, self.manager)[0], 200)
        self.assertEqual(call("PUT", f"/api/claims/{c['id']}", {"amount": 99999}, self.employee)[0], 403)

    # ---------------------------------------------------------- attendance
    def test_50_attendance_late_detection_and_import(self):
        d = date.today() - timedelta(days=1)
        while d.weekday() in (4, 5):
            d -= timedelta(days=1)
        s, _ = call("PUT", "/api/attendance/daily", {"date": d.isoformat(), "records": [{"emp_id": 2, "status": "P", "check_in": "09:40", "check_out": "18:00"}]}, self.hr)
        self.assertEqual(s, 200)
        _, day = call("GET", f"/api/attendance/daily?date={d.isoformat()}", token=self.hr)
        self.assertEqual(next(r for r in day["rows"] if r["id"] == 2)["status"], "L")
        s, res = call("POST", "/api/attendance/import", {"csv": f"employee_id,date,check_in,check_out\nST-1003,{d.isoformat()},08:50,18:00\nST-9999,{d.isoformat()},09:00,18:00"}, self.hr)
        self.assertEqual(res["imported"], 1)
        self.assertEqual(len(res["errors"]), 1)

    # ---------------------------------------------------------- reports, audit, backup
    def test_60_every_report_runs(self):
        _, cat = call("GET", "/api/reports", token=self.admin)
        self.assertGreaterEqual(len(cat["items"]), 15)
        for r in cat["items"]:
            s, out = call("GET", f"/api/reports/{r['key']}", token=self.admin)
            self.assertEqual(s, 200, r["key"])
            self.assertTrue(all(len(row) == len(out["columns"]) for row in out["rows"]), r["key"])

    def test_61_audit_and_backup(self):
        _, a = call("GET", "/api/audit?action=login", token=self.admin)
        self.assertTrue(a["items"])
        s, raw = call("GET", "/api/system/backup", token=self.admin)
        self.assertEqual(s, 200)
        self.assertTrue(raw.startswith(b"SQLite format 3"))

    def test_62_settings_validation(self):
        self.assertEqual(call("PUT", "/api/settings", {"basic_pct": 90, "house_rent_pct": 30}, self.admin)[0], 400)
        s, out = call("PUT", "/api/settings", {"grace_minutes": 10}, self.admin)
        self.assertEqual(out["grace_minutes"], 10)


    # ---------------------------------------------------------- regressions (bug-hunt round 1)
    def test_70_keepalive_unread_body_does_not_corrupt_next_request(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", PORT)
        hdr = {"Content-Type": "application/json", "Authorization": "Bearer " + self.payroll}
        conn.request("POST", "/api/payroll/runs/2099-01/finalize", body=b'{"ignored": true}', headers=hdr)
        r1 = conn.getresponse()
        r1.read()
        self.assertEqual(r1.status, 409)
        conn.request("GET", "/api/payroll/runs", headers=hdr)  # same socket
        r2 = conn.getresponse()
        r2.read()
        self.assertEqual(r2.status, 200)
        conn.close()

    def test_71_manager_sees_only_team(self):
        _, me = call("GET", "/api/auth/me", token=self.manager)
        _, lst = call("GET", "/api/employees", token=self.manager)
        _, team = call("GET", f"/api/employees?manager_id={me['emp_id']}", token=self.hr)
        self.assertEqual(len(lst["items"]), len(team["items"]) + 1)
        self.assertEqual(call("GET", "/api/employees/1", token=self.manager)[0], 403)

    def test_72_reporting_loop_rejected(self):
        # employee 4 manages employee 14 → making 14 the manager of 4 must fail
        self.assertEqual(call("PUT", "/api/employees/4", {"manager_id": 14}, self.hr)[0], 400)
        self.assertEqual(call("POST", "/api/employees/4/events", {"event_type": "Transfer", "manager_id": 14}, self.hr)[0], 400)

    def test_73_exit_finalised_after_last_day(self):
        from backend.core.utils import run_daily
        s, res = call("POST", "/api/employees", {"full_name": "Leaving Soon", "join_date": "2024-01-01", "create_login": True}, self.admin)
        emp_id = res["employee"]["id"]
        future = (date.today() + timedelta(days=5)).isoformat()
        call("POST", f"/api/employees/{emp_id}/events", {"event_type": "Resignation", "exit_date": future}, self.hr)
        _, e = call("GET", f"/api/employees/{emp_id}", token=self.hr)
        self.assertEqual(e["status"], "On Notice")
        conn = db.connect()
        conn.execute("UPDATE employees SET exit_date = ? WHERE id = ?", ((date.today() - timedelta(days=1)).isoformat(), emp_id))
        conn.commit()
        run_daily(conn, force=True)
        conn.close()
        _, e = call("GET", f"/api/employees/{emp_id}", token=self.hr)
        self.assertEqual(e["status"], "Resigned")
        self.assertEqual(call("POST", "/api/auth/login", {"username": res["login"]["username"], "password": res["login"]["temporary_password"]})[0], 403)
        _, day = call("GET", f"/api/attendance/daily?date={date.today().isoformat()}", token=self.hr)
        self.assertNotIn(emp_id, [r["id"] for r in day["rows"]])

    def test_74_admin_cannot_lock_themselves_out(self):
        _, me = call("GET", "/api/auth/me", token=self.admin)
        self.assertEqual(call("PUT", f"/api/users/{me['id']}", {"role": "employee"}, self.admin)[0], 400)
        self.assertEqual(call("PUT", f"/api/users/{me['id']}", {"is_active": False}, self.admin)[0], 400)

    def test_75_csv_formula_injection_neutralised(self):
        call("POST", "/api/notices", {"title": "x"}, self.hr)
        s, c = call("POST", "/api/employees", {"full_name": "=HYPERLINK(\"http://evil\")", "join_date": "2025-01-01"}, self.hr)
        s, raw = call("GET", "/api/reports/employee-master?format=csv", token=self.hr)
        self.assertIn(b"'=HYPERLINK", raw)
        call("DELETE", f"/api/employees/{c['employee']['id']}", token=self.hr)

    def test_76_future_attendance_cannot_be_marked_present(self):
        future = (date.today() + timedelta(days=3)).isoformat()
        self.assertEqual(call("POST", "/api/attendance/mark-all", {"date": future}, self.hr)[0], 400)

    def test_77_expired_notices_hidden_from_employees(self):
        call("POST", "/api/notices", {"title": "Old news", "expires_on": "2020-01-01"}, self.hr)
        _, mine = call("GET", "/api/notices", token=self.employee)
        self.assertNotIn("Old news", [n["title"] for n in mine["items"]])
        _, hr = call("GET", "/api/notices", token=self.hr)
        self.assertIn("Old news", [n["title"] for n in hr["items"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
