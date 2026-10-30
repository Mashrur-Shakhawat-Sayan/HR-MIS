/** Expense claims — approval queue and payment tracking. */
import { api } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { $, badge, esc, fmtDate, kpi, money, on, plural, toast } from '../core/ui.js';

let C;
const CATS = ['Travel', 'Food', 'Fuel', 'Mobile Bill', 'Medical', 'Accommodation', 'Office Supplies', 'Training', 'Other'];

export async function render(main, ctx) {
  C = ctx;
  const all = (await api.get('/api/claims')).items;
  const sum = (st) => all.filter((c) => c.status === st).reduce((s, c) => s + c.amount, 0);
  const full = ctx.can('claims.view_all');
  await mountCrud(main, crudView({
    id: 'claims', endpoint: '/api/claims', title: full ? 'All expense claims' : 'Team expense claims', single: 'Claim', canManage: full,
    initialFilters: { status: 'Pending' },
    filters: [{ k: 'status', all: 'All statuses', o: ['Pending', 'Approved', 'Rejected', 'Paid'] }, { k: 'category', all: 'All categories', o: CATS }],
    fields: [{ k: 'emp_id', l: 'Employee', t: 'emp', req: 1, w: 2 }, { k: 'claim_date', l: 'Date', t: 'date', req: 1 }, { k: 'category', l: 'Category', t: 'select', o: CATS, req: 1 },
      { k: 'amount', l: 'Amount (৳)', t: 'number', req: 1, min: 1 }, { k: 'status', l: 'Status', t: 'select', o: ['Pending', 'Approved', 'Rejected', 'Paid'], req: 1, d: 'Pending' },
      { k: 'description', l: 'Description', t: 'textarea', w: 2 }],
    cols: [{ l: 'Date', fmt: (c) => `<span class="nowrap">${fmtDate(c.claim_date)}</span>` }, { l: 'Employee', fmt: (c) => `<b>${esc(c.full_name)}</b><br><small class="muted">${esc(c.code)}<i class="sep"></i>${esc(c.department || '')}</small>` },
      { l: 'Category', k: 'category' }, { l: 'Description', k: 'description' }, { l: 'Amount', num: 1, fmt: (c) => `<b>${money(c.amount)}</b>` },
      { l: 'Status', fmt: (c) => badge(c.status) + (c.decided_by ? `<br><small class="muted">${esc(c.decided_by)}</small>` : '') }],
    rowActions: (c) => c.emp_id === ctx.user.emp_id || !ctx.can('claims.approve') ? '' : c.status === 'Pending'
      ? `<button class="btn sm ok" data-act="clm:set" data-id="${c.id}" data-s="Approved">Approve</button> <button class="btn sm ghost" data-act="clm:set" data-id="${c.id}" data-s="Rejected">Reject</button> `
      : c.status === 'Approved' && full ? `<button class="btn sm ghost" data-act="clm:set" data-id="${c.id}" data-s="Paid">Mark paid</button> ` : '',
  }), `<div class="kpis">${kpi('Waiting for approval', money(sum('Pending')), plural(all.filter((c) => c.status === 'Pending').length, 'claim'), 'accent')}
    ${kpi('Approved, not yet paid', money(sum('Approved')), plural(all.filter((c) => c.status === 'Approved').length, 'claim'))}${kpi('Paid', money(sum('Paid')), 'reimbursed', 'info')}</div>`);
}
on('clm:set', async (el) => {
  await api.post(`/api/claims/${el.dataset.id}/decision`, { status: el.dataset.s });
  toast(`Claim ${el.dataset.s.toLowerCase()}`, 'ok');
  C.refreshNav();
  render($('#main'), C);
});
