# 09 · Payroll & policy rules

All percentages and divisors are in **Settings → Payroll rules** and **Settings → Working time**. The defaults below are a
common Bangladesh corporate structure. **Have your HR policy, finance team and tax adviser confirm the values before
paying real salaries.** HR-MIS applies the rules you configure; it does not give legal or tax advice.

## Salary structure

| Component | Default | Formula |
|---|---|---|
| Gross (monthly) | per employee | entered on the employee record |
| Basic | 60 % | gross × `basic_pct` |
| House rent | 30 % | gross × `house_rent_pct` |
| Medical | 6 % | gross × `medical_pct` |
| Conveyance | remainder (4 %) | gross − basic − house rent − medical |

Basic + house rent + medical may not exceed 100 % (the settings screen refuses it).

## Monthly calculation

| Item | Formula (defaults) | Setting |
|---|---|---|
| Paid days | calendar days employed in the month (joiners and leavers are pro-rated) | — |
| Gross for the month | full gross × paid days ÷ days in month | — |
| Overtime | basic_full ÷ **208** × **2** × OT hours | `ot_divisor_hours`, `ot_multiplier` |
| Festival bonus | basic_full × **100 %** (only when the run has *Include festival bonus* ticked) | `festival_bonus_pct` |
| Additions | typed per payslip (arrears, special allowances) | — |
| **Leave without pay (LWP) days** | absent days + ½ × half days + unpaid-leave working days + ⌊late days ÷ **3**⌋ | `late_per_lwp_day` (0 = off) |
| LWP deduction | basic_full ÷ **30** × LWP days (never more than the month's gross) | `lwp_divisor_days` |
| Provident fund (employee) | basic × **10 %** (PF members only) | `pf_employee_pct` |
| PF (employer), reported | basic × **10 %** | `pf_employer_pct` |
| Income tax (TDS) | gross × **3 %** when full gross ≥ **৳35,000** | `tax_pct`, `tax_min_gross` |
| Loan installments | Σ min(installment, outstanding) for active loans already started | — |
| Other deductions | typed per payslip | — |
| **Net pay** | gross + OT + bonus + additions − (PF + tax + LWP + loans + other) | — |

*basic_full* is the basic of the **full** monthly gross; it is used for day and hour rates, so a mid-month joiner's daily rate is the same as everyone else's.

### Worked example

Gross ৳50,000, PF member, 10 OT hours, 1 absent day, 2 late arrivals (below the 3-late threshold), no bonus, no loan.

| | ৳ |
|---|---|
| Basic 60 % | 30,000.00 |
| House rent 30 % | 15,000.00 |
| Medical 6 % | 3,000.00 |
| Conveyance (remainder) | 2,000.00 |
| Overtime 30,000 ÷ 208 × 2 × 10 | 2,884.62 |
| **Total earnings** | **52,884.62** |
| PF 10 % of basic | 3,000.00 |
| Tax 3 % of gross (50,000 ≥ 35,000) | 1,500.00 |
| LWP 30,000 ÷ 30 × 1 | 1,000.00 |
| **Total deductions** | **5,500.00** |
| **Net pay** | **47,384.62** |

## About income tax

Bangladesh income tax is calculated on **annual** taxable income using slabs, a tax-free threshold, exemptions and
investment rebates, and these change with each Finance Act. The flat monthly TDS in HR-MIS is a **placeholder estimate**.
Options:
1. Set `tax_pct` and `tax_min_gross` to approximate your company's average TDS.
2. Set `tax_pct` to 0 and enter each person's monthly TDS in **Other deductions**, as calculated by your tax adviser.
3. Implement the annual slab calculator (roadmap item). It plugs into `compute()` in `backend/modules/payroll.py`.

## Leave policy defaults (Bangladesh Labour Act 2006)

| Type | Default | Counting | Notes |
|---|---|---|---|
| Casual | 10 days / year | working days | |
| Sick | 14 days / year | working days | |
| Earned (annual) | 20 days / year | working days | The Act accrues earned leave by days worked; set your accrual policy and use *opening balances* for carry-forward (max 40 by default) |
| Maternity | 112 days (16 weeks) | calendar days | female employees only |
| Paternity | 5 days | working days | company policy, male employees only |
| Unpaid | no limit | working days | counts as LWP in payroll |

Add or change types in **Leave → Leave types & policy** (e.g. Study, Hajj, Compensatory). Changes affect balances
immediately; past approved leave keeps its day count.

## Working days

A day is a **working day** unless its weekday is in *Settings → Weekly holidays* (default Friday and Saturday; tick only Friday for a 6-day week) or it is in the **holiday calendar**.
Working days drive leave day counts, attendance %, unpaid-leave LWP and dashboard figures.

## Attendance thresholds

- **Late:** check-in later than `work_start` + `grace_minutes` (default 09:00 + 15 min).
- **Late → LWP:** every `late_per_lwp_day` late arrivals (default 3) costs one LWP day. Set it to 0 to disable.
- **Half day:** counts as ½ attended for attendance % and ½ LWP for pay.

## Things to set before going live

- [ ] Salary structure percentages match your appointment letters
- [ ] PF rates match your PF trust deed; untick *PF member* for staff not enrolled
- [ ] TDS approach decided (see above)
- [ ] OT eligibility: enter OT hours only for eligible staff (the Labour Act OT rule is meant for *workers*)
- [ ] Festival bonus percentage and which runs include it (two Eid bonuses for most companies)
- [ ] Weekend days and the holiday calendar for the year
- [ ] Leave entitlements and opening balances for existing staff
