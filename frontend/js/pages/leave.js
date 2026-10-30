/** Leave — approvals, balances, who's away, leave types and opening balances. */
import { api, lookups } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { $, addMonths, badge, confirmBox, esc, fmtDate, fmtShort, formHTML, ic, modal, monthName, num, on, plural, readForm, table, tabs, thisMonth, toast } from '../core/ui.js';
import { applyLeaveModal } from './me.js';

let C;
const S = { tab: 'requests', status: 'Pending', year: new Date().getFullYear(), month: thisMonth() };

export async function render(main, ctx) {
  C = ctx;
  const T = [['requests', 'Requests'], ['calendar', "Who's away"]];
  if (ctx.can('leave.view_all')) T.splice(1, 0, ['balances', 'Balances']);
  if (ctx.can('leave.manage')) T.push(['types', 'Leave types & policy'], ['adjust', 'Opening balances / carry forward']);
  main.innerHTML = `${tabs('lv:tab', T, S.tab)}<div id="lvBody" style="margin-top:16px"></div>`;
  const body = $('#lvBody');
  if (S.tab === 'requests') return requests(body);
  if (S.tab === 'balances') return balances(body);
  if (S.tab === 'calendar') return calendar(body);
  if (S.tab === 'types') return mountCrud(body, typesView(), '<div class="banner info" style="margin-bottom:12px">Defaults follow the Bangladesh Labour Act 2006: casual 10, sick 14, maternity 16 weeks (112 days). Earned leave and paternity are company policy — adjust as needed.</div>');
  if (S.tab === 'adjust') return adjustments(body);
}
on('lv:tab', (el) => { S.tab = el.dataset.tab; render($('#main'), C); });

async function requests(body) {
  const { items } = await api.get('/api/leave/requests', { status: S.status === 'All' ? '' : S.status });
  body.innerHTML = `<div class="card"><div class="card-head"><select data-change="lv:status">${['Pending', 'Approved', 'Rejected', 'Cancelled', 'All'].map((s) => `<option ${s === S.status ? 'selected' : ''}>${s}</option>`).join('')}</select>
      <span class="muted">${plural(items.length, 'request')}</span><span class="grow"></span><button class="btn ghost" data-act="lv:csv">${ic('download')}Leave register</button>
      ${C.can('leave.manage') ? `<button class="btn" data-act="lv:apply">${ic('plus')}Apply for an employee</button>` : ''}</div>
    ${table([{ l: 'Employee', fmt: (r) => `<a class="link" href="#/employees/${r.emp_id}"><b>${esc(r.full_name)}</b></a><br><small class="muted">${esc(r.code)}<i class="sep"></i>${esc(r.department || '')}</small>` },
      { l: 'Type', fmt: (r) => `${esc(r.leave_type)}${r.paid ? '' : ' <span class="badge mute">unpaid</span>'}` }, { l: 'Dates', fmt: (r) => `<span class="nowrap">${fmtShort(r.from_date)}${r.to_date !== r.from_date ? ' – ' + fmtDate(r.to_date) : ' ' + r.from_date.slice(0, 4)}</span>` },
      { l: 'Days', num: 1, fmt: (r) => num(r.days, 1) }, { l: 'Reason', k: 'reason' }, { l: 'Applied', fmt: (r) => `<small class="muted">${fmtDate(r.applied_at)}<br>by ${esc(r.applied_by || '')}</small>` },
      { l: 'Status', fmt: (r) => badge(r.status) + (r.decided_by ? `<br><small class="muted">${esc(r.decided_by)}</small>` : '') },
      { l: '', cls: 'r nowrap', fmt: (r) => `${r.can_decide ? `<button class="btn sm ok" data-act="lv:decide" data-id="${r.id}" data-d="Approved">Approve</button> <button class="btn sm ghost" data-act="lv:decide" data-id="${r.id}" data-d="Rejected">Reject</button>` : ''}
        ${C.can('leave.manage') && ['Pending', 'Approved'].includes(r.status) ? `<button class="ib danger" title="Cancel leave" aria-label="Cancel leave" data-act="lv:cancel" data-id="${r.id}">${ic('undo')}</button>` : ''}` }],
    items, { empty: S.status === 'Pending' ? 'No leave requests waiting for a decision' : 'No leave requests' })}</div>`;
}
on('lv:status', (el) => { S.status = el.value; requests($('#lvBody')); });
on('lv:csv', () => api.download('/api/reports/leave-register', { format: 'csv', year: S.year }));
on('lv:apply', () => applyLeaveModal(null, () => requests($('#lvBody')), true));
on('lv:decide', async (el) => {
  const decision = el.dataset.d;
  if (decision === 'Rejected') {
    modal('Reject leave', '<label class="fld"><span>Reason (shown to the employee)</span><textarea id="rejWhy" rows="3"></textarea></label>', {
      saveLabel: 'Reject', danger: true, size: 'narrow',
      onSave: async () => { await api.post(`/api/leave/requests/${el.dataset.id}/decision`, { decision, remarks: $('#rejWhy').value }); toast('Leave rejected'); C.refreshNav(); requests($('#lvBody')); },
    });
    return;
  }
  await api.post(`/api/leave/requests/${el.dataset.id}/decision`, { decision });
  toast('Leave approved', 'ok');
  C.refreshNav();
  requests($('#lvBody'));
});
on('lv:cancel', async (el) => {
  if (!(await confirmBox('Cancel this leave?', 'Approved days are removed from attendance.', { okLabel: 'Cancel leave', danger: true }))) return;
  await api.post(`/api/leave/requests/${el.dataset.id}/cancel`);
  requests($('#lvBody'));
});

