/** Organization — business units, departments, designations & grades, org chart. */
import { api } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { $, avatar, esc, on, tabs } from '../core/ui.js';

let C;
const S = { tab: 'departments' };

export async function render(main, ctx) {
  C = ctx;
  const manage = ctx.can('org.manage');
  main.innerHTML = `${tabs('org:tab', [['departments', 'Departments'], ['units', 'Business units'], ['designations', 'Designations & grades'], ['chart', 'Organisation chart']], S.tab)}<div id="orgBody" style="margin-top:16px"></div>`;
  const body = $('#orgBody');
  if (S.tab === 'chart') return chart(body);
  const views = {
    units: () => crudView({ id: 'units', endpoint: '/api/units', title: 'Business units', single: 'Business unit', canManage: manage,
      fields: [{ k: 'name', l: 'Name', req: 1, w: 2 }, { k: 'code', l: 'Short code' }, { k: 'location', l: 'Location' }],
      cols: [{ l: 'Business unit', fmt: (u) => `<b>${esc(u.name)}</b>` }, { l: 'Code', k: 'code' }, { l: 'Location', k: 'location' }, { l: 'Active staff', num: 1, k: 'headcount' }] }),
    departments: () => crudView({ id: 'depts', endpoint: '/api/departments', title: 'Departments', single: 'Department', canManage: manage,
      fields: [{ k: 'name', l: 'Department', req: 1 }, { k: 'unit_id', l: 'Business unit', t: 'unit' }, { k: 'head_emp_id', l: 'Department head', t: 'emp' }, { k: 'cost_center', l: 'Cost centre' }],
      cols: [{ l: 'Department', fmt: (d) => `<b>${esc(d.name)}</b>` }, { l: 'Business unit', k: 'unit_name' }, { l: 'Head', fmt: (d) => (d.head_emp_id ? `<a class="link" href="#/employees/${d.head_emp_id}">${esc(d.head_name)}</a>` : '<span class="muted">—</span>') },
        { l: 'Cost centre', k: 'cost_center' }, { l: 'Active staff', num: 1, k: 'headcount' }] }),
    designations: () => crudView({ id: 'desigs', endpoint: '/api/designations', title: 'Designations', single: 'Designation', canManage: manage,
      fields: [{ k: 'title', l: 'Designation', req: 1, w: 2 }, { k: 'grade', l: 'Grade' }, { k: 'level', l: 'Level (1 = most senior)', t: 'number', min: 1 }],
      cols: [{ l: 'Level', num: 1, k: 'level' }, { l: 'Designation', fmt: (d) => `<b>${esc(d.title)}</b>` }, { l: 'Grade', k: 'grade' }, { l: 'Active staff', num: 1, k: 'headcount' }] }),
  };
  await mountCrud(body, views[S.tab]());
}
on('org:tab', (el) => { S.tab = el.dataset.tab; render($('#main'), C); });

async function chart(body) {
  const { items } = await api.get('/api/org-chart');
  const kids = (id) => items.filter((e) => e.manager_id === id);
  const node = (e) => `<div class="tree-node"><a class="who" href="#/employees/${e.id}">${avatar(e.full_name, 'sm')}<span><b>${esc(e.full_name)}</b><small>${esc(e.designation || '')}<i class="sep"></i>${esc(e.department || '')}${kids(e.id).length ? `<i class="sep"></i>${kids(e.id).length} direct report${kids(e.id).length > 1 ? 's' : ''}` : ''}</small></span></a>
    ${kids(e.id).length ? `<div class="tree">${kids(e.id).map(node).join('')}</div>` : ''}</div>`;
  body.innerHTML = `<div class="card"><h3>Reporting structure</h3>${items.filter((e) => !e.manager_id).map(node).join('') || '<div class="empty">Set reporting managers on employee records to build the chart.</div>'}</div>`;
}
