/** Employees — directory, profile, add/edit, documents, career events, checklists, ID card. */
import { api, lookups } from '../core/api.js';
import { $, avatar, badge, closeModal, confirmBox, debounce, esc, fileToBase64, fmtDate, formHTML, ic, meta, modal, money, num, on, plural, printHTML, readForm, table, tabs, toast, yearsSince } from '../core/ui.js';

let C;
const S = { q: '', status: 'Active', dept_id: '', unit_id: '', emp_type: '', tab: 'overview' };
const TYPES = ['Permanent', 'Probation', 'Contract', 'Intern', 'Part-time'];
const STATUSES = ['Active', 'On Notice', 'Resigned', 'Terminated', 'Retired'];

export function employeeFields(ctx, isNew) {
  const f = [
    { t: 'section', l: 'Identity' },
    { k: 'code', l: 'Employee ID', hint: isNew ? 'Leave blank to auto-generate' : '' }, { k: 'full_name', l: 'Full name', req: 1 },
    { k: 'gender', l: 'Gender', t: 'select', o: ['Male', 'Female', 'Other'] }, { k: 'dob', l: 'Date of birth', t: 'date' },
    { k: 'marital_status', l: 'Marital status', t: 'select', o: ['Single', 'Married', 'Divorced', 'Widowed'] },
    { k: 'blood_group', l: 'Blood group', t: 'select', o: ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'] },
    { k: 'nid', l: 'NID number' }, { k: 'father_name', l: "Father's name" }, { k: 'mother_name', l: "Mother's name" },
    { t: 'section', l: 'Contact' },
    { k: 'phone', l: 'Mobile' }, { k: 'email', l: 'Email', t: 'email' },
    { k: 'present_address', l: 'Present address', t: 'textarea', rows: 2 }, { k: 'permanent_address', l: 'Permanent address', t: 'textarea', rows: 2 },
    { k: 'emergency_name', l: 'Emergency contact (name / relation)' }, { k: 'emergency_phone', l: 'Emergency phone' },
    { t: 'section', l: 'Job' },
    { k: 'unit_id', l: 'Business unit', t: 'unit' }, { k: 'dept_id', l: 'Department', t: 'dept' },
    { k: 'designation_id', l: 'Designation', t: 'desig' }, { k: 'grade', l: 'Grade' },
    { k: 'emp_type', l: 'Employment type', t: 'select', o: TYPES, req: 1, d: 'Permanent' }, { k: 'manager_id', l: 'Reporting manager', t: 'emp' },
    { k: 'join_date', l: 'Joining date', t: 'date', req: 1 }, { k: 'confirm_date', l: 'Confirmation date', t: 'date' },
    { k: 'status', l: 'Status', t: 'select', o: STATUSES, req: 1, d: 'Active' }, { k: 'exit_date', l: 'Exit / last working date', t: 'date' },
  ];
  if (ctx.can('employees.salary')) {
    f.push({ t: 'section', l: 'Pay & bank' }, { k: 'gross_salary', l: 'Gross salary (৳ / month)', t: 'number', min: 0 },
      { k: 'pf_member', l: 'Provident fund', t: 'checkbox', cl: 'PF member', d: 1 }, { k: 'bank_name', l: 'Bank' },
      { k: 'bank_account', l: 'Bank account number' }, { k: 'tin', l: 'e-TIN' });
  }
  return f;
}

export async function render(main, ctx) {
  C = ctx;
  if (ctx.segs[1]) return renderProfile(main, Number(ctx.segs[1]));
  const depts = ctx.can('org.view') ? await lookups.departments() : [];
  const units = ctx.can('org.view') ? await lookups.units() : [];
  const opt = (k, list, all) => `<select data-change="emp:filter" data-k="${k}" aria-label="${esc(all || k)}">${all ? `<option value="">${all}</option>` : ''}${list.map(([v, l]) => `<option value="${esc(v)}" ${String(S[k]) === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
  main.innerHTML = `<div class="card"><div class="card-head">
      <label class="search-box">${ic('search')}<input placeholder="Name, ID, phone or designation" aria-label="Search employees" value="${esc(S.q)}" data-input="emp:search"></label>
      ${units.length ? opt('unit_id', units.map((u) => [u.id, u.name]), 'All units') : ''}
      ${depts.length ? opt('dept_id', depts.map((d) => [d.id, d.name]), 'All departments') : ''}
      ${opt('emp_type', TYPES.map((t) => [t, t]), 'All types')}
      ${opt('status', [['Active', 'Current staff'], ...STATUSES.slice(1).map((s) => [s, s]), ['all', 'Everyone, including leavers']], '')}
      <span class="grow"></span><span class="muted" id="empCount"></span>
      ${ctx.can('reports.view') ? `<button class="btn ghost" data-act="emp:csv">${ic('download')}Export</button>` : ''}
      ${ctx.can('employees.manage') ? `<button class="btn" data-act="emp:new">${ic('user-plus')}Add employee</button>` : ''}</div>
    <div id="empList"><div class="empty">Loading…</div></div></div>`;
  await loadList();
}

async function loadList() {
  const { items } = await api.get('/api/employees', { q: S.q, status: S.status, dept_id: S.dept_id, unit_id: S.unit_id, emp_type: S.emp_type });
  $('#empCount').textContent = plural(items.length, 'employee');
  const sal = C.can('employees.salary');
  $('#empList').innerHTML = table([
    { l: 'ID', fmt: (e) => `<span class="nowrap">${esc(e.code)}</span>` },
    { l: 'Employee', fmt: (e) => `<a class="who" href="#/employees/${e.id}">${avatar(e.full_name, 'sm')}<span><b>${esc(e.full_name)}</b><small>${esc(e.email || e.phone || '')}</small></span></a>` },
    { l: 'Role', fmt: (e) => `<div class="who" style="display:block"><b style="font-weight:400">${esc(e.designation || '—')}</b><small>${meta(e.department, e.unit_name)}</small></div>` },
    { l: 'Type', fmt: (e) => e.emp_type === 'Permanent' ? 'Permanent' : badge(e.emp_type) },
    { l: 'Joined', fmt: (e) => `<span class="nowrap">${fmtDate(e.join_date)}</span>` },
    ...(sal ? [{ l: 'Gross', num: 1, fmt: (e) => money(e.gross_salary) }] : []),
    { l: 'Status', fmt: (e) => badge(e.status) },
    { l: '', cls: 'r nowrap', fmt: (e) => `<a class="ib" title="Open profile" aria-label="Open profile" href="#/employees/${e.id}">${ic('eye')}</a>${C.can('employees.manage') ? `<button class="ib" title="Edit" aria-label="Edit" data-act="emp:edit" data-id="${e.id}">${ic('pencil')}</button>` : ''}<button class="ib" title="Print ID card" aria-label="Print ID card" data-act="emp:idcard" data-id="${e.id}">${ic('idcard')}</button>` },
  ], items, { empty: 'No employees match these filters' });
}

const later = debounce(loadList, 250);
on('emp:search', (el) => { S.q = el.value; later(); });
on('emp:filter', (el) => { S[el.dataset.k] = el.value; loadList(); });
on('emp:csv', () => api.download('/api/reports/employee-master', { format: 'csv', status: S.status === 'Active' ? '' : 'all' }));
on('emp:new', () => editEmployee());
on('emp:edit', (el) => editEmployee(Number(el.dataset.id)));
on('emp:idcard', async (el) => idCard(await api.get(`/api/employees/${el.dataset.id}`)));

export async function editEmployee(id, prefill = {}, after) {
  const row = id ? await api.get(`/api/employees/${id}`) : { status: 'Active', emp_type: 'Permanent', pf_member: 1, ...prefill };
  const fields = employeeFields(C, !id);
  const extra = !id && C.can('users.manage') ? `<div class="sec">Login account</div><label class="chk"><input type="checkbox" id="mkLogin"> Create a login for this employee (username = employee ID, a temporary password is shown once)</label>
    <label class="fld" style="margin-top:8px;max-width:280px"><span>Role</span><select id="mkRole"><option value="employee">Employee</option><option value="manager">Line Manager</option><option value="hr_officer">HR Officer</option><option value="payroll_officer">Payroll Officer</option><option value="hr_manager">HR Manager</option></select></label>` : '';
  modal(id ? `Edit ${row.full_name}` : 'New employee', await formHTML(fields, row, 'three') + extra, {
    size: 'wide', saveLabel: id ? 'Save changes' : 'Create employee',
    onSave: async () => {
      const d = readForm(fields, $('#modal'));
      if (!d) return false;
      if (id) {
        await api.put(`/api/employees/${id}`, d);
        toast('Employee updated', 'ok');
      } else {
        if ($('#mkLogin')?.checked) { d.create_login = true; d.role = $('#mkRole').value; }
        const res = await api.post('/api/employees', d);
        toast(`Employee ${res.employee.code} created`, 'ok');
        if (res.login) {
          setTimeout(() => modal('Login created', `<p>Share these details with <b>${esc(res.employee.full_name)}</b>. The password must be changed at first sign-in and will not be shown again.</p>
            <div class="dl"><div><small>Username</small><b>${esc(res.login.username)}</b></div><div><small>Temporary password</small><b class="mono">${esc(res.login.temporary_password)}</b></div></div>`), 50);
        }
        if (after) after(res.employee);
        else location.hash = `#/employees/${res.employee.id}`;
        return;
      }
      if (C.segs[1]) renderProfile($('#main'), id); else loadList();
    },
  });
  const desig = $('#f_designation_id'), grade = $('#f_grade'), dept = $('#f_dept_id'), unit = $('#f_unit_id');
  const designations = await lookups.designations(), departments = await lookups.departments();
  desig?.addEventListener('change', () => { const g = designations.find((x) => String(x.id) === desig.value); if (g && g.grade) grade.value = g.grade; });
  dept?.addEventListener('change', () => {
    const dd = departments.find((x) => String(x.id) === dept.value);
    if (dd && dd.unit_id) unit.value = dd.unit_id;
    if (dd && dd.head_emp_id && !$('#f_manager_id').value && String(dd.head_emp_id) !== String(id)) $('#f_manager_id').value = dd.head_emp_id;
  });
}

/* ------------------------------------------------------------ profile */
async function renderProfile(main, id) {
  const e = await api.get(`/api/employees/${id}`);
  C.setTitle('Employee profile', '', ['#/employees', 'All employees']);
  const kv = (l, v) => `<div><small>${l}</small>${v || '<span class="muted">—</span>'}</div>`;
  const T = [['overview', 'Overview'], ['job', 'Job & pay'], ['leave', 'Leave & attendance']];
  if (e.events.length || C.can('lifecycle.view')) T.push(['history', 'Career history']);
  if (C.can('lifecycle.view')) T.push(['checklist', `Checklists${e.tasks.filter((t) => !t.done).length ? ` (${e.tasks.filter((t) => !t.done).length})` : ''}`]);
  if (C.can('employees.documents') || C.user.emp_id === id) T.push(['docs', `Documents (${e.documents.length})`]);
  if (!T.find((t) => t[0] === S.tab)) S.tab = 'overview';
  let body = '';
  if (S.tab === 'overview') {
    body = `<div class="sec">Personal</div><div class="dl">${kv('Gender', esc(e.gender))}${kv('Date of birth', e.dob ? `${fmtDate(e.dob)} (${yearsSince(e.dob)} yrs)` : '')}${kv('Marital status', esc(e.marital_status))}
      ${kv('Blood group', esc(e.blood_group))}${'nid' in e ? kv('NID', esc(e.nid)) : ''}${kv("Father's name", esc(e.father_name))}${kv("Mother's name", esc(e.mother_name))}</div>
      <div class="sec">Contact</div><div class="dl">${kv('Mobile', esc(e.phone))}${kv('Email', esc(e.email))}${kv('Emergency contact', `${esc(e.emergency_name || '')} ${esc(e.emergency_phone || '')}`)}
      ${kv('Present address', esc(e.present_address))}${kv('Permanent address', esc(e.permanent_address))}</div>
      ${e.team.length ? `<div class="sec">Direct reports (${e.team.length})</div><div class="chips">${e.team.map((t) => `<a class="chip link" href="#/employees/${t.id}">${esc(t.full_name)}</a>`).join('')}</div>` : ''}
      ${e.assets.length ? `<div class="sec">Assets held</div><div class="chips">${e.assets.map((a) => `<span class="chip">${ic('laptop', 14)}${esc(a.tag)}, ${esc(a.name)}</span>`).join('')}</div>` : ''}
      ${e.user ? `<div class="sec">Login account</div><div class="dl">${kv('Username', esc(e.user.username))}${kv('Role', esc(e.user.role))}${kv('Last sign-in', e.user.last_login ? fmtDate(e.user.last_login) : 'Never')}</div>` : ''}`;
  } else if (S.tab === 'job') {
    body = `<div class="dl">${kv('Business unit', esc(e.unit_name))}${kv('Department', esc(e.department))}${kv('Designation', esc(e.designation))}${kv('Grade', esc(e.grade))}
      ${kv('Employment type', esc(e.emp_type))}${kv('Reporting manager', e.manager_id ? `<a class="link" href="#/employees/${e.manager_id}">${esc(e.manager_name)}</a>` : '')}
      ${kv('Joining date', fmtDate(e.join_date))}${kv('Service length', plural(yearsSince(e.join_date), 'year'))}${kv('Confirmation date', fmtDate(e.confirm_date))}
      ${e.exit_date ? kv('Exit date', fmtDate(e.exit_date)) + kv('Exit reason', esc(e.exit_reason)) : ''}</div>
      ${'gross_salary' in e ? `<div class="sec">Pay</div><div class="dl">${kv('Gross salary', money(e.gross_salary))}${kv('Provident fund', e.pf_member ? 'Member' : 'Not a member')}${kv('Bank', esc(e.bank_name))}${kv('Account', esc(e.bank_account))}${kv('e-TIN', esc(e.tin))}</div>` : ''}
      ${e.loans.length ? `<div class="sec">Loans & advances</div>${table([{ l: 'Type', k: 'loan_type' }, { l: 'Amount', num: 1, fmt: (r) => money(r.principal) }, { l: 'Installment', num: 1, fmt: (r) => money(r.installment) }, { l: 'Status', fmt: (r) => badge(r.status) }], e.loans)}` : ''}
      ${e.reviews.length ? `<div class="sec">Performance reviews</div>${table([{ l: 'Period', k: 'period' }, { l: 'Score', num: 1, fmt: (r) => r.score ?? '' }, { l: 'Status', fmt: (r) => badge(r.status) }], e.reviews)}` : ''}`;
  } else if (S.tab === 'leave') {
    const att = await api.get('/api/attendance/register', { month: new Date().toISOString().slice(0, 7) }).catch(() => null);
    const me = att?.rows.find((r) => r.id === id);
    body = `<div class="sec">Leave balance ${new Date().getFullYear()}</div>${table([{ l: 'Leave type', k: 'leave_type' }, { l: 'Entitled', num: 1, fmt: (b) => b.remaining === null ? '—' : num(b.entitled, 1) },
      { l: 'Taken', num: 1, fmt: (b) => num(b.used, 1) }, { l: 'Pending', num: 1, fmt: (b) => num(b.pending, 1) }, { l: 'Remaining', num: 1, fmt: (b) => b.remaining === null ? '—' : `<b>${num(b.remaining, 1)}</b>` }], e.leave_balance)}
      ${me ? `<div class="sec">Attendance this month</div><div class="chips">${[['P', 'Present'], ['L', 'Late'], ['HD', 'Half day'], ['A', 'Absent'], ['LV', 'Leave'], ['WFH', 'WFH']].map(([k, l]) => `<span class="chip s-${k}">${l}<b>${me.totals[k] || 0}</b></span>`).join('')}<span class="chip">Attendance<b>${me.totals.pct}%</b></span></div>` : ''}`;
  } else if (S.tab === 'history') {
    body = `${C.can('lifecycle.manage') ? `<div class="toolbar" style="margin-bottom:10px"><span class="grow"></span><button class="btn" data-act="emp:event" data-id="${id}">${ic('route')}Record event</button></div>` : ''}
      ${table([{ l: 'Date', fmt: (v) => fmtDate(v.effective_date) }, { l: 'Event', fmt: (v) => badge(v.event_type) }, { l: 'From', k: 'old_value' }, { l: 'To', k: 'new_value' }, { l: 'Details', k: 'details' }, { l: 'By', k: 'created_by' }], e.events, { empty: 'No career events recorded' })}`;
  } else if (S.tab === 'checklist') {
    const groups = {};
    e.tasks.forEach((t) => (groups[t.category] ||= []).push(t));
    body = `${C.can('lifecycle.manage') ? `<div class="toolbar" style="margin-bottom:10px"><span class="grow"></span><button class="btn ghost" data-act="emp:task" data-id="${id}">${ic('plus')}Add task</button></div>` : ''}
      ${Object.entries(groups).map(([g, list]) => `<div class="sec">${esc(g)} — ${list.filter((t) => t.done).length}/${list.length} done</div>${list.map((t) => `<div class="task ${t.done ? 'done' : ''}">
        <input type="checkbox" ${t.done ? 'checked' : ''} ${C.can('lifecycle.manage') ? '' : 'disabled'} data-change="emp:tick" data-id="${t.id}" data-emp="${id}"><span class="grow">${esc(t.task)}</span><small class="muted">${esc(t.owner || '')}</small>${t.due_date ? `<small class="muted">${fmtDate(t.due_date)}</small>` : ''}</div>`).join('')}`).join('') || '<div class="empty">No checklist items</div>'}
      ${e.disciplinary.length ? `<div class="sec">Disciplinary record</div>${table([{ l: 'Date', fmt: (r) => fmtDate(r.action_date) }, { l: 'Action', k: 'action_type' }, { l: 'Reason', k: 'reason' }, { l: 'Status', fmt: (r) => badge(r.status) }], e.disciplinary)}` : ''}`;
  } else if (S.tab === 'docs') {
    body = `${C.can('employees.documents') ? `<div class="toolbar" style="margin-bottom:10px"><span class="grow"></span><button class="btn" data-act="emp:upload" data-id="${id}">${ic('upload')}Upload document</button></div>` : ''}
      ${table([{ l: 'Title', fmt: (d) => `<b>${esc(d.title)}</b><br><small class="muted">${esc(d.filename)}</small>` }, { l: 'Type', k: 'doc_type' }, { l: 'Size', num: 1, fmt: (d) => `${num((d.size || 0) / 1024)} KB` }, { l: 'Uploaded', fmt: (d) => fmtDate(d.uploaded_at) },
        { l: '', cls: 'r nowrap', fmt: (d) => `<button class="ib" title="Download" aria-label="Download" data-act="emp:dl" data-id="${d.id}">${ic('download')}</button>${C.can('employees.documents') ? `<button class="ib danger" title="Delete" aria-label="Delete" data-act="emp:deldoc" data-id="${d.id}" data-emp="${id}">${ic('trash')}</button>` : ''}` }],
      e.documents, { empty: 'No documents yet', emptyHint: 'Keep NID copies, certificates, appointment letters and contracts here.', emptyIcon: 'file' })}`;
  }
  main.innerHTML = `<div class="card"><div class="prof-head">${avatar(e.full_name, 'lg')}<div class="grow"><h2>${esc(e.full_name)}</h2>
      <div class="sub">${meta(e.designation, e.department, e.unit_name)}</div>
      <div class="chips" style="margin-top:10px">${badge(e.status)}<span class="chip">${esc(e.code)}</span><span class="chip">${esc(e.emp_type)}</span><span class="chip">${yearsSince(e.join_date)} years of service</span>${e.manager_name ? `<span class="chip">Reports to ${esc(e.manager_name)}</span>` : ''}</div></div>
      <div class="toolbar"><button class="btn ghost" data-act="emp:idcard" data-id="${id}">${ic('idcard')}ID card</button>
      ${C.can('lifecycle.manage') ? `<button class="btn ghost" data-act="emp:event" data-id="${id}">${ic('route')}Promote, transfer or exit</button>` : ''}
      ${C.can('employees.manage') ? `<button class="btn" data-act="emp:edit" data-id="${id}">${ic('pencil')}Edit</button><button class="ib danger" title="Delete employee" aria-label="Delete employee" data-act="emp:delete" data-id="${id}">${ic('trash')}</button>` : ''}</div></div></div>
    <div class="card">${tabs('emp:tab', T, S.tab)}<div style="padding-top:14px">${body}</div></div>`;
}

on('emp:tab', (el) => { S.tab = el.dataset.tab; renderProfile($('#main'), Number(C.segs[1])); });
on('emp:delete', async (el) => {
  if (!(await confirmBox('Delete this employee?', 'All of their attendance, leave, claims and documents will be deleted too. If they have left the company, record a resignation instead to keep the history.', { okLabel: 'Delete permanently', danger: true }))) return;
  await api.del(`/api/employees/${el.dataset.id}`);
  toast('Employee deleted');
  location.hash = '#/employees';
});
on('emp:tick', async (el) => { await api.put(`/api/tasks/${el.dataset.id}`, { done: el.checked }); renderProfile($('#main'), Number(el.dataset.emp)); });
on('emp:task', async (el) => {
  const f = [{ k: 'category', l: 'Checklist', t: 'select', o: ['Onboarding', 'Offboarding', 'Other'], req: 1 }, { k: 'owner', l: 'Owner' }, { k: 'task', l: 'Task', req: 1, w: 2 }, { k: 'due_date', l: 'Due date', t: 'date' }];
  modal('Add checklist task', await formHTML(f), { onSave: async () => { const d = readForm(f, $('#modal')); if (!d) return false; await api.post(`/api/employees/${el.dataset.id}/tasks`, d); renderProfile($('#main'), Number(el.dataset.id)); } });
});
on('emp:dl', (el) => api.download(`/api/documents/${el.dataset.id}/download`));
on('emp:deldoc', async (el) => {
  if (!(await confirmBox('Delete document?', 'The file will be removed permanently.', { okLabel: 'Delete', danger: true }))) return;
  await api.del(`/api/documents/${el.dataset.id}`);
  closeModal();
  renderProfile($('#main'), Number(el.dataset.emp));
});
on('emp:upload', async (el) => {
  const f = [{ k: 'title', l: 'Title', req: 1 }, { k: 'doc_type', l: 'Type', t: 'select', o: ['NID', 'Photo', 'CV', 'Certificate', 'Appointment Letter', 'Contract', 'Experience Letter', 'Medical', 'Other'], req: 1 }];
  modal('Upload document', await formHTML(f) + '<label class="fld" style="margin-top:12px"><span>File (max 10 MB)</span><input type="file" id="docFile"></label>', {
    saveLabel: 'Upload',
    onSave: async () => {
      const d = readForm(f, $('#modal'));
      const file = $('#docFile').files[0];
      if (!d) return false;
      if (!file) { toast('Choose a file', 'bad'); return false; }
      if (file.size > 10 * 1024 * 1024) { toast('File is larger than 10 MB', 'bad'); return false; }
      await api.post(`/api/employees/${el.dataset.id}/documents`, { ...d, filename: file.name, content_type: file.type, data: await fileToBase64(file) });
      toast('Uploaded', 'ok');
      renderProfile($('#main'), Number(el.dataset.id));
    },
  });
});

/* ------------------------------------------------------------ career events */
on('emp:event', async (el) => {
  const id = Number(el.dataset.id);
  const e = await api.get(`/api/employees/${id}`);
  const base = [{ k: 'event_type', l: 'Event', t: 'select', o: ['Promotion', 'Transfer', 'Increment', 'Confirmation', 'Resignation', 'Termination', 'Retirement', 'Re-hire'], req: 1 },
    { k: 'effective_date', l: 'Effective date', t: 'date', req: 1, d: new Date().toISOString().slice(0, 10) }];
  const by = {
    Promotion: [{ k: 'designation_id', l: 'New designation', t: 'desig', req: 1 }, { k: 'grade', l: 'New grade (optional)' }, ...(C.can('employees.salary') ? [{ k: 'gross_salary', l: 'New gross salary (optional)', t: 'number' }] : [])],
    Transfer: [{ k: 'unit_id', l: 'New business unit', t: 'unit' }, { k: 'dept_id', l: 'New department', t: 'dept' }, { k: 'manager_id', l: 'New reporting manager', t: 'emp' }],
    Increment: [{ k: 'increment_pct', l: 'Increment %', t: 'number' }, { k: 'gross_salary', l: 'or new gross salary', t: 'number' }],
    Resignation: [{ k: 'exit_date', l: 'Last working day', t: 'date', req: 1 }], Termination: [{ k: 'exit_date', l: 'Last working day', t: 'date', req: 1 }],
    Retirement: [{ k: 'exit_date', l: 'Last working day', t: 'date', req: 1 }], Confirmation: [], 'Re-hire': [],
  };
  const details = { k: 'details', l: 'Details / reason', t: 'textarea', w: 2 };
  let kind = 'Promotion';
  const draw = async () => {
    const vals = {};
    document.querySelectorAll('#evBody [name]').forEach((i) => { vals[i.name] = i.value; });
    vals.event_type = kind;
    $('#evBody').innerHTML = await formHTML([...base, ...by[kind], details], vals);
    $('#f_event_type').addEventListener('change', (ev) => { kind = ev.target.value; draw(); });
  };
  modal(`Career event for ${e.full_name}`, `<div id="evBody"></div><p class="note">Now: ${esc(e.designation || '—')}, ${esc(e.department || '—')}${'gross_salary' in e ? `, gross ${money(e.gross_salary)}` : ''}. Saving updates the employee record and adds the event to their history. Exits also create an offboarding checklist.</p>`, {
    saveLabel: 'Record event',
    onSave: async () => {
      const d = readForm([...base, ...by[kind], details], $('#modal'));
      if (!d) return false;
      if (kind === 'Increment' && !d.increment_pct && !d.gross_salary) { toast('Enter an increment % or the new gross salary', 'bad'); return false; }
      await api.post(`/api/employees/${id}/events`, d);
      toast(`${kind} recorded`, 'ok');
      if (C.segs[1]) { S.tab = 'history'; renderProfile($('#main'), id); }
    },
  });
  await draw();
});

/* ------------------------------------------------------------ ID card */
export function idCard(e) {
  const co = C.user.company;
  printHTML(`ID card ${e.code}`, `<div style="width:2.13in;height:3.37in;border:1px solid #cfd6dd;border-radius:10px;overflow:hidden;text-align:center;margin:0 auto;position:relative;font-family:Segoe UI,Arial,sans-serif">
    <div style="background:linear-gradient(135deg,#0e6b58,#12866e);color:#fff;padding:10px 6px 34px;font-size:12px"><b>${esc(co.name)}</b><br><span style="opacity:.8;font-size:9.5px;letter-spacing:.08em">EMPLOYEE IDENTITY CARD</span></div>
    <div style="width:70px;height:70px;border-radius:50%;background:#d9912b;color:#fff;font-size:24px;font-weight:700;display:grid;place-items:center;margin:-30px auto 6px;border:3px solid #fff">${esc(e.full_name.split(' ').map((w) => w[0]).slice(0, 2).join(''))}</div>
    <div style="font-weight:700;font-size:13px">${esc(e.full_name)}</div><div style="font-size:10.5px;color:#6b7684">${esc(e.designation || '')}</div><div style="font-size:10.5px;color:#6b7684">${esc(e.department || '')}</div>
    <table style="font-size:10px;margin:8px auto 0;text-align:left"><tr><td>ID</td><td><b>${esc(e.code)}</b></td></tr><tr><td>Blood</td><td><b>${esc(e.blood_group || '—')}</b></td></tr><tr><td>Joined</td><td>${fmtDate(e.join_date)}</td></tr><tr><td>Phone</td><td>${esc(e.phone || '')}</td></tr></table>
    <div style="position:absolute;bottom:0;left:0;right:0;background:#0b2621;color:#cfe;font-size:8px;padding:4px">If found, please return to the HR Department</div></div>`);
}
