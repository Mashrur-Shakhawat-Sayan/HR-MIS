# 01 · Overview & feature catalogue

HR-MIS is a Human Resource Management Information System for any group of companies or large organisation:
a conglomerate such as Meghna Group (MGI, the maker of Fresh), Akij Group or United Group, a large single company
such as Grameenphone, or a mid-sized firm with one office. Units, departments, designations, leave types, holidays,
payroll rules and the employee ID prefix are all set inside the app, so it fits a new company without code changes.

The demo data models **Sonar Tori Group**, a fictional conglomerate: a head office plus sister concerns (paper, cement,
LP gas, food & beverage, steel), each with its own departments, staff and reporting lines. Companies named on this page
are examples of the kind of organisation HR-MIS suits; the project is not affiliated with or endorsed by any of them. All business rules default to Bangladesh practice
(Labour Act 2006 leave entitlements, BDT, lakh/crore number formatting, Friday–Saturday weekend, July–June
fiscal year) and every rule can be changed in **Settings**.

## Who uses it

| Role | Typical person | Main screens |
|---|---|---|
| System Administrator | IT / HRIS admin | Users & roles, Settings, Audit trail, backups |
| HR Manager | Head of HR | Everything, including salaries and payroll |
| HR Officer | HR executive | Employees, attendance, leave, recruitment, training, assets, notices (no salaries) |
| Payroll Officer | Accounts / payroll | Payroll, loans, claims, salary and bank details |
| Line Manager | Department / section head | Team leave and claim approvals, team attendance, team reviews |
| Employee | Everyone | My Workspace (self-service) |

Every employee can also be given a second role, for example an HR officer who is also an employee, without
any extra setup. *My Workspace* appears for anyone whose login is linked to an employee record.

## Feature catalogue

### 1. Dashboard
- Personal greeting with today's check-in status and leave balances
- KPIs (filtered by role): headcount, present / late / on leave today, approvals waiting, monthly gross payroll, joiners and exits, open positions
- Attendance trend for the last 7 working days, headcount by department, gender and employment-type mix
- Approval inbox: approve or reject leave and claims in one click
- Notice board, upcoming holidays, birthdays and work anniversaries, open checklist count

### 2. Employees
- Directory with search (name, ID, phone, email, designation) and filters (unit, department, type, status)
- 30+ fields: identity (NID, e-TIN, parents), contact, emergency contact, job, reporting manager, pay and bank
- Auto-generated employee IDs (`ST-1001`, … in the demo; `EMP-` on a fresh install) with a configurable prefix
- Profile tabs: overview, job & pay, leave & attendance, career history, checklists, documents
- Document vault: upload NID copies, certificates, contracts and similar files (up to 10 MB each), then download or delete them
- Printable employee ID card (CR-80 size)
- Optional login creation at hire time, with a one-time temporary password
- Salary, bank and NID fields hidden from users without `employees.salary`
- Delete protection: employees with payroll history must be archived (resigned / terminated) instead

### 3. Organisation
- Business units (sister concerns) with code and location
- Departments per unit with department head and cost centre
- Designations with grade and seniority level
- Live organisation chart built from reporting lines
- Headcount per unit, department and designation; deletion blocked while staff are assigned

### 4. Lifecycle
- Career events that **update the employee record** and keep history: promotion, transfer, increment (amount or %), confirmation, resignation, termination, retirement, re-hire
- Direct edits to designation, department or salary are also logged automatically
- Onboarding checklist (8 tasks) created for every new joiner; offboarding checklist (9 tasks: assets, accounts, final settlement, exit interview, release letter) created for every exit
- Probation tracker: confirmations due in the next 30 days, with overdue flags
- Disciplinary register: verbal and written warnings, show-cause, suspension and termination, each with status and resolution

### 5. Attendance
- Daily sheet for all employees: status, check-in, check-out, worked hours and note; save in bulk
- Statuses: Present, Late, Half day, Absent, On leave, Work from home, On duty
- Automatic **late** marking from office start time + grace minutes
- "Mark unmarked as present" for fast entry
- Monthly register grid (days × employees) with weekends and holidays shaded, plus totals and attendance %
- CSV import from fingerprint / face-recognition devices (`employee_id,date,in,out[,status]`), with a per-line error report
- Employee self check-in and check-out from the dashboard or My Attendance
- Holiday calendar (national, religious, company, optional) shared by attendance, leave and payroll

