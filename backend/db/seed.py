"""Initial data.

`seed_base`  — always: administrator account, leave types (BD Labour Act defaults), holiday calendar.
`seed_demo`  — optional: a realistic sample organisation, the fictional Sonar Tori Group, with ~60 days of history,
               demo login accounts for every role, and one paid payroll month.

Demo logins (change or disable them before real use):
    admin / Admin@123          System Administrator
    hr.manager / Hr@12345      HR Manager
    hr.officer / Hr@12345      HR Officer
    payroll / Pay@12345        Payroll Officer
    manager / Mgr@12345        Line Manager (IT)
    employee / Emp@12345       Employee (IT)
"""
import random
from datetime import date, timedelta

from ..core import db
from ..core.security import hash_password
from ..core.utils import Calendar, get_settings, now, save_settings

LEAVE_TYPES = [
    # name, days/year, gender, paid, calendar_days, carry_forward, max_carry, color
    ("Casual", 10, "Any", 1, 0, 0, 0, "#12866e"),
    ("Sick", 14, "Any", 1, 0, 0, 0, "#2463b0"),
    ("Earned", 20, "Any", 1, 0, 1, 40, "#d9912b"),
    ("Maternity", 112, "Female", 1, 1, 0, 0, "#b5487a"),
    ("Paternity", 5, "Male", 1, 0, 0, 0, "#7a4fb5"),
    ("Unpaid", 0, "Any", 0, 0, 0, 0, "#6b7684"),
]

HOLIDAYS = [
    ("2026-02-21", "Shaheed Day & International Mother Language Day", "National"),
    ("2026-03-20", "Eid-ul-Fitr (tentative)", "Religious"), ("2026-03-21", "Eid-ul-Fitr (tentative)", "Religious"),
    ("2026-03-22", "Eid-ul-Fitr (tentative)", "Religious"), ("2026-03-26", "Independence Day", "National"),
    ("2026-04-14", "Pahela Baishakh", "National"), ("2026-05-01", "May Day", "National"),
    ("2026-05-26", "Eid-ul-Adha (tentative)", "Religious"), ("2026-05-27", "Eid-ul-Adha (tentative)", "Religious"),
    ("2026-05-28", "Eid-ul-Adha (tentative)", "Religious"), ("2026-08-05", "July Mass Uprising Day", "National"),
    ("2026-12-16", "Victory Day", "National"), ("2026-12-25", "Christmas Day", "Religious"),
    ("2027-02-21", "Shaheed Day & International Mother Language Day", "National"),
    ("2027-03-09", "Eid-ul-Fitr (tentative)", "Religious"), ("2027-03-10", "Eid-ul-Fitr (tentative)", "Religious"),
    ("2027-03-11", "Eid-ul-Fitr (tentative)", "Religious"), ("2027-03-26", "Independence Day", "National"),
    ("2027-04-14", "Pahela Baishakh", "National"), ("2027-05-01", "May Day", "National"),
    ("2027-05-16", "Eid-ul-Adha (tentative)", "Religious"), ("2027-05-17", "Eid-ul-Adha (tentative)", "Religious"),
    ("2027-05-18", "Eid-ul-Adha (tentative)", "Religious"), ("2027-08-05", "July Mass Uprising Day", "National"),
    ("2027-12-16", "Victory Day", "National"), ("2027-12-25", "Christmas Day", "Religious"),
]


def seed_base(conn, admin_password="Admin@123"):
    if not db.scalar(conn, "SELECT COUNT(*) FROM users WHERE username = 'admin'"):
        db.insert(conn, "users", {"username": "admin", "password_hash": hash_password(admin_password), "role": "admin",
                                  "is_active": 1, "must_change_pw": 0, "created_at": now()})
    if not db.scalar(conn, "SELECT COUNT(*) FROM leave_types"):
        for n, days, g, paid, cal, cf, mx, color in LEAVE_TYPES:
            db.insert(conn, "leave_types", {"name": n, "days_per_year": days, "gender": g, "paid": paid, "calendar_days": cal,
                                            "carry_forward": cf, "max_carry": mx, "active": 1, "color": color})
    for dt, name, kind in HOLIDAYS:
        conn.execute("INSERT OR IGNORE INTO holidays (date, name, type) VALUES (?,?,?)", (dt, name, kind))