async function balances(body) {
  const d = await api.get('/api/leave/balances', { year: S.year });
  const types = d.types.filter((t) => t.days_per_year > 0);
  body.innerHTML = `<div class="card"><div class="card-head"><select data-change="lv:year">${[S.year - 1, S.year, S.year + 1].map((y) => `<option ${y === S.year ? 'selected' : ''}>${y}</option>`).join('')}</select>
      <span class="muted">remaining / entitled days</span><span class="grow"></span><button class="btn ghost" data-act="lv:balcsv">${ic('download')}Export</button></div>
    ${table([{ l: 'Employee', fmt: (e) => `<b>${esc(e.full_name)}</b><br><small class="muted">${esc(e.code)}<i class="sep"></i>${esc(e.department || '')}</small>` },
      ...types.map((t) => ({ l: t.name, cls: 'c', fmt: (e) => { const b = e.balances.find((x) => x.leave_type_id === t.id); if (!b) return '<span class="muted">—</span>'; const c = b.remaining <= 0 ? 'var(--bad)' : b.remaining <= 2 ? 'var(--warn)' : 'inherit'; return `<b style="color:${c}">${num(b.remaining, 1)}</b><span class="muted"> / ${num(b.entitled, 1)}</span>`; } })),
      { l: 'Unpaid taken', cls: 'c', fmt: (e) => num(e.balances.find((x) => x.leave_type === 'Unpaid')?.used || 0, 1) }], d.items)}</div>`;
}
on('lv:year', (el) => { S.year = Number(el.value); balances($('#lvBody')); });
on('lv:balcsv', () => api.download('/api/reports/leave-balance', { format: 'csv', year: S.year }));

async function calendar(body) {
  const { items } = await api.get('/api/leave/calendar', { month: S.month });
  body.innerHTML = `<div class="card"><div class="card-head"><button class="ib" title="Previous" aria-label="Previous" data-act="lv:mon" data-d="-1">${ic('chev-left')}</button><b>${monthName(S.month)}</b><button class="ib" title="Next" aria-label="Next" data-act="lv:mon" data-d="1">${ic('chev-right')}</button></div>
    ${table([{ l: 'Employee', fmt: (r) => `<b>${esc(r.full_name)}</b><br><small class="muted">${esc(r.department || '')}</small>` }, { l: 'Leave', k: 'leave_type' },
      { l: 'From', fmt: (r) => fmtDate(r.from_date) }, { l: 'To', fmt: (r) => fmtDate(r.to_date) }, { l: 'Days', num: 1, fmt: (r) => num(r.days, 1) }], items, { empty: 'Nobody is on approved leave this month' })}</div>`;
}
on('lv:mon', (el) => { S.month = addMonths(S.month, Number(el.dataset.d)); calendar($('#lvBody')); });

