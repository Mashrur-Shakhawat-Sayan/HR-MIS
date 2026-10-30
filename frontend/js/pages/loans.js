/** Loans & salary advances — issue, approve requests, track repayments. */
import { api } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { $, badge, esc, fmtDate, formHTML, ic, kpi, modal, money, monthName, on, plural, readForm, table, thisMonth, toast } from '../core/ui.js';

let C, V;

export async function render(main, ctx) {
  C = ctx;
  const all = (await api.get('/api/loans')).items;
  const act = all.filter((l) => l.status === 'Active');
  V = crudView({
    id: 'loans', endpoint: '/api/loans', title: 'Loans & advances', single: 'Loan', canManage: ctx.can('loans.manage'),
    filters: [{ k: 'status', all: 'All statuses', o: ['Pending', 'Active', 'Closed', 'Rejected'] }],
    fields: [{ k: 'emp_id', l: 'Employee', t: 'emp', req: 1, w: 2 }, { k: 'loan_type', l: 'Type', t: 'select', req: 1, o: ['Salary Advance', 'Personal Loan', 'House Building Loan', 'Vehicle Loan', 'Medical Loan', 'Other'] },
      { k: 'principal', l: 'Amount (৳)', t: 'number', req: 1, min: 1 }, { k: 'installment', l: 'Monthly installment (৳)', t: 'number', req: 1, min: 1 },
      { k: 'start_month', l: 'First deduction month', t: 'month', req: 1, d: thisMonth() }, { k: 'issued_on', l: 'Issued on', t: 'date' },
      { k: 'status', l: 'Status', t: 'select', o: ['Pending', 'Active', 'Closed', 'Rejected'], req: 1, d: 'Active' }, { k: 'purpose', l: 'Purpose', t: 'textarea', w: 2 }],
    cols: [{ l: 'Employee', fmt: (l) => `<a class="link" href="#/employees/${l.emp_id}"><b>${esc(l.full_name)}</b></a><br><small class="muted">${esc(l.code)}</small>` }, { l: 'Type', k: 'loan_type' },
      { l: 'Amount', num: 1, fmt: (l) => money(l.principal) }, { l: 'Installment', num: 1, fmt: (l) => money(l.installment) }, { l: 'From', fmt: (l) => monthName(l.start_month) },
      { l: 'Repaid', num: 1, fmt: (l) => money(l.repaid) }, { l: 'Outstanding', num: 1, fmt: (l) => `<b>${money(l.outstanding)}</b>` }, { l: 'Status', fmt: (l) => badge(l.status) }],
    rowActions: (l) => `<button class="ib" title="Repayment history" aria-label="Repayment history" data-act="loan:hist" data-id="${l.id}">${ic('history')}</button>${l.status === 'Pending' && ctx.can('loans.manage') ? `<button class="btn sm ok" data-act="loan:set" data-id="${l.id}" data-s="Active">Approve</button> <button class="btn sm ghost" data-act="loan:set" data-id="${l.id}" data-s="Rejected">Reject</button>` : ''}`,
  });
  await mountCrud(main, V, `<div class="kpis">${kpi('Active loans', act.length, `${plural(all.filter((l) => l.status === 'Pending').length, 'request')} pending`, 'accent')}
    ${kpi('Outstanding', money(act.reduce((s, l) => s + l.outstanding, 0)), 'to be recovered through payroll')}${kpi('Monthly recovery', money(act.reduce((s, l) => s + Math.min(l.installment, l.outstanding), 0)), 'deducted each payroll', 'info')}</div>`,
  '<p class="note">Installments are deducted automatically when payroll is generated and recorded as repayments when payroll is finalized. A loan closes itself when it is fully repaid.</p>');
}

on('loan:set', async (el) => { await api.put(`/api/loans/${el.dataset.id}`, { status: el.dataset.s }); toast(`Loan ${el.dataset.s === 'Active' ? 'approved' : 'rejected'}`, 'ok'); render($('#main'), C); });
on('loan:hist', async (el) => {
  const { items } = await api.get(`/api/loans/${el.dataset.id}/repayments`);
  modal('Repayment history', table([{ l: 'Month', fmt: (r) => monthName(r.month) }, { l: 'Amount', num: 1, fmt: (r) => money(r.amount) }, { l: 'Note', k: 'note' }], items, { empty: 'No repayments yet' }) +
    (C.can('loans.manage') ? `<div class="toolbar" style="margin-top:12px"><span class="grow"></span><button class="btn ghost" data-act="loan:pay" data-id="${el.dataset.id}">${ic('plus')}Record a manual repayment</button></div>` : ''));
});
on('loan:pay', async (el) => {
  const f = [{ k: 'month', l: 'Month', t: 'month', req: 1, d: thisMonth() }, { k: 'amount', l: 'Amount (৳)', t: 'number', req: 1, min: 1 }, { k: 'note', l: 'Note', w: 2, d: 'Cash repayment' }];
  modal('Manual repayment', await formHTML(f), { onSave: async () => { const d = readForm(f, $('#modal')); if (!d) return false; await api.post(`/api/loans/${el.dataset.id}/repayments`, d); toast('Repayment recorded', 'ok'); render($('#main'), C); } });
});
void fmtDate;