DEMO_COMPANY = {
    "company_name": "Sonar Tori Group",
    "company_short": "ST",
    "company_address": "Tejgaon, Dhaka-1208, Bangladesh",
    "employee_code_prefix": "ST-",
}


def seed_demo(conn):
    rnd = random.Random(20260601)
    T = date.today()
    iso = lambda x: x.isoformat()
    ts = now()

    # The demo company is fictional. Real installations set their own name in Settings.
    save_settings(conn, DEMO_COMPANY)
    units = [("Head Office", "HO", "Tejgaon, Dhaka"), ("Sonar Tori Paper Mills", "STP", "Plant site"),
             ("Sonar Tori Cement", "STC", "Plant site"), ("Sonar Tori LP Gas", "STL", "Plant & depots"),
             ("Sonar Tori Food & Beverage", "STF", "Plant site"), ("Sonar Tori Steel", "STS", "Plant site")]
    unit_id = {n: db.insert(conn, "business_units", {"name": n, "code": c, "location": l, "created_at": ts}) for n, c, l in units}
    depts = [("Human Resources", "Head Office", "CC-100"), ("Finance & Accounts", "Head Office", "CC-110"),
             ("Information Technology", "Head Office", "CC-120"), ("Sales & Marketing", "Sonar Tori LP Gas", "CC-310"),
             ("Supply Chain", "Sonar Tori Cement", "CC-220"), ("Production", "Sonar Tori Paper Mills", "CC-410"),
             ("Administration", "Head Office", "CC-130"), ("Quality Control", "Sonar Tori Food & Beverage", "CC-520")]
    dept_id = [db.insert(conn, "departments", {"name": n, "unit_id": unit_id[u], "cost_center": cc, "created_at": ts}) for n, u, cc in depts]
    desig = [("Executive Director", "M1", 380000), ("General Manager", "M2", 230000), ("Deputy General Manager", "M3", 165000),
             ("Senior Manager", "M4", 125000), ("Manager", "M5", 92000), ("Assistant Manager", "M6", 66000),
             ("Senior Executive", "E1", 50000), ("Executive", "E2", 38000), ("Junior Executive", "E3", 29000),
             ("Officer", "E4", 24000), ("Intern", "I1", 12000)]
    desig_id = [db.insert(conn, "designations", {"title": t, "grade": g, "level": i + 1, "created_at": ts}) for i, (t, g, _) in enumerate(desig)]

    plan = [(6, 0), (0, 1), (1, 3), (2, 3), (3, 2), (4, 4), (5, 3), (7, 4), (0, 5), (0, 7), (1, 5), (1, 7), (2, 6), (2, 7),
            (2, 8), (3, 6), (3, 7), (3, 9), (4, 7), (5, 6), (5, 9), (5, 9), (7, 7), (6, 8), (0, 8), (2, 10),
            (3, 7), (3, 8), (4, 8), (5, 7), (5, 8), (6, 9), (7, 8), (1, 8), (2, 7), (5, 9)]
    male = ["Tanvir", "Mahmudul", "Rakibul", "Shakil", "Arif", "Imran", "Sabbir", "Fahim", "Nayeem", "Sohel", "Jahidul",
            "Mehedi", "Raihan", "Asif", "Kamrul", "Tariq", "Ashraf", "Rezaul", "Masud", "Nazmul", "Habib", "Saiful", "Rubel", "Monir"]
    female = ["Nusrat", "Farzana", "Sadia", "Tahmina", "Ayesha", "Sharmin", "Rumana", "Jannatul", "Lamia", "Sumaiya", "Afroza", "Nasrin"]
    last_m = ["Hossain", "Ahmed", "Rahman", "Islam", "Chowdhury", "Karim", "Sarker", "Khan", "Uddin", "Haque", "Alam", "Bhuiyan", "Talukder", "Mia"]
    last_f = ["Akter", "Rahman", "Islam", "Chowdhury", "Haque", "Sultana", "Ahmed", "Khatun"]
    areas = ["Banani, Dhaka", "Badda, Dhaka", "Uttara, Dhaka", "Mirpur, Dhaka", "Dhanmondi, Dhaka", "Mohammadpur, Dhaka",
             "Rampura, Dhaka", "Narayanganj", "Gazipur", "Banasree, Dhaka"]
    banks = ["Dutch-Bangla Bank", "BRAC Bank", "The City Bank", "Eastern Bank", "Islami Bank Bangladesh", "Prime Bank"]
    emps, mi, fi = [], 0, 0
    for i, (di, gi) in enumerate(plan):
        gender = "Female" if i % 3 == 1 else "Male"
        if i == 14:
            name, gender = "Pritom Das", "Male"
        elif i == 16:
            name = "Ananya Saha"
        elif gender == "Male":
            name = f"{male[mi % len(male)]} {rnd.choice(last_m)}"
            mi += 1
        else:
            name = f"{female[fi % len(female)]} {rnd.choice(last_f)}"
            fi += 1
        first, last = name.split()[0].lower(), name.split()[-1].lower()
        by = 1966 + gi * 2 + rnd.randint(0, 6)
        dob = f"{by}-{T.month if i in (4, 13, 27) else rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}"
        etype, join, status, exit_date, reason = "Permanent", f"{rnd.randint(2012, 2025)}-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}", "Active", None, None
        if gi == 10:
            etype, join = "Intern", iso(T - timedelta(days=110))
        if i in (21, 30):
            etype, join = "Probation", iso(T - timedelta(days=170 if i == 21 else 60))
        if i == 22:
            etype = "Contract"
        if i == 7:
            join = f"{T.year - 5}-{T.month:02d}-{rnd.randint(1, 28):02d}"
        if i == 24:
            status, exit_date, reason = "Resigned", iso(T.replace(day=1) - timedelta(days=1)), "Higher studies abroad"
        gross = round(desig[gi][2] * (0.92 + rnd.random() * 0.16) / 500) * 500
        e = {"code": f"ST-{1001 + i}", "full_name": name, "gender": gender, "dob": dob,
             "marital_status": rnd.choice(["Married", "Single"]) if gi < 8 else "Single", "blood_group": rnd.choice(["A+", "B+", "O+", "AB+", "O+", "B+", "A-", "O-"]),
             "phone": "01" + rnd.choice("789356") + str(rnd.randint(10000000, 99999999)), "email": f"{first}.{last}@example.com",
             "present_address": rnd.choice(areas), "permanent_address": rnd.choice(["Cumilla", "Sylhet", "Rajshahi", "Khulna", "Barishal", "Rangpur", "Mymensingh", "Bogura"]),
             "emergency_name": rnd.choice(["Father", "Mother", "Spouse", "Brother"]), "emergency_phone": "01" + str(rnd.randint(300000000, 999999999)),
             "unit_id": unit_id[depts[di][1]], "dept_id": dept_id[di], "designation_id": desig_id[gi], "grade": desig[gi][1],
             "emp_type": etype, "join_date": join, "status": status, "exit_date": exit_date, "exit_reason": reason, "gross_salary": gross,
             "bank_name": rnd.choice(banks), "bank_account": str(rnd.randint(100, 999)) + str(rnd.randint(1000000000, 9999999999)),
             "pf_member": 0 if etype in ("Intern", "Probation") else 1, "created_at": ts}
        e["id"] = db.insert(conn, "employees", e)
        e["_dept"] = di
        emps.append(e)
    heads = {}
    for e in emps:
        heads.setdefault(e["_dept"], e["id"])
    for di, eid in heads.items():
        db.update(conn, "departments", dept_id[di], {"head_emp_id": eid})
    for e in emps[1:]:
        mgr = heads[e["_dept"]] if heads[e["_dept"]] != e["id"] else emps[0]["id"]
        db.update(conn, "employees", e["id"], {"manager_id": mgr})
        e["manager_id"] = mgr
    for e in emps:
        db.insert(conn, "emp_events", {"emp_id": e["id"], "event_type": "Joining", "effective_date": e["join_date"],
                                       "new_value": e["emp_type"], "details": "Joined the company", "created_by": "system", "created_at": ts})
    for idx, old, new in ((3, "Manager", "Senior Manager"), (12, "Executive", "Senior Executive")):
        db.insert(conn, "emp_events", {"emp_id": emps[idx]["id"], "event_type": "Promotion", "effective_date": f"{T.year - 1}-07-01",
                                       "old_value": old, "new_value": new, "details": "Annual promotion", "created_by": "system", "created_at": ts})
    db.insert(conn, "emp_events", {"emp_id": emps[24]["id"], "event_type": "Resignation", "effective_date": emps[24]["exit_date"],
                                   "old_value": "Active", "new_value": "Resigned", "details": "Higher studies abroad", "created_by": "system", "created_at": ts})
    newbie = emps[30]
    for k, (task, owner) in enumerate([("Collect signed appointment letter", "HR"), ("Collect NID, photos and academic certificates", "HR"),
                                       ("Open salary bank account / verify account details", "Accounts"), ("Issue employee ID card", "HR"),
                                       ("Create email and system accounts", "IT"), ("Issue laptop / equipment", "IT"),
                                       ("Department induction and introduction to team", "Line Manager")]):
        db.insert(conn, "emp_tasks", {"emp_id": newbie["id"], "category": "Onboarding", "task": task, "owner": owner,
                                      "due_date": newbie["join_date"], "done": 1 if k < 5 else 0, "done_at": ts if k < 5 else None})

    # ---- demo logins
    accounts = [("hr.manager", "Hr@12345", "hr_manager", 1), ("hr.officer", "Hr@12345", "hr_officer", 9),
                ("payroll", "Pay@12345", "payroll_officer", 10), ("manager", "Mgr@12345", "manager", 3),
                ("employee", "Emp@12345", "employee", 13)]
    for u, pw, role, idx in accounts:
        db.insert(conn, "users", {"username": u, "password_hash": hash_password(pw), "role": role, "emp_id": emps[idx]["id"],
                                  "is_active": 1, "must_change_pw": 0, "created_at": ts})

    # ---- attendance (last ~65 days)
    cal = Calendar(conn)
    for k in range(65, -1, -1):
        dd = iso(T - timedelta(days=k))
        if not cal.is_workday(dd):
            continue
        for e in emps:
            if e["join_date"] > dd or (e["exit_date"] and dd > e["exit_date"]):
                continue
            r = rnd.random()
            if k == 0:
                if r < .8:
                    m = rnd.randint(520, 575)
                    conn.execute("INSERT INTO attendance (emp_id,date,status,check_in,source) VALUES (?,?,?,?, 'Device')",
                                 (e["id"], dd, "L" if cal.is_late(f"{m // 60:02d}:{m % 60:02d}") else "P", f"{m // 60:02d}:{m % 60:02d}"))
                continue
            if r < .87:
                st, a, b = "P", rnd.randint(520, 554), rnd.randint(1075, 1125)
            elif r < .94:
                st, a, b = "L", rnd.randint(556, 620), rnd.randint(1080, 1140)
            elif r < .965:
                st, a, b = "A", None, None
            elif r < .98:
                st, a, b = "WFH", 540, 1080
            else:
                st, a, b = "HD", rnd.randint(520, 550), rnd.randint(780, 820)
            fmt = lambda m: f"{m // 60:02d}:{m % 60:02d}" if m else None
            conn.execute("INSERT INTO attendance (emp_id,date,status,check_in,check_out,source) VALUES (?,?,?,?,?, 'Device')",
                         (e["id"], dd, st, fmt(a), fmt(b)))

    # ---- leave
    lt = {r["name"]: r["id"] for r in db.q(conn, "SELECT id, name FROM leave_types")}

    def wd(start, n, step):
        x, c = start, 0
        while c < n:
            x = x + timedelta(days=step)
            if cal.is_workday(iso(x)):
                c += 1
        return iso(x)

    leaves = [(9, "Casual", wd(T, 12, -1), wd(T, 11, -1), "Family program in Sylhet", "Approved"),
              (12, "Sick", wd(T, 6, -1), wd(T, 6, -1), "Fever", "Approved"),
              (3, "Earned", wd(T, 22, -1), wd(T, 20, -1), "Annual vacation", "Approved"),
              (15, "Earned", wd(T, 4, 1), wd(T, 6, 1), "Visiting hometown", "Pending"),
              (2, "Casual", wd(T, 1, 1), wd(T, 1, 1), "Personal work at the bank", "Pending"),
              (20, "Paternity", wd(T, 8, 1), wd(T, 12, 1), "Birth of child", "Pending"),
              (13, "Casual", wd(T, 3, 1), wd(T, 3, 1), "Family matter", "Pending"),
              (18, "Sick", wd(T, 3, -1), wd(T, 3, -1), "Not mentioned", "Rejected")]
    for idx, name, a, b, reason, status in leaves:
        days = len(cal.workdays(a, b))
        rid = db.insert(conn, "leave_requests", {"emp_id": emps[idx]["id"], "leave_type_id": lt[name], "from_date": a, "to_date": b,
                                                 "days": days, "reason": reason, "status": status, "applied_at": ts, "applied_by": "system",
                                                 "decided_by": "hr.manager" if status != "Pending" else None, "decided_at": ts if status != "Pending" else None})
        if status == "Approved":
            for x in cal.workdays(a, b):
                conn.execute("""INSERT INTO attendance (emp_id,date,status,source,note) VALUES (?,?,'LV','Leave',?)
                                ON CONFLICT(emp_id,date) DO UPDATE SET status='LV', check_in=NULL, check_out=NULL, source='Leave'""",
                             (emps[idx]["id"], x, f"Leave #{rid}"))
    db.insert(conn, "leave_adjustments", {"emp_id": emps[3]["id"], "leave_type_id": lt["Earned"], "year": T.year, "days": 8,
                                          "note": "Carry forward from previous year", "created_by": "system", "created_at": ts})

    # ---- claims, loans
    for k, (idx, cat, amt, desc, st) in enumerate([(5, "Travel", 4850, "Bus & hotel — Chattogram site visit", "Pending"),
                                                   (16, "Mobile Bill", 1200, "Monthly mobile allowance", "Approved"),
                                                   (13, "Food", 980, "Overtime dinner — server migration", "Pending"),
                                                   (3, "Fuel", 3500, "Fuel for depot inspection", "Paid"),
                                                   (8, "Medical", 2600, "Doctor visit", "Rejected"),
                                                   (19, "Travel", 7200, "Plant visit — Narayanganj", "Approved")]):
        db.insert(conn, "claims", {"emp_id": emps[idx]["id"], "claim_date": wd(T, k * 2 + 1, -1), "category": cat, "amount": amt,
                                   "description": desc, "status": st, "decided_by": None if st == "Pending" else "payroll",
                                   "created_at": ts})
    prev_month = (T.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    loans = [(17, "Salary Advance", 20000, 5000, prev_month, "Active"), (11, "Personal Loan", 150000, 12500, prev_month, "Active"),
             (22, "Medical Loan", 30000, 6000, T.strftime("%Y-%m"), "Pending")]
    for idx, kind, p, inst, start, st in loans:
        db.insert(conn, "loans", {"emp_id": emps[idx]["id"], "loan_type": kind, "principal": p, "installment": inst, "start_month": start,
                                  "issued_on": iso(T - timedelta(days=40)), "purpose": "Personal need", "status": st,
                                  "approved_by": "payroll" if st == "Active" else None, "created_at": ts})

    # ---- recruitment
    jobs = [("Senior Software Engineer", 2, 0, 2, "Permanent", "80,000–1,10,000", "Open", 20),
            ("Sales Executive", 3, 3, 5, "Permanent", "35,000–45,000", "Open", 12),
            ("Production Supervisor", 5, 1, 1, "Permanent", "45,000–55,000", "On Hold", 30),
            ("HR Intern", 0, 0, 2, "Intern", "12,000", "Closed", -10)]
    job_id = {}
    for k, (title, di, ui, vac, typ, sal, st, dl) in enumerate(jobs):
        job_id[title] = db.insert(conn, "jobs", {"title": title, "dept_id": dept_id[di], "unit_id": unit_id[units[ui][0]], "vacancies": vac,
                                                 "emp_type": typ, "salary_range": sal, "posted_on": iso(T - timedelta(days=25 - k * 3)),
                                                 "deadline": iso(T + timedelta(days=dl)), "status": st,
                                                 "description": f"We are hiring a {title} to join our growing team."})
    for k, (name, job, src, stage, rating, exp) in enumerate([
            ("Shuvo Ahmed", "Senior Software Engineer", "Bdjobs", "Interview", 4, 95000),
            ("Mahfuza Akter", "Senior Software Engineer", "LinkedIn", "Screening", 4, 100000),
            ("Rashed Kabir", "Senior Software Engineer", "Referral", "Offer", 5, 105000),
            ("Ibrahim Khalil", "Sales Executive", "Bdjobs", "Applied", 3, 38000),
            ("Tania Sultana", "Sales Executive", "Walk-in", "Interview", 4, 40000),
            ("Sajib Hasan", "Sales Executive", "Campus", "Applied", 3, 35000),
            ("Nafisa Tabassum", "Sales Executive", "LinkedIn", "Rejected", 2, 45000),
            ("Riyad Hossain", "HR Intern", "Campus", "Hired", 4, 12000)]):
        db.insert(conn, "candidates", {"job_id": job_id[job], "name": name, "phone": f"0171{1000000 + k * 137911}",
                                       "email": name.split()[0].lower() + "@example.com", "source": src, "expected_salary": exp,
                                       "stage": stage, "rating": rating, "interview_date": wd(T, 2 + k % 3, 1) if stage == "Interview" else None,
                                       "created_at": ts})

    # ---- performance, training, assets, notices, disciplinary
    for idx, rev, sc, comment in [(9, 1, (4, 4, 5, 4, 4), "Reliable and organised; ready for more ownership."),
                                  (13, 3, (5, 4, 4, 3, 5), "Strong delivery on the ERP integration."),
                                  (12, 3, (4, 4, 4, 4, 4), "Consistent performer."),
                                  (17, 4, (3, 4, 4, 3, 3), "Meets targets; work on reporting discipline."),
                                  (11, 2, (4, 5, 4, 5, 4), "Excellent month-end closing turnaround.")]:
        db.insert(conn, "reviews", {"emp_id": emps[idx]["id"], "reviewer_id": emps[rev]["id"], "period": f"{T.year} H1",
                                    "quality": sc[0], "productivity": sc[1], "teamwork": sc[2], "punctuality": sc[3], "initiative": sc[4],
                                    "score": round(sum(sc) / 5, 2), "comments": comment, "goals": "Agreed goals for next period",
                                    "status": "Submitted", "created_at": ts})
    trs = [("Fire Safety & Evacuation Drill", "Safety", "Safety Officer", -15, 3, "Production floor", "Classroom", 0, "Completed", [5, 6, 19, 20, 21, 29, 30, 35]),
           ("Advanced Excel for Finance", "Technical", "External trainer", 6, 12, "Head Office Training Room", "Classroom", 45000, "Scheduled", [2, 10, 11, 33]),
           ("Leadership Development Program", "Leadership", "Consultant", 20, 16, "Online", "Online", 120000, "Scheduled", [3, 4, 5, 6, 7]),
           ("New Joiner Orientation", "Onboarding", "HR", -50, 4, "Head Office", "Classroom", 0, "Completed", [25, 21, 30])]
    for title, cat, trainer, off, hrs, venue, mode, cost, st, who in trs:
        tid = db.insert(conn, "trainings", {"title": title, "category": cat, "trainer": trainer, "start_date": iso(T + timedelta(days=off)),
                                            "hours": hrs, "venue": venue, "mode": mode, "cost": cost, "status": st})
        for w in who:
            conn.execute("INSERT INTO training_participants (training_id, emp_id, attended) VALUES (?,?,?)",
                         (tid, emps[w]["id"], 1 if st == "Completed" else 0))
    for tag, name, cat, serial, idx, val in [("IT-LT-0012", "Dell Latitude 5440", "Laptop", "DL5440-88K2", 13, 125000),
                                             ("IT-LT-0019", "HP ProBook 450", "Laptop", "HPB450-1QZ", 12, 98000),
                                             ("IT-LT-0020", "Lenovo ThinkPad E14", "Laptop", "LTE14-77A", 3, 110000),
                                             ("IT-MB-0044", "Samsung Galaxy A35", "Mobile Phone", "SM-A356E-71", 15, 38000),
                                             ("IT-SIM-0103", "Corporate SIM", "SIM", "—", 16, 0),
                                             ("VH-0007", "Toyota Axio (pool car)", "Vehicle", "DHAKA-METRO-GA-XX", None, 2400000),
                                             ("IT-DT-0031", "Lenovo ThinkCentre M70", "Desktop", "LTC-M70-55", 10, 72000),
                                             ("IT-LT-0025", "Dell Latitude 3540", "Laptop", "DL3540-11B", None, 85000)]:
        db.insert(conn, "assets", {"tag": tag, "name": name, "category": cat, "serial": serial, "emp_id": emps[idx]["id"] if idx is not None else None,
                                   "issued_on": iso(T - timedelta(days=200)) if idx is not None else None, "value": val, "condition": "Good",
                                   "status": "Assigned" if idx is not None else "In Stock"})
    for off, title, body, aud, pr in [(0, "Annual performance review cycle", "The H2 review cycle opens on 1 December. Managers should complete reviews in HR-MIS before 20 December.", "All Employees", "Important"),
                                      (-6, "Health check-up camp at Head Office", "Free basic health screening on the 3rd floor, 10am–4pm. Bring your employee ID card.", "Head Office", "Normal"),
                                      (-14, "Updated travel allowance policy", "Revised TA/DA rates are effective from this month. Submit claims with receipts within 15 days.", "All Employees", "Normal")]:
        db.insert(conn, "notices", {"posted_on": iso(T + timedelta(days=off)), "title": title, "body": body, "audience": aud, "priority": pr, "created_by": "hr.manager"})
    db.insert(conn, "disciplinary", {"emp_id": emps[18]["id"], "action_date": iso(T - timedelta(days=20)), "action_type": "Verbal Warning",
                                     "reason": "Repeated late arrival", "issued_by": "Department Head", "status": "Closed",
                                     "resolution": "Punctuality improved", "created_at": ts})

    # ---- a paid payroll for last month (so payslips exist from day one)
    from ..modules import payroll as pr
    s = get_settings(conn)
    run_id = db.insert(conn, "payroll_runs", {"month": prev_month, "status": "Paid", "include_bonus": 0, "created_by": "payroll",
                                              "created_at": ts, "finalized_by": "payroll", "finalized_at": ts, "paid_at": ts})
    for e in pr.payroll_employees(conn, prev_month):
        adj = {"ot_hours": 10} if e["code"] in ("ST-1020", "ST-1021", "ST-1022") else {}
        row = pr.compute(conn, s, cal, e, prev_month, 0, adj, run_id)
        row["run_id"] = run_id
        db.insert(conn, "payslips", row)
        for loan_id, amt in pr.loan_deduction(conn, e["id"], prev_month, run_id)[1]:
            db.insert(conn, "loan_repayments", {"loan_id": loan_id, "month": prev_month, "amount": amt, "run_id": run_id, "note": "Payroll deduction"})