function typesView() {
  return crudView({
    id: 'leavetypes', endpoint: '/api/leave-types', title: 'Leave types', single: 'Leave type', canManage: true,
    fields: [{ k: 'name', l: 'Name', req: 1 }, { k: 'days_per_year', l: 'Days per year', t: 'number', req: 1, min: 0, hint: '0 = no fixed entitlement (e.g. unpaid)' },
      { k: 'gender', l: 'Available to', t: 'select', o: ['Any', 'Female', 'Male'], req: 1, d: 'Any' }, { k: 'paid', l: 'Paid', t: 'checkbox', cl: 'Paid leave', d: 1 },
      { k: 'calendar_days', l: 'Counting', t: 'checkbox', cl: 'Count calendar days (e.g. maternity)' }, { k: 'carry_forward', l: 'Carry forward', t: 'checkbox', cl: 'Unused days carry forward' },
      { k: 'max_carry', l: 'Max carry forward days', t: 'number', min: 0 }, { k: 'active', l: 'Status', t: 'checkbox', cl: 'Active', d: 1 }, { k: 'color', l: 'Colour', t: 'color', d: '#12866e' }],
    cols: [{ l: 'Leave type', fmt: (t) => `<span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${esc(t.color || '#999')};margin-right:6px"></span><b>${esc(t.name)}</b>` },
      { l: 'Days / year', num: 1, fmt: (t) => t.days_per_year || '—' }, { l: 'For', k: 'gender' }, { l: 'Paid', fmt: (t) => (t.paid ? 'Yes' : 'No') },
      { l: 'Counting', fmt: (t) => (t.calendar_days ? 'Calendar days' : 'Working days') }, { l: 'Carry forward', fmt: (t) => (t.carry_forward ? `Yes (max ${t.max_carry})` : 'No') }, { l: 'Status', fmt: (t) => badge(t.active ? 'Active' : 'Closed') }],
  });
}

async function adjustments(body) {
  const { items } = await api.get('/api/leave/adjustments');
  body.innerHTML = `<div class="card"><div class="card-head"><h3>Opening balances, carry forward and corrections</h3><span class="grow"></span><button class="btn" data-act="lv:adj">${ic('plus')}Add adjustment</button></div>
    <p class="muted" style="margin-top:-6px">Positive days add to the entitlement for that year (e.g. earned leave carried forward); negative days reduce it (e.g. encashment).</p>
    ${table([{ l: 'Year', k: 'year' }, { l: 'Employee', fmt: (a) => `${esc(a.full_name)} <small class="muted">${esc(a.code)}</small>` }, { l: 'Leave type', k: 'leave_type' },
      { l: 'Days', num: 1, fmt: (a) => (a.days > 0 ? '+' : '') + num(a.days, 1) }, { l: 'Note', k: 'note' }, { l: 'By', k: 'created_by' },
      { l: '', cls: 'r', fmt: (a) => `<button class="ib danger" title="Delete" aria-label="Delete" data-act="lv:deladj" data-id="${a.id}">${ic('trash')}</button>` }], items, { empty: 'No adjustments' })}</div>`;
}
on('lv:adj', async () => {
  const f = [{ k: 'emp_id', l: 'Employee', t: 'emp', req: 1, w: 2 }, { k: 'leave_type_id', l: 'Leave type', t: 'leave', req: 1 }, { k: 'year', l: 'Year', t: 'number', req: 1, d: S.year },
    { k: 'days', l: 'Days (+/−)', t: 'number', req: 1 }, { k: 'note', l: 'Note', ph: 'e.g. Carry forward from 2025' }];
  modal('Leave adjustment', await formHTML(f), { onSave: async () => { const d = readForm(f, $('#modal')); if (!d) return false; await api.post('/api/leave/adjustments', d); toast('Saved', 'ok'); adjustments($('#lvBody')); } });
});
on('lv:deladj', async (el) => { await api.del(`/api/leave/adjustments/${el.dataset.id}`); adjustments($('#lvBody')); });
void lookups;
