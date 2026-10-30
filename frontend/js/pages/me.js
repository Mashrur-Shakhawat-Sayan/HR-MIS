/** My Workspace — employee self-service: profile, attendance, leave, payslips, loans, claims. */
import { api, lookups } from '../core/api.js';
import { $, addMonths, badge, confirmBox, esc, fmtDate, formHTML, ic, kpi, modal, money, monthName, num, on, parseDate, plural, readForm, table, thisMonth, toast } from '../core/ui.js';
import { payslipHTML, printSlips } from './payroll.js';

let C;
const S = { month: thisMonth() };

export async function render(main, ctx) {
  C = ctx;
  const page = ctx.segs[1];
  if (page === 'profile') return profile(main);
  if (page === 'attendance') return attendance(main);
  if (page === 'leave') return leave(main);
  if (page === 'pay') return pay(main);
  if (page === 'claims') return claims(main);
}

/* ------------------------------------------------------------ profile */
const EDITABLE = [{ k: 'phone', l: 'Mobile' }, { k: 'email', l: 'Personal email', t: 'email' },
  { k: 'marital_status', l: 'Marital status', t: 'select', o: ['Single', 'Married', 'Divorced', 'Widowed'] },
  { k: 'blood_group', l: 'Blood group', t: 'select', o: ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'] },
  { k: 'present_address', l: 'Present address', t: 'textarea', rows: 2 }, { k: 'permanent_address', l: 'Permanent address', t: 'textarea', rows: 2 },
  { k: 'emergency_name', l: 'Emergency contact (name / relation)' }, { k: 'emergency_phone', l: 'Emergency phone' }];

async function profile(main) {
  const e = await api.get('/api/me/profile');
  const kv = (l, v) => `<div><small>${l}</small>${v || '<span class="muted">—</span>'}</div>`;
  main.innerHTML = `<div class="card"><div class="prof-head"><span class="av lg" style="background:var(--brand)">${esc(e.full_name.split(' ').map((w) => w[0]).slice(0, 2).join(''))}</span>
      <div class="grow"><h2>${esc(e.full_name)}</h2><div class="muted">${esc(e.designation || '')}<i class="sep"></i>${esc(e.department || '')}<i class="sep"></i>${esc(e.unit_name || '')}</div>
      <div class="chips" style="margin-top:8px">${badge(e.status)}<span class="chip">${esc(e.code)}</span><span class="chip">${esc(e.emp_type)}</span>${e.manager_name ? `<span class="chip">Reports to ${esc(e.manager_name)}</span>` : ''}</div></div>
      <button class="btn" data-act="me:edit">${ic('pencil')}Update my details</button></div></div>
    <div class="grid2e"><div class="card"><h3>Personal & contact</h3><div class="dl">${kv('Mobile', esc(e.phone))}${kv('Email', esc(e.email))}${kv('Date of birth', fmtDate(e.dob))}
      ${kv('Blood group', esc(e.blood_group))}${kv('Marital status', esc(e.marital_status))}${kv('Emergency contact', `${esc(e.emergency_name || '')} ${esc(e.emergency_phone || '')}`)}
      ${kv('Present address', esc(e.present_address))}${kv('Permanent address', esc(e.permanent_address))}</div></div>
    <div class="card"><h3>Employment</h3><div class="dl">${kv('Joining date', fmtDate(e.join_date))}${kv('Grade', esc(e.grade))}${kv('Bank', esc(e.bank_name))}${kv('Account', esc(e.bank_account))}
      ${kv('Gross salary', money(e.gross_salary))}${kv('Provident fund', e.pf_member ? 'Member' : 'Not a member')}</div>
      ${e.assets.length ? `<div class="sec">Company assets with me</div><div class="chips">${e.assets.map((a) => `<span class="chip">${ic('laptop', 14)}${esc(a.tag)}, ${esc(a.name)}</span>`).join('')}</div>` : ''}</div></div>
    ${e.events.length ? `<div class="card"><h3>My career history</h3>${table([{ l: 'Date', fmt: (v) => fmtDate(v.effective_date) }, { l: 'Event', fmt: (v) => badge(v.event_type) }, { l: 'From', k: 'old_value' }, { l: 'To', k: 'new_value' }], e.events)}</div>` : ''}
    ${e.documents.length ? `<div class="card"><h3>My documents</h3>${table([{ l: 'Title', k: 'title' }, { l: 'Type', k: 'doc_type' }, { l: 'Uploaded', fmt: (d) => fmtDate(d.uploaded_at) }, { l: '', cls: 'r', fmt: (d) => `<button class="btn sm ghost" data-act="me:doc" data-id="${d.id}">${ic('download')}Download</button>` }], e.documents)}</div>` : ''}`;
  S.profile = e;
}
on('me:doc', (el) => api.download(`/api/documents/${el.dataset.id}/download`));
on('me:edit', async () => {
  modal('Update my details', await formHTML(EDITABLE, S.profile), {
    onSave: async () => { const d = readForm(EDITABLE, $('#modal')); if (!d) return false; await api.put('/api/me/profile', d); toast('Details updated', 'ok'); profile($('#main')); },
  });
});

/* ------------------------------------------------------------ attendance */
const STATUS = { P: 'Present', L: 'Late', HD: 'Half day', A: 'Absent', LV: 'On leave', WFH: 'Work from home', OD: 'On duty' };
async function attendance(main) {
  const d = await api.get('/api/attendance/my', { month: S.month });
  const t = d.today;
  main.innerHTML = `<div class="card"><div class="clock"><div><small class="muted">Today</small><div class="time">${new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}</div></div>
      <div class="grow">${t ? `${badge(STATUS[t.status] || t.status)}<span class="muted" style="margin-left:10px">In <b>${t.check_in || '—'}</b><i class="sep"></i>Out <b>${t.check_out || '—'}</b></span>` : d.is_workday ? 'You have not checked in yet today.' : 'Today is not a working day.'}</div>
      ${!t || !t.check_in ? `<button class="btn" data-act="me:clock" data-a="in">${ic('login')}Check in</button>` : !t.check_out ? `<button class="btn ghost" data-act="me:clock" data-a="out">${ic('logout')}Check out</button>` : ''}</div></div>
    <div class="toolbar card"><span class="stepper"><button class="ib" title="Previous month" aria-label="Previous month" data-act="me:month" data-d="-1">${ic('chev-left')}</button><b>${monthName(S.month)}</b><button class="ib" title="Next month" aria-label="Next month" data-act="me:month" data-d="1">${ic('chev-right')}</button></span><span class="grow"></span>
      <div class="chips">${['P', 'L', 'HD', 'A', 'LV', 'WFH'].map((k) => `<span class="chip"><span class="s-${k}">${STATUS[k]}</span> <b>${d.totals[k] || 0}</b></span>`).join('')}<span class="chip">Attendance <b>${d.totals.pct || 0}%</b></span></div></div>
    <div class="card">${table([{ l: 'Date', fmt: (r) => fmtDate(r.date) }, { l: 'Day', fmt: (r) => parseDate(r.date).toLocaleDateString('en-GB', { weekday: 'long' }) },
      { l: 'Status', fmt: (r) => `<span class="s-${r.status}"><b>${esc(STATUS[r.status] || r.status)}</b></span>` }, { l: 'Check-in', k: 'check_in' }, { l: 'Check-out', k: 'check_out' }, { l: 'Note', k: 'note' }],
      d.rows, { empty: 'No attendance recorded for this month' })}</div>`;
}
on('me:month', (el) => { S.month = addMonths(S.month, Number(el.dataset.d)); attendance($('#main')); });
on('me:clock', async (el) => { const r = await api.post('/api/attendance/clock', { action: el.dataset.a }); toast(`${el.dataset.a === 'in' ? 'Checked in' : 'Checked out'} at ${r.time}`, 'ok'); attendance($('#main')); });

/* ------------------------------------------------------------ leave */
async function leave(main) {
  const year = new Date().getFullYear();
  const [bal, reqs] = await Promise.all([api.get('/api/leave/balances', { year, emp_id: C.user.emp_id }), api.get('/api/leave/requests', { mine: 1 })]);
  main.innerHTML = `<div class="kpis">${bal.items.filter((b) => b.remaining !== null).map((b) => kpi(`${b.leave_type} leave left`, `${num(b.remaining, 1)}<small> of ${num(b.entitled, 1)}</small>`, `${num(b.used, 1)} taken, ${num(b.pending, 1)} pending`)).join('')}</div>
    <div class="card"><div class="card-head"><h3>My leave requests</h3><span class="grow"></span><button class="btn" data-act="me:apply">${ic('plus')}Apply for leave</button></div>
    ${table([{ l: 'Type', k: 'leave_type' }, { l: 'From', fmt: (r) => fmtDate(r.from_date) }, { l: 'To', fmt: (r) => fmtDate(r.to_date) }, { l: 'Days', num: 1, fmt: (r) => num(r.days, 1) },
      { l: 'Reason', k: 'reason' }, { l: 'Status', fmt: (r) => badge(r.status) }, { l: 'Decided by', fmt: (r) => esc(r.decided_by || '') + (r.remarks ? `<br><small class="muted">${esc(r.remarks)}</small>` : '') },
      { l: '', cls: 'r', fmt: (r) => ['Pending', 'Approved'].includes(r.status) && r.from_date > new Date().toISOString().slice(0, 10) || r.status === 'Pending' ? `<button class="btn sm ghost" data-act="me:cancel" data-id="${r.id}">Cancel</button>` : '' }],
    reqs.items, { empty: 'You have not applied for any leave yet' })}</div>`;
}
export async function applyLeaveModal(empId, after, onBehalf = false) {
  const f = [...(onBehalf ? [{ k: 'emp_id', l: 'Employee', t: 'emp', req: 1, w: 2 }] : []), { k: 'leave_type_id', l: 'Leave type', t: 'leave', req: 1 },
    { k: 'half_day', l: 'Duration', t: 'checkbox', cl: 'Half day only' }, { k: 'from_date', l: 'From', t: 'date', req: 1, d: new Date().toISOString().slice(0, 10) },
    { k: 'to_date', l: 'To', t: 'date', req: 1, d: new Date().toISOString().slice(0, 10) }, { k: 'reason', l: 'Reason', t: 'textarea', w: 2 }];
  if (onBehalf) f.push({ k: 'approve', l: 'Approval', t: 'checkbox', cl: 'Approve immediately (HR)' });
  modal(onBehalf ? 'Apply leave for an employee' : 'Apply for leave', await formHTML(f) + '<div class="banner info" id="lvInfo" style="margin-top:12px">Choose a leave type and dates.</div>', {
    saveLabel: 'Submit request',
    onSave: async () => { const d = readForm(f, $('#modal')); if (!d) return false; await api.post('/api/leave/requests', { ...d, emp_id: d.emp_id || empId }); toast('Leave request submitted', 'ok'); after(); },
  });
  const upd = async () => {
    const lt = $('#f_leave_type_id').value, from = $('#f_from_date').value, to = $('#f_to_date').value, emp = onBehalf ? $('#f_emp_id').value : empId;
    if (!lt || !from || !to || !emp) return;
    try {
      const p = await api.get('/api/leave/preview', { leave_type_id: lt, from_date: from, to_date: to, emp_id: emp, half_day: $('#f_half_day').checked ? 1 : '' });
      const b = p.balance;
      $('#lvInfo').innerHTML = `<b>${p.days}</b> ${p.calendar_days ? 'calendar' : 'working'} ${+p.days === 1 ? 'day' : 'days'}` + (b && b.remaining !== null ? `<i class="sep"></i>balance <b>${num(b.remaining - b.pending, 1)}</b> of ${num(b.entitled, 1)} available` : '');
    } catch (e) { $('#lvInfo').textContent = e.message; }
  };
  ['leave_type_id', 'from_date', 'to_date', 'half_day', 'emp_id'].forEach((k) => $('#f_' + k)?.addEventListener('change', () => {
    if (k === 'from_date' && $('#f_to_date').value < $('#f_from_date').value) $('#f_to_date').value = $('#f_from_date').value;
    upd();
  }));
}
on('me:apply', () => applyLeaveModal(C.user.emp_id, () => leave($('#main'))));
on('me:cancel', async (el) => {
  if (!(await confirmBox('Cancel this leave request?', 'Approved leave will be removed from your attendance.', { okLabel: 'Cancel leave', danger: true }))) return;
  await api.post(`/api/leave/requests/${el.dataset.id}/cancel`);
  toast('Leave cancelled');
  leave($('#main'));
});

/* ------------------------------------------------------------ payslips & loans */
async function pay(main) {
  const [slips, loans] = await Promise.all([api.get('/api/payroll/my'), api.get('/api/loans/my')]);
  S.slips = slips.items;
  main.innerHTML = `<div class="card"><div class="card-head"><h3>My payslips</h3></div>
    ${table([{ l: 'Month', fmt: (s) => `<b>${monthName(s.month)}</b>` }, { l: 'Gross', num: 1, fmt: (s) => money(s.gross) }, { l: 'Earnings', num: 1, fmt: (s) => money(s.earnings) },
      { l: 'Deductions', num: 1, fmt: (s) => money(s.deductions) }, { l: 'Net pay', num: 1, fmt: (s) => `<b>${money(s.net)}</b>` }, { l: 'Status', fmt: (s) => badge(s.run_status) },
      { l: '', cls: 'r nowrap', fmt: (s) => `<button class="btn sm ghost" data-act="me:slip" data-id="${s.id}">View</button> <button class="btn sm ghost" data-act="me:print" data-id="${s.id}">${ic('printer')}Print</button>` }],
    slips.items, { empty: 'No payslips yet', emptyHint: ' Payslips appear here once payroll is finalized.' })}</div>
    <div class="card"><div class="card-head"><h3>My loans & salary advances</h3><span class="grow"></span><button class="btn ghost" data-act="me:loan">${ic('plus')}Request an advance or loan</button></div>
    ${table([{ l: 'Type', k: 'loan_type' }, { l: 'Amount', num: 1, fmt: (l) => money(l.principal) }, { l: 'Installment', num: 1, fmt: (l) => money(l.installment) },
      { l: 'From', fmt: (l) => monthName(l.start_month) }, { l: 'Repaid', num: 1, fmt: (l) => money(l.repaid) }, { l: 'Outstanding', num: 1, fmt: (l) => money(l.outstanding) }, { l: 'Status', fmt: (l) => badge(l.status) }],
    loans.items, { empty: 'No loans or advances' })}</div>`;
}
on('me:slip', (el) => { const s = S.slips.find((x) => x.id === Number(el.dataset.id)); modal(`Payslip — ${monthName(s.month)}`, payslipHTML(s, C.user.company), { size: 'wide' }); });
on('me:print', (el) => printSlips([S.slips.find((x) => x.id === Number(el.dataset.id))], C.user.company));
on('me:loan', async () => {
  const f = [{ k: 'loan_type', l: 'Type', t: 'select', o: ['Salary Advance', 'Personal Loan', 'Medical Loan', 'House Building Loan', 'Vehicle Loan', 'Other'], req: 1 },
    { k: 'principal', l: 'Amount (৳)', t: 'number', req: 1, min: 1 }, { k: 'installment', l: 'Monthly installment (৳)', t: 'number', req: 1, min: 1 },
    { k: 'start_month', l: 'First deduction month', t: 'month', req: 1, d: addMonths(thisMonth(), 1) }, { k: 'purpose', l: 'Purpose', t: 'textarea', w: 2 }];
  modal('Request a loan / salary advance', await formHTML(f), { saveLabel: 'Submit request', onSave: async () => { const d = readForm(f, $('#modal')); if (!d) return false; await api.post('/api/loans/request', d); toast('Request sent to payroll', 'ok'); pay($('#main')); } });
});

/* ------------------------------------------------------------ claims */
const CLAIM_F = [{ k: 'claim_date', l: 'Date of expense', t: 'date', req: 1, d: new Date().toISOString().slice(0, 10) },
  { k: 'category', l: 'Category', t: 'select', o: ['Travel', 'Food', 'Fuel', 'Mobile Bill', 'Medical', 'Accommodation', 'Office Supplies', 'Training', 'Other'], req: 1 },
  { k: 'amount', l: 'Amount (৳)', t: 'number', req: 1, min: 1 }, { k: 'description', l: 'Description', t: 'textarea', w: 2 }];
async function claims(main) {
  const r = await api.get('/api/claims', { emp_id: C.user.emp_id });
  const mine = r.items.filter((c) => c.emp_id === C.user.emp_id);
  S.claims = mine;
  const sum = (st) => mine.filter((c) => c.status === st).reduce((s, c) => s + c.amount, 0);
  main.innerHTML = `<div class="kpis">${kpi('Pending', money(sum('Pending')), 'awaiting approval', 'accent')}${kpi('Approved', money(sum('Approved')), 'to be paid with salary or by accounts')}${kpi('Paid', money(sum('Paid')), 'reimbursed', 'info')}</div>
    <div class="card"><div class="card-head"><h3>My expense claims</h3><span class="grow"></span><button class="btn" data-act="me:claim">${ic('plus')}New claim</button></div>
    ${table([{ l: 'Date', fmt: (c) => fmtDate(c.claim_date) }, { l: 'Category', k: 'category' }, { l: 'Description', k: 'description' }, { l: 'Amount', num: 1, fmt: (c) => money(c.amount) }, { l: 'Status', fmt: (c) => badge(c.status) },
      { l: '', cls: 'r nowrap', fmt: (c) => c.status === 'Pending' ? `<button class="ib" title="Edit" aria-label="Edit" data-act="me:claim" data-id="${c.id}">${ic('pencil')}</button><button class="ib danger" title="Delete" aria-label="Delete" data-act="me:delclaim" data-id="${c.id}">${ic('trash')}</button>` : '' }],
    mine, { empty: 'No claims yet' })}</div>`;
}
on('me:claim', async (el) => {
  const id = el.dataset.id ? Number(el.dataset.id) : null;
  modal(id ? 'Edit claim' : 'New expense claim', await formHTML(CLAIM_F, id ? S.claims.find((c) => c.id === id) : {}), {
    saveLabel: id ? 'Save' : 'Submit claim',
    onSave: async () => { const d = readForm(CLAIM_F, $('#modal')); if (!d) return false; if (id) await api.put(`/api/claims/${id}`, d); else await api.post('/api/claims', d); toast('Claim saved', 'ok'); claims($('#main')); },
  });
});
on('me:delclaim', async (el) => { if (!(await confirmBox('Delete claim?', 'This cannot be undone.', { okLabel: 'Delete', danger: true }))) return; await api.del(`/api/claims/${el.dataset.id}`); claims($('#main')); });
