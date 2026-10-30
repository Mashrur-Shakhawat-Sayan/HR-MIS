/** Payroll — monthly runs, adjustments, finalize/pay workflow, payslips, bank advice and PF exports. */
import { api } from '../core/api.js';
import { $, addMonths, badge, confirmBox, esc, fmtDateTime, ic, inWords, kpi, modal, money, monthName, num, on, printHTML, table, thisMonth, toast } from '../core/ui.js';

let C;
const S = { month: thisMonth(), data: null };

export async function render(main, ctx) {
  C = ctx;
  const [d, runs] = await Promise.all([api.get(`/api/payroll/runs/${S.month}`), api.get('/api/payroll/runs')]);
  S.data = d;
  const run = d.run, t = d.totals, draft = run.status === 'Draft', manage = ctx.can('payroll.manage');
  const editable = draft && manage;
  const mi = (r, k) => editable ? `<input class="mini" type="number" min="0" step="any" value="${r[k] || ''}" data-change="pay:adj" data-id="${r.id}" data-k="${k}" aria-label="${k.replace('_', ' ')}">` : num(r[k]);
  const actions = [];
  if (manage) {
    if (run.status === 'Not generated') actions.push(`<label class="chk"><input type="checkbox" id="payBonus"> Include festival bonus</label><button class="btn" data-act="pay:gen">${ic('calculator')}Generate payroll</button>`);
    if (draft) actions.push(`<label class="chk"><input type="checkbox" id="payBonus" ${run.include_bonus ? 'checked' : ''}> Festival bonus</label><button class="btn ghost" data-act="pay:gen">${ic('refresh')}Recalculate</button><button class="btn" data-act="pay:step" data-s="finalize">${ic('lock')}Finalize</button><button class="ib danger" title="Delete draft" aria-label="Delete draft" data-act="pay:delete">${ic('trash')}</button>`);
    if (run.status === 'Finalized') actions.push(`<button class="btn" data-act="pay:step" data-s="pay">${ic('check-circle')}Mark as paid</button><button class="btn ghost" data-act="pay:step" data-s="reopen">${ic('rotate')}Reopen</button>`);
  }
  const statusLine = run.status === 'Not generated' ? 'This is a preview from current salaries and attendance. Nothing is saved until you generate it.'
    : run.status === 'Draft' ? 'Draft. Enter overtime, additions and deductions in the table, then finalize.'
      : run.status === 'Finalized' ? `Locked by ${run.finalized_by} on ${fmtDateTime(run.finalized_at)}. Payslips are visible to employees.` : `Paid on ${fmtDateTime(run.paid_at)}.`;
  ctx.setTitle('Payroll', `${monthName(S.month)}: ${statusLine}`);
  main.innerHTML = `<div class="toolbar card"><span class="stepper"><button class="ib" title="Previous month" aria-label="Previous month" data-act="pay:month" data-d="-1">${ic('chev-left')}</button>
      <input type="month" value="${S.month}" data-change="pay:pick" aria-label="Pay month"><button class="ib" title="Next month" aria-label="Next month" data-act="pay:month" data-d="1">${ic('chev-right')}</button></span>
      ${badge(run.status)}<span class="grow"></span>${actions.join('')}</div>
    <div class="kpis">${kpi('Employees paid', t.count, monthName(S.month))}${kpi('Gross earnings', money(t.earnings), `Overtime ${money(t.ot_amount)}, bonus ${money(t.bonus)}`)}
      ${kpi('Deductions', money(t.deductions), `PF ${money(t.pf)}, tax ${money(t.tax)}, loans ${money(t.loan_deduction)}`)}
      ${kpi('Net payable', money(t.net), `Employer PF ${money(t.pf_employer)} on top`)}</div>
    <div class="card"><div class="card-head"><h3>Payroll register</h3><span class="count">${t.count} employees</span><span class="grow"></span>
      <button class="btn ghost" data-act="pay:csv" data-t="register">${ic('download')}Register</button><button class="btn ghost" data-act="pay:csv" data-t="bank">${ic('download')}Bank advice</button>
      <button class="btn ghost" data-act="pay:csv" data-t="pf">${ic('download')}PF statement</button>${run.id ? `<button class="btn ghost" data-act="pay:printall">${ic('printer')}All payslips</button>` : ''}</div>
    ${table([
      { l: 'ID', k: 'emp_code' }, { l: 'Employee', fmt: (r) => `<b>${esc(r.emp_name)}</b><br><small class="muted">${esc(r.designation || '')}</small>` },
      { l: 'Gross', num: 1, fmt: (r) => num(r.gross) }, { l: 'Days', num: 1, fmt: (r) => `${r.pay_days}/${r.month_days}` },
      { l: 'OT hrs', num: 1, fmt: (r) => mi(r, 'ot_hours') }, { l: 'OT', num: 1, fmt: (r) => num(r.ot_amount) }, { l: 'Bonus', num: 1, fmt: (r) => num(r.bonus) },
      { l: 'Additions', num: 1, fmt: (r) => mi(r, 'additions') }, { l: 'Late', num: 1, fmt: (r) => r.late_count || '' }, { l: 'LWP days', num: 1, fmt: (r) => r.lwp_days || '' },
      { l: 'PF', num: 1, fmt: (r) => num(r.pf) }, { l: 'Tax', num: 1, fmt: (r) => num(r.tax) }, { l: 'LWP ded.', num: 1, fmt: (r) => num(r.lwp_deduction) },
      { l: 'Loan', num: 1, fmt: (r) => num(r.loan_deduction) }, { l: 'Other ded.', num: 1, fmt: (r) => mi(r, 'other_deduction') },
      { l: 'Net pay', num: 1, fmt: (r) => `<b>${num(r.net)}</b>` },
      { l: '', fmt: (r) => r.id ? `<button class="btn sm ghost" data-act="pay:slip" data-id="${r.id}">Payslip</button>` : '' },
    ], d.items, {
      empty: 'No employees are payable this month', cls: 'compact',
      foot: (rows) => `<tr><td></td><td>Total</td>${['gross'].map((k) => `<td class="num">${num(t[k])}</td>`).join('')}<td></td><td class="num">${num(rows.reduce((s, r) => s + (r.ot_hours || 0), 0))}</td><td class="num">${num(t.ot_amount)}</td><td class="num">${num(t.bonus)}</td><td class="num">${num(rows.reduce((s, r) => s + (r.additions || 0), 0))}</td><td></td><td></td><td class="num">${num(t.pf)}</td><td class="num">${num(t.tax)}</td><td class="num">${num(t.lwp_deduction)}</td><td class="num">${num(t.loan_deduction)}</td><td class="num">${num(rows.reduce((s, r) => s + (r.other_deduction || 0), 0))}</td><td class="num">${num(t.net)}</td><td></td></tr>`,
    })}
    <p class="note">Rules (change them in Settings, under Payroll rules): basic, house rent and medical are percentages of gross; conveyance is the remainder. Overtime = basic ÷ 208 × multiplier per hour. LWP (absent days, half days, unpaid leave and every N late arrivals) = basic ÷ 30 per day. Loan installments are deducted automatically. Tax is a flat TDS estimate; set it to match NBR rules.</p></div>
    <div class="card"><h3>Payroll history</h3>${table([{ l: 'Month', fmt: (r) => `<a class="link" data-act="pay:goto" data-m="${r.month}">${monthName(r.month)}</a>` }, { l: 'Status', fmt: (r) => badge(r.status) },
      { l: 'Employees', num: 1, k: 'count' }, { l: 'Gross', num: 1, fmt: (r) => money(r.gross) }, { l: 'Deductions', num: 1, fmt: (r) => money(r.deductions) }, { l: 'Net', num: 1, fmt: (r) => money(r.net) },
      { l: 'Created by', k: 'created_by' }], runs.items, { empty: 'No payroll has been generated yet' })}</div>`;
}

