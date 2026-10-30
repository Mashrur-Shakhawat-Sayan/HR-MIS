/** Lifecycle — career events, onboarding/offboarding checklists, confirmations due, disciplinary register. */
import { api } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { $, badge, esc, fmtDate, on, table, tabs } from '../core/ui.js';

let C;
const S = { tab: 'events', type: '' };

export async function render(main, ctx) {
  C = ctx;
  main.innerHTML = `${tabs('lc:tab', [['events', 'Career events'], ['tasks', 'Onboarding & offboarding'], ['confirm', 'Confirmations due'], ['disc', 'Disciplinary']], S.tab)}<div id="lcBody" style="margin-top:16px"></div>`;
  const body = $('#lcBody');
  if (S.tab === 'events') {
    const { items } = await api.get('/api/lifecycle/events', { type: S.type });
    body.innerHTML = `<div class="card"><div class="card-head"><select data-change="lc:type"><option value="">All events</option>${['Joining', 'Confirmation', 'Promotion', 'Transfer', 'Increment', 'Resignation', 'Termination', 'Retirement', 'Re-hire'].map((t) => `<option ${t === S.type ? 'selected' : ''}>${t}</option>`).join('')}</select>
      <span class="grow"></span><span class="muted">Record a promotion, transfer, increment or exit from the employee's profile.</span></div>
      ${table([{ l: 'Date', fmt: (v) => `<span class="nowrap">${fmtDate(v.effective_date)}</span>` }, { l: 'Employee', fmt: (v) => `<a class="link" href="#/employees/${v.emp_id}"><b>${esc(v.full_name)}</b></a><br><small class="muted">${esc(v.code)}</small>` },
        { l: 'Event', fmt: (v) => badge(v.event_type) }, { l: 'From', k: 'old_value' }, { l: 'To', k: 'new_value' }, { l: 'Details', k: 'details' }, { l: 'By', k: 'created_by' }], items, { empty: 'No events' })}</div>`;
  } else if (S.tab === 'tasks') {
    const { items } = await api.get('/api/lifecycle/tasks', { open: 1 });
    const by = {};
    items.forEach((t) => (by[`${t.category} — ${t.full_name} (${t.code})`] ||= { emp: t.emp_id, list: [] }).list.push(t));
    body.innerHTML = `<div class="card"><h3>Open checklist items (${items.length})</h3>${Object.entries(by).map(([k, g]) => `<div class="sec"><a class="link" href="#/employees/${g.emp}">${esc(k)}</a></div>
      ${g.list.map((t) => `<div class="task"><input type="checkbox" ${C.can('lifecycle.manage') ? '' : 'disabled'} data-change="lc:tick" data-id="${t.id}"><span class="grow">${esc(t.task)}</span><small class="muted">${esc(t.owner || '')}</small><small class="muted">${fmtDate(t.due_date)}</small></div>`).join('')}`).join('') || '<div class="empty"><b>All checklists complete</b>New joiners and leavers get a checklist automatically.</div>'}</div>`;
  } else if (S.tab === 'confirm') {
    const { items } = await api.get('/api/lifecycle/confirmations-due');
    body.innerHTML = `<div class="card"><h3>Probation ending within 30 days</h3>${table([{ l: 'Employee', fmt: (e) => `<a class="link" href="#/employees/${e.id}"><b>${esc(e.full_name)}</b></a><br><small class="muted">${esc(e.code)}</small>` },
      { l: 'Designation', k: 'designation' }, { l: 'Department', k: 'department' }, { l: 'Joined', fmt: (e) => fmtDate(e.join_date) }, { l: 'Confirmation due', fmt: (e) => `${fmtDate(e.due_date)} ${e.overdue ? badge('Overdue') : ''}` },
      { l: '', cls: 'r', fmt: (e) => `<a class="btn sm ghost" href="#/employees/${e.id}">Open profile</a>` }], items, { empty: 'No confirmations due' })}
      <p class="note">To confirm someone, open their profile, choose “Promote, transfer or exit”, then Confirmation.</p></div>`;
  } else {
    await mountCrud(body, crudView({
      id: 'disc', endpoint: '/api/disciplinary', title: 'Disciplinary register', single: 'Disciplinary record', canManage: C.can('lifecycle.manage'),
      fields: [{ k: 'emp_id', l: 'Employee', t: 'emp', req: 1 }, { k: 'action_date', l: 'Date', t: 'date', req: 1 },
        { k: 'action_type', l: 'Action', t: 'select', req: 1, o: ['Verbal Warning', 'Written Warning', 'Show Cause', 'Suspension', 'Final Warning', 'Termination'] },
        { k: 'issued_by', l: 'Issued by' }, { k: 'reason', l: 'Reason', t: 'textarea', w: 2 }, { k: 'status', l: 'Status', t: 'select', o: ['Open', 'Replied', 'Closed'], req: 1, d: 'Open' },
        { k: 'resolution', l: 'Resolution / outcome', t: 'textarea' }],
      cols: [{ l: 'Date', fmt: (r) => fmtDate(r.action_date) }, { l: 'Employee', fmt: (r) => `<b>${esc(r.full_name)}</b><br><small class="muted">${esc(r.code)}</small>` },
        { l: 'Action', k: 'action_type' }, { l: 'Reason', k: 'reason' }, { l: 'Issued by', k: 'issued_by' }, { l: 'Status', fmt: (r) => badge(r.status) }],
    }));
  }
}
on('lc:tab', (el) => { S.tab = el.dataset.tab; render($('#main'), C); });
on('lc:type', (el) => { S.type = el.value; render($('#main'), C); });
on('lc:tick', async (el) => { await api.put(`/api/tasks/${el.dataset.id}`, { done: el.checked }); render($('#main'), C); });
