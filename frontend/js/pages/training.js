/** Training programs and participants / attendance. */
import { api, lookups } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { $, badge, esc, fmtDate, ic, kpi, modal, money, on, plural, toast } from '../core/ui.js';

let C;

export async function render(main, ctx) {
  C = ctx;
  const all = (await api.get('/api/trainings')).items;
  const yr = String(new Date().getFullYear());
  const thisYear = all.filter((t) => (t.start_date || '').startsWith(yr));
  await mountCrud(main, crudView({
    id: 'trainings', endpoint: '/api/trainings', title: 'Training programs', single: 'Training', canManage: ctx.can('training.manage'),
    filters: [{ k: 'status', all: 'All statuses', o: ['Scheduled', 'Completed', 'Cancelled'] }],
    fields: [{ k: 'title', l: 'Program', req: 1, w: 2 }, { k: 'category', l: 'Category', t: 'select', o: ['Technical', 'Compliance', 'Leadership', 'Soft Skills', 'Onboarding', 'Safety'] },
      { k: 'trainer', l: 'Trainer' }, { k: 'start_date', l: 'Date', t: 'date' }, { k: 'hours', l: 'Duration (hours)', t: 'number', min: 0 }, { k: 'venue', l: 'Venue' },
      { k: 'mode', l: 'Mode', t: 'select', o: ['Classroom', 'Online', 'On-the-job'] }, { k: 'cost', l: 'Cost (৳)', t: 'number', min: 0 },
      { k: 'status', l: 'Status', t: 'select', o: ['Scheduled', 'Completed', 'Cancelled'], req: 1, d: 'Scheduled' }, { k: 'description', l: 'Description', t: 'textarea', w: 2 }],
    cols: [{ l: 'Date', fmt: (t) => `<span class="nowrap">${fmtDate(t.start_date)}</span>` }, { l: 'Program', fmt: (t) => `<b>${esc(t.title)}</b><br><small class="muted">${esc(t.trainer || '')}<i class="sep"></i>${esc(t.venue || '')}</small>` },
      { l: 'Category', k: 'category' }, { l: 'Mode', k: 'mode' }, { l: 'Hours', num: 1, k: 'hours' }, { l: 'Participants', num: 1, fmt: (t) => `${t.participants}${t.status === 'Completed' ? ` <small class="muted">(${t.attended} attended)</small>` : ''}` },
      { l: 'Cost', num: 1, fmt: (t) => money(t.cost) }, { l: 'Status', fmt: (t) => badge(t.status) }],
    rowActions: (t) => `<button class="btn sm ghost" data-act="trn:people" data-id="${t.id}">${ic('users')}Participants</button> `,
  }), `<div class="kpis">${kpi(`Programs in ${yr}`, thisYear.length, `${thisYear.filter((t) => t.status === 'Completed').length} completed`)}
    ${kpi('Training hours delivered', thisYear.filter((t) => t.status === 'Completed').reduce((s, t) => s + (t.hours || 0) * (t.attended || 0), 0), 'person-hours this year', 'info')}
    ${kpi('Training spend', money(thisYear.reduce((s, t) => s + (t.cost || 0), 0)), 'this year', 'accent')}</div>`);
}

on('trn:people', async (el) => {
  const id = Number(el.dataset.id);
  const [cur, emps] = await Promise.all([api.get(`/api/trainings/${id}/participants`), lookups.employees()]);
  const sel = new Map(cur.items.map((p) => [p.emp_id, p.attended]));
  const edit = C.can('training.manage');
  modal('Participants', `<input class="search" placeholder="Filter employees" id="trnQ" style="width:100%;margin-bottom:10px">
    <div style="max-height:420px;overflow:auto" id="trnList">${emps.map((e) => `<div class="task" data-name="${esc((e.full_name + ' ' + e.code + ' ' + (e.department || '')).toLowerCase())}">
      <label class="chk grow"><input type="checkbox" class="trn-in" value="${e.id}" ${sel.has(e.id) ? 'checked' : ''} ${edit ? '' : 'disabled'}> ${esc(e.full_name)} <small class="muted">${esc(e.code)}<i class="sep"></i>${esc(e.department || '')}</small></label>
      <label class="chk"><input type="checkbox" class="trn-att" value="${e.id}" ${sel.get(e.id) ? 'checked' : ''} ${edit ? '' : 'disabled'}> attended</label></div>`).join('')}</div>`,
  edit ? { saveLabel: 'Save participants', onSave: async () => {
    const att = new Set([...document.querySelectorAll('.trn-att:checked')].map((x) => Number(x.value)));
    const participants = [...document.querySelectorAll('.trn-in:checked')].map((x) => ({ emp_id: Number(x.value), attended: att.has(Number(x.value)) }));
    await api.put(`/api/trainings/${id}/participants`, { participants });
    toast(`${plural(participants.length, 'participant')} saved`, 'ok');
    render($('#main'), C);
  } } : {});
  $('#trnQ').addEventListener('input', (e) => { const q = e.target.value.toLowerCase(); document.querySelectorAll('#trnList .task').forEach((r) => r.classList.toggle('hidden', !r.dataset.name.includes(q))); });
});