const reload = () => render($('#main'), C);
on('pay:month', (el) => { S.month = addMonths(S.month, Number(el.dataset.d)); reload(); });
on('pay:pick', (el) => { if (el.value) { S.month = el.value; reload(); } });
on('pay:goto', (el) => { S.month = el.dataset.m; reload(); });
on('pay:gen', async () => {
  await api.post(`/api/payroll/runs/${S.month}/generate`, { include_bonus: $('#payBonus')?.checked || false });
  toast('Payroll calculated', 'ok');
  reload();
});
on('pay:adj', async (el) => { await api.put(`/api/payroll/payslips/${el.dataset.id}`, { [el.dataset.k]: el.value || 0 }); reload(); });
on('pay:step', async (el) => {
  const s = el.dataset.s;
  const msg = { finalize: ['Finalize payroll?', 'Figures will be locked, loan installments recorded and payslips released to employees.'],
    pay: ['Mark payroll as paid?', 'Confirm that salaries have been transferred to the bank.'], reopen: ['Reopen payroll?', 'Loan repayments from this run will be reversed and the payroll becomes editable again.'] }[s];
  if (!(await confirmBox(msg[0], msg[1], { okLabel: s === 'pay' ? 'Mark as paid' : s[0].toUpperCase() + s.slice(1) }))) return;
  await api.post(`/api/payroll/runs/${S.month}/${s}`);
  toast({ finalize: 'Payroll finalized', pay: 'Payroll marked as paid', reopen: 'Payroll reopened' }[s], 'ok');
  reload();
});
on('pay:delete', async () => {
  if (!(await confirmBox('Delete this draft?', 'Adjustments entered for this month will be lost.', { okLabel: 'Delete draft', danger: true }))) return;
  await api.del(`/api/payroll/runs/${S.month}`);
  reload();
});
on('pay:csv', (el) => api.download(`/api/payroll/runs/${S.month}/export`, { type: el.dataset.t }));
on('pay:slip', (el) => {
  const r = S.data.items.find((x) => x.id === Number(el.dataset.id));
  modal(`Payslip for ${r.emp_name}`, payslipHTML({ ...r, month: S.month }, C.user.company) + '<div class="toolbar" style="margin-top:12px;justify-content:flex-end"><button class="btn" data-act="pay:print1" data-id="' + r.id + '">' + ic('printer') + 'Print or save as PDF</button></div>', { size: 'wide' });
});
on('pay:print1', (el) => printSlips([{ ...S.data.items.find((x) => x.id === Number(el.dataset.id)), month: S.month }], C.user.company));
on('pay:printall', () => printSlips(S.data.items.map((r) => ({ ...r, month: S.month })), C.user.company));

