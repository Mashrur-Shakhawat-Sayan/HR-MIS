/** Notice board — announcements for everyone; notices.manage can post. */
import { api } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { badge, emptyState, esc, fmtDate } from '../core/ui.js';

export async function render(main, ctx) {
  const manage = ctx.can('notices.manage');
  if (!manage) {
    const { items } = await api.get('/api/notices');
    main.innerHTML = `<div class="card">${items.map((n) => `<div class="notice ${n.priority === 'Important' ? 'imp' : ''}">
      <b style="font-size:15px">${esc(n.title)} ${n.priority === 'Important' ? badge('Important') : ''}</b><small>${fmtDate(n.posted_on)}<i class="sep"></i>${esc(n.audience || '')}</small>
      <p>${esc(n.body || '')}</p></div>`).join('') || emptyState('No notices right now', 'Announcements from HR will appear here.', 'megaphone')}</div>`;
    return;
  }
  await mountCrud(main, crudView({
    id: 'notices', endpoint: '/api/notices', title: 'Notice board', single: 'Notice', canManage: true,
    prefill: () => ({ posted_on: new Date().toISOString().slice(0, 10), audience: 'All Employees', priority: 'Normal' }),
    fields: [{ k: 'title', l: 'Title', req: 1, w: 2 }, { k: 'posted_on', l: 'Date', t: 'date', req: 1 }, { k: 'expires_on', l: 'Show until (optional)', t: 'date' },
      { k: 'audience', l: 'Audience', ph: 'All Employees / a unit / a department' }, { k: 'priority', l: 'Priority', t: 'select', o: ['Normal', 'Important'], req: 1 },
      { k: 'body', l: 'Message', t: 'textarea', w: 2, rows: 6 }],
    cols: [{ l: 'Date', fmt: (n) => `<span class="nowrap">${fmtDate(n.posted_on)}</span>` }, { l: 'Notice', fmt: (n) => `<b>${esc(n.title)}</b><br><small class="muted">${esc((n.body || '').slice(0, 140))}</small>` },
      { l: 'Audience', k: 'audience' }, { l: 'Priority', fmt: (n) => (n.priority === 'Important' ? badge('Important') : '<span class="muted">Normal</span>') },
      { l: 'Expires', fmt: (n) => fmtDate(n.expires_on) }, { l: 'Posted by', k: 'created_by' }],
  }));
}
