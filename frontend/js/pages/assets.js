/** Asset register — issue to and return from employees. */
import { api } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { $, badge, esc, fmtDate, formHTML, ic, kpi, modal, money, on, readForm, toast } from '../core/ui.js';

let C;
const CATS = ['Laptop', 'Desktop', 'Mobile Phone', 'SIM', 'Vehicle', 'Furniture', 'ID / Access Card', 'Other'];

export async function render(main, ctx) {
  C = ctx;
  const all = (await api.get('/api/assets')).items;
  const manage = ctx.can('assets.manage');
  await mountCrud(main, crudView({
    id: 'assets', endpoint: '/api/assets', title: 'Asset register', single: 'Asset', canManage: manage,
    filters: [{ k: 'status', all: 'All statuses', o: ['Assigned', 'In Stock', 'Under Repair', 'Disposed'] }, { k: 'category', all: 'All categories', o: CATS }],
    fields: [{ k: 'tag', l: 'Asset tag', req: 1 }, { k: 'name', l: 'Asset name / model', req: 1 }, { k: 'category', l: 'Category', t: 'select', o: CATS }, { k: 'serial', l: 'Serial / registration no.' },
      { k: 'value', l: 'Purchase value (৳)', t: 'number', min: 0 }, { k: 'condition', l: 'Condition', t: 'select', o: ['New', 'Good', 'Fair', 'Damaged'], d: 'Good' },
      { k: 'status', l: 'Status', t: 'select', o: ['Assigned', 'In Stock', 'Under Repair', 'Disposed'], req: 1, d: 'In Stock' }, { k: 'emp_id', l: 'Assigned to', t: 'emp' },
      { k: 'issued_on', l: 'Issued on', t: 'date' }, { k: 'notes', l: 'Notes', t: 'textarea', w: 2 }],
    cols: [{ l: 'Tag', fmt: (a) => `<b>${esc(a.tag)}</b>` }, { l: 'Asset', fmt: (a) => `${esc(a.name)}<br><small class="muted">${esc(a.serial || '')}</small>` }, { l: 'Category', k: 'category' },
      { l: 'Assigned to', fmt: (a) => (a.emp_id ? `<a class="link" href="#/employees/${a.emp_id}">${esc(a.full_name)}</a><br><small class="muted">since ${fmtDate(a.issued_on)}</small>` : '<span class="muted">—</span>') },
      { l: 'Value', num: 1, fmt: (a) => money(a.value) }, { l: 'Condition', k: 'condition' }, { l: 'Status', fmt: (a) => badge(a.status) }],
    rowActions: (a) => !manage ? '' : a.emp_id ? `<button class="btn sm ghost" data-act="ast:return" data-id="${a.id}">${ic('undo')}Return</button> ` : a.status === 'In Stock' ? `<button class="btn sm ghost" data-act="ast:issue" data-id="${a.id}">${ic('send')}Issue</button> ` : '',
  }), `<div class="kpis">${kpi('Total assets', all.length, money(all.reduce((s, a) => s + (a.value || 0), 0)) + ' book value')}${kpi('Assigned', all.filter((a) => a.status === 'Assigned').length, 'with employees', 'info')}
    ${kpi('In stock', all.filter((a) => a.status === 'In Stock').length, 'available to issue')}${kpi('Under repair', all.filter((a) => a.status === 'Under Repair').length, '', 'accent')}</div>`);
}
on('ast:issue', async (el) => {
  const f = [{ k: 'emp_id', l: 'Issue to', t: 'emp', req: 1, w: 2 }, { k: 'issued_on', l: 'Issue date', t: 'date', req: 1, d: new Date().toISOString().slice(0, 10) }];
  modal('Issue asset', await formHTML(f), { saveLabel: 'Issue', onSave: async () => { const d = readForm(f, $('#modal')); if (!d) return false; await api.post(`/api/assets/${el.dataset.id}/issue`, d); toast('Asset issued', 'ok'); render($('#main'), C); } });
});
on('ast:return', async (el) => {
  const f = [{ k: 'condition', l: 'Condition on return', t: 'select', o: ['Good', 'Fair', 'Damaged'], req: 1, d: 'Good' }];
  modal('Return asset', await formHTML(f), { saveLabel: 'Mark returned', onSave: async () => { const d = readForm(f, $('#modal')); await api.post(`/api/assets/${el.dataset.id}/return`, d); toast('Asset returned to stock', 'ok'); render($('#main'), C); } });
});