/* ------------------------------------------------------------ payslip template (shared with My Workspace) */
export function payslipHTML(r, company) {
  const L = (rows) => rows.filter(([, v, always]) => always || v).map(([l, v]) => `<tr><td>${esc(l)}</td><td class="r">${num(v)}</td></tr>`).join('');
  return `<div class="slip"><div class="slip-h"><div><div class="co">${esc(company.name)}</div><div style="font-size:12px;color:#6b7684">Salary statement</div></div>
    <div style="text-align:right"><b>PAYSLIP</b><div style="font-size:12px;color:#6b7684">${monthName(r.month)}</div></div></div>
    <table class="kv"><tr><td>Employee</td><td><b>${esc(r.emp_name)}</b></td><td>Employee ID</td><td>${esc(r.emp_code)}</td></tr>
    <tr><td>Designation</td><td>${esc(r.designation || '')}</td><td>Department</td><td>${esc(r.department || '')}</td></tr>
    <tr><td>Bank</td><td>${esc(r.bank_name || '—')}</td><td>Account no.</td><td>${esc(r.bank_account || '—')}</td></tr>
    <tr><td>Paid days</td><td>${r.pay_days} of ${r.month_days}</td><td>LWP days</td><td>${r.lwp_days || 0}${r.late_count ? ` (late ${r.late_count}×)` : ''}</td></tr></table>
    <div class="cols"><table class="lines"><tr><th>Earnings</th><th class="r">BDT</th></tr>${L([['Basic salary', r.basic, 1], ['House rent allowance', r.house_rent, 1], ['Medical allowance', r.medical, 1], ['Conveyance allowance', r.conveyance, 1], [`Overtime (${r.ot_hours || 0} h)`, r.ot_amount], ['Festival bonus', r.bonus], ['Arrears / additions', r.additions]])}
      <tr class="t"><td>Total earnings</td><td class="r">${num(r.earnings)}</td></tr></table>
    <table class="lines"><tr><th>Deductions</th><th class="r">BDT</th></tr>${L([['Provident fund', r.pf, 1], ['Income tax (TDS)', r.tax, 1], ['Leave without pay', r.lwp_deduction], ['Loan / advance installment', r.loan_deduction], ['Other deductions', r.other_deduction]])}
      <tr class="t"><td>Total deductions</td><td class="r">${num(r.deductions)}</td></tr></table></div>
    <div class="net"><div><div style="font-size:12px;color:#6b7684">Net pay</div><div style="font-size:12.5px">Taka ${inWords(r.net)} only</div></div><b>৳ ${num(r.net)}</b></div>
    ${r.pf_employer ? `<div style="font-size:12px;color:#6b7684;margin-top:8px">Employer PF contribution this month: ৳ ${num(r.pf_employer)}</div>` : ''}
    <div class="sign"><span>Prepared by (HR)</span><span>Checked by (Accounts)</span><span>Authorised signatory</span></div>
    <div class="foot">This is a system-generated payslip from HR-MIS.</div></div>`;
}
export function printSlips(rows, company) { printHTML('Payslips', rows.map((r) => payslipHTML(r, company)).join('')); }