### 6. Leave
- Leave types with days per year, gender restriction, paid or unpaid, calendar or working-day counting, and carry-forward rules
- Defaults: Casual 10, Sick 14, Earned 20, Maternity 112 (calendar days, female), Paternity 5 (male), Unpaid
- Apply (employee) or apply on behalf (HR, optionally pre-approved); half-day leave; live day count and balance preview
- Overlap and balance checks
- Workflow: Pending → Approved / Rejected → Cancelled, with remarks. Line managers approve only their own team, and nobody approves their own request
- Approval writes "On leave" into attendance; cancelling or rejecting removes it
- Balance sheet for all employees; opening balances, carry-forward and encashment adjustments
- "Who's away" monthly calendar

### 7. Payroll
- Monthly run: preview → generate (draft) → adjust → finalize (locked) → mark paid; reopen when needed
- Salary structure from gross: basic / house rent / medical / conveyance percentages
- Pro-rating for mid-month joiners and leavers
- Overtime (basic ÷ 208 × 2 per hour by default), festival bonus (basic × %), additions and arrears
- Deductions: provident fund (employee share; employer share reported), income tax TDS, leave-without-pay (absent, half-day, unpaid leave and every N late arrivals), loan installments, other
- Payslip with amount in words (Taka … only), printable or saved as PDF, released to employees once finalized
- Exports: payroll register, bank advice (account-wise net), PF contribution statement
- Payroll history with totals per month

### 8. Loans & salary advances
- Types: salary advance, personal, house building, vehicle, medical, other
- Employee requests → payroll approves → installments deducted automatically → loan closes itself when repaid
- Manual repayments, repayment history, outstanding balance

### 9. Expense claims
- Employees submit claims (travel, food, fuel, mobile, medical and more)
- Approve or reject (managers for their team, payroll for everyone), then mark as paid
- Totals by status; claims summary report by category

### 10. Recruitment
- Job openings per department and unit with vacancies, salary range, deadline and status
- Candidate pipeline board: Applied → Screening → Interview → Offer → Hired / Rejected, with ratings and interview dates
- **Onboard** a hired candidate in one click: the employee form opens prefilled with their details

### 11. Performance
- Review per period with five 1–5 factors (quality, productivity, teamwork, punctuality, initiative)
- Automatic score and rating band (Outstanding / Exceeds / Meets / Needs improvement)
- Goals and comments; Draft → Submitted → Acknowledged
- Line managers review only their direct reports

### 12. Training
- Programs with category, trainer, date, hours, venue, mode, cost and status
- Nominate participants and mark attendance
- KPIs: programs, person-hours delivered, spend

### 13. Assets
- Register of laptops, phones, SIMs, vehicles and more, with tag, serial, value and condition
- Issue to an employee and record the return with its condition; assets show on the employee's profile

### 14. Notice board
- Announcements with audience, priority and optional expiry; shown on everyone's dashboard

### 15. Reports (17)

| Group | Reports |
|---|---|
| People | Employee master list · Headcount by department & unit · Joiners and leavers · Turnover by department · Birthdays & anniversaries · Probation / contract / interns |
| Time & leave | Monthly attendance summary · Late-comers and absentees · Leave register · Leave balance statement |
| Payroll | Payroll summary by month · Salary cost by department · Outstanding loans · Expense claims by category |
| Talent | Training summary · Performance ratings |
| Administration | Asset register |

Every report can be previewed on screen, printed, and exported to CSV (opens in Excel).

### 16. Administration & security
- Users & roles: create logins, link them to employees, change roles, disable accounts, reset passwords (forces a change at next sign-in)
- Permission matrix: see exactly what each role can do
- Audit trail of every sign-in, create, update, delete and export, with the user, time, IP address and changed fields
- Settings: company profile, ID prefix, office hours, grace minutes, weekend days, late-to-LWP rule, probation period, all payroll percentages and divisors
- Backups: download a consistent copy of the database, or save one on the server

### 17. My workspace (self-service)
- **My Profile:** view details and career history; update phone, address and emergency contact; download own documents
- **My Attendance:** check in and out, monthly history and totals
- **My Leave:** balances, apply, cancel, follow status and remarks
- **My Payslips:** view and print payslips; request loans and advances and track repayment
- **My Claims:** submit, edit and track expense claims

### 18. Interface
- Light and dark themes: follows the Windows setting by default; the moon/sun button switches and remembers the choice
- **Ctrl + K** (or `/`) search palette to jump to any page or open any employee you are allowed to see
- Headline figures in one ruled strip; status colours carry meaning (green done, marigold needs attention, red problem)
- Attendance register drawn as coloured status tiles, with weekends and holidays shaded
- Bundled fonts (Instrument Sans, Bricolage Grotesque) and icons: nothing is loaded from the internet
- Works on phones and tablets; visible keyboard focus; respects reduced-motion settings
- Payslips, ID cards and reports always print as clean white pages
