/** Performance reviews — five-factor scorecards with an overall rating. */
import { api } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { badge, esc, kpi } from '../core/ui.js';

const rating = (s) => (s == null ? '' : s >= 4.5 ? '<span class="badge ok">Outstanding</span>' : s >= 3.75 ? '<span class="badge ok">Exceeds</span>' : s >= 2.75 ? '<span class="badge info">Meets</span>' : '<span class="badge bad">Needs improvement</span>');

export async function render(main, ctx) {
  const all = (await api.get('/api/reviews')).items;
  const scored = all.filter((r) => r.score != null);
  const avg = scored.length ? scored.reduce((s, r) => s + r.score, 0) / scored.length : 0;
  const top = [...scored].sort((a, b) => b.score - a.score)[0];
  const scoreF = (k, l) => ({ k, l: `${l} (1–5)`, t: 'number', min: 1, max: 5, d: 3 });
  await mountCrud(main, crudView({
    id: 'reviews', endpoint: '/api/reviews', title: ctx.can('performance.view_all') ? 'Performance reviews' : 'My team’s reviews', single: 'Review', canManage: ctx.can('performance.manage'),
    filters: [{ k: 'status', all: 'All statuses', o: ['Draft', 'Submitted', 'Acknowledged'] }],
    prefill: () => ({ period: `${new Date().getFullYear()} ${new Date().getMonth() < 6 ? 'H1' : 'H2'}`, status: 'Draft' }),
    fields: [{ k: 'emp_id', l: 'Employee', t: 'emp', req: 1, team: !ctx.can('performance.view_all') }, { k: 'reviewer_id', l: 'Reviewer', t: 'emp' }, { k: 'period', l: 'Review period', req: 1, ph: 'e.g. 2026 H2' },
      { k: 'status', l: 'Status', t: 'select', o: ['Draft', 'Submitted', 'Acknowledged'], req: 1, d: 'Draft' },
      scoreF('quality', 'Quality of work'), scoreF('productivity', 'Productivity'), scoreF('teamwork', 'Teamwork'), scoreF('punctuality', 'Punctuality & attendance'), scoreF('initiative', 'Initiative'),
      { k: 'goals', l: 'Goals for next period', t: 'textarea', w: 2 }, { k: 'comments', l: 'Reviewer comments', t: 'textarea', w: 2 }],
    cols: [{ l: 'Employee', fmt: (r) => `<a class="link" href="#/employees/${r.emp_id}"><b>${esc(r.full_name)}</b></a><br><small class="muted">${esc(r.code)}<i class="sep"></i>${esc(r.department || '')}</small>` },
      { l: 'Period', k: 'period' }, { l: 'Reviewer', k: 'reviewer_name' }, ...['quality', 'productivity', 'teamwork', 'punctuality', 'initiative'].map((k) => ({ l: k.slice(0, 5) + '.', num: 1, k })),
      { l: 'Score', num: 1, fmt: (r) => `<b>${r.score ?? ''}</b>` }, { l: 'Rating', fmt: (r) => rating(r.score) }, { l: 'Status', fmt: (r) => badge(r.status) }],
  }), `<div class="kpis">${kpi('Reviews', all.length, `${all.filter((r) => r.status === 'Draft').length} in draft`)}${kpi('Average score', `${avg.toFixed(2)} / 5`, 'across all reviews', 'info')}
    ${kpi('Top performer', top ? esc(top.full_name) : '—', top ? `${top.score}<i class="sep"></i>${esc(top.period)}` : '', 'accent')}</div>`,
  '<p class="note">The score is the average of the five factors. A score of 4.5 or more is Outstanding, 3.75 or more Exceeds expectations, 2.75 or more Meets expectations, and anything lower Needs improvement.</p>');
}
