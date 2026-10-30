/** Recruitment — job openings and a candidate pipeline board with one-click onboarding. */
import { api } from '../core/api.js';
import { crudView, mountCrud } from '../core/crud.js';
import { $, badge, esc, fmtDate, formHTML, ic, modal, money, on, readForm, stars, tabs, toast } from '../core/ui.js';
import { editEmployee } from './employees.js';

let C;
const S = { tab: 'pipeline', job: '' };
const STAGES = ['Applied', 'Screening', 'Interview', 'Offer', 'Hired', 'Rejected'];
const CAND_F = [{ k: 'name', l: 'Candidate name', req: 1 }, { k: 'job_id', l: 'Applied for', t: 'job', req: 1 }, { k: 'phone', l: 'Mobile' }, { k: 'email', l: 'Email', t: 'email' },
  { k: 'source', l: 'Source', t: 'select', o: ['Bdjobs', 'LinkedIn', 'Referral', 'Walk-in', 'Campus', 'Company website', 'Other'] }, { k: 'expected_salary', l: 'Expected salary (৳)', t: 'number' },
  { k: 'stage', l: 'Stage', t: 'select', o: STAGES, req: 1, d: 'Applied' }, { k: 'rating', l: 'Rating (1–5)', t: 'number', min: 1, max: 5 },
  { k: 'interview_date', l: 'Interview date', t: 'date' }, { k: 'notes', l: 'Notes', t: 'textarea', w: 2 }];

export async function render(main, ctx) {
  C = ctx;
  main.innerHTML = `${tabs('rec:tab', [['pipeline', 'Candidate pipeline'], ['jobs', 'Job openings'], ['all', 'All candidates']], S.tab)}<div id="recBody" style="margin-top:16px"></div>`;
  const body = $('#recBody');
  const manage = ctx.can('recruitment.manage');
  if (S.tab === 'jobs') {
    return mountCrud(body, crudView({
      id: 'jobs', endpoint: '/api/jobs', title: 'Job openings', single: 'Job opening', canManage: manage,
      filters: [{ k: 'status', all: 'All statuses', o: ['Open', 'On Hold', 'Closed'] }],
      fields: [{ k: 'title', l: 'Position', req: 1, w: 2 }, { k: 'dept_id', l: 'Department', t: 'dept' }, { k: 'unit_id', l: 'Business unit', t: 'unit' }, { k: 'vacancies', l: 'Vacancies', t: 'number', min: 1, d: 1 },
        { k: 'emp_type', l: 'Employment type', t: 'select', o: ['Permanent', 'Contract', 'Intern', 'Part-time'], d: 'Permanent' }, { k: 'salary_range', l: 'Salary range (৳)' },
        { k: 'posted_on', l: 'Posted on', t: 'date' }, { k: 'deadline', l: 'Application deadline', t: 'date' }, { k: 'status', l: 'Status', t: 'select', o: ['Open', 'On Hold', 'Closed'], req: 1, d: 'Open' },
        { k: 'description', l: 'Job description', t: 'textarea', w: 2, rows: 5 }],
      cols: [{ l: 'Position', fmt: (j) => `<b>${esc(j.title)}</b><br><small class="muted">${esc(j.department || '')}<i class="sep"></i>${esc(j.unit_name || '')}</small>` }, { l: 'Vacancies', num: 1, k: 'vacancies' },
        { l: 'Applicants', num: 1, k: 'applicants' }, { l: 'Hired', num: 1, k: 'hired' }, { l: 'Salary', k: 'salary_range' }, { l: 'Deadline', fmt: (j) => fmtDate(j.deadline) }, { l: 'Status', fmt: (j) => badge(j.status) }],
    }));
  }
  if (S.tab === 'all') {
    return mountCrud(body, crudView({
      id: 'cands', endpoint: '/api/candidates', title: 'Candidates', single: 'Candidate', canManage: manage, fields: CAND_F,
      filters: [{ k: 'stage', all: 'All stages', o: STAGES }],
      cols: [{ l: 'Candidate', fmt: (c) => `<b>${esc(c.name)}</b><br><small class="muted">${esc(c.email || c.phone || '')}</small>` }, { l: 'Position', k: 'job_title' }, { l: 'Source', k: 'source' },
        { l: 'Rating', fmt: (c) => stars(c.rating) }, { l: 'Expected', num: 1, fmt: (c) => money(c.expected_salary) }, { l: 'Stage', fmt: (c) => badge(c.stage) }],
    }));
  }
  const [cands, jobs] = await Promise.all([api.get('/api/candidates', { job_id: S.job }), api.get('/api/jobs')]);
  body.innerHTML = `<div class="toolbar" style="margin-bottom:12px"><select data-change="rec:job"><option value="">All positions</option>${jobs.items.map((j) => `<option value="${j.id}" ${String(j.id) === String(S.job) ? 'selected' : ''}>${esc(j.title)} (${j.applicants})</option>`).join('')}</select>
    <span class="grow"></span>${manage ? `<button class="btn" data-act="rec:add">${ic('user-plus')}Add candidate</button>` : ''}</div>
    <div class="board">${STAGES.map((s, i) => { const list = cands.items.filter((c) => c.stage === s); return `<div class="col"><h4>${s}<span>${list.length}</span></h4>${list.map((c) => `<div class="kc"><b>${esc(c.name)}</b><span class="muted">${esc(c.job_title || '')}</span>
      <div>${stars(c.rating)}<i class="sep"></i>${esc(c.source || '')}</div>${c.expected_salary ? `<div class="muted">Expects ${money(c.expected_salary)}</div>` : ''}${c.interview_date && s === 'Interview' ? `<div class="chips" style="margin-top:4px"><span class="chip">${ic('calendar', 14)}Interview ${fmtDate(c.interview_date)}</span></div>` : ''}
      ${manage ? `<div class="acts">${i > 0 && i < 5 ? `<button class="ib" title="Move back" aria-label="Move back" data-act="rec:move" data-id="${c.id}" data-s="${STAGES[i - 1]}">${ic('chev-left')}</button>` : ''}${i < 4 ? `<button class="ib" title="Move forward" aria-label="Move forward" data-act="rec:move" data-id="${c.id}" data-s="${STAGES[i + 1]}">${ic('chev-right')}</button><button class="ib danger" title="Reject" aria-label="Reject" data-act="rec:move" data-id="${c.id}" data-s="Rejected">${ic('x')}</button>` : ''}
        ${s === 'Hired' && C.can('employees.manage') ? `<button class="btn sm" data-act="rec:hire" data-id="${c.id}">${ic('user-plus')}Onboard</button>` : ''}<button class="ib" title="Edit" aria-label="Edit" data-act="rec:edit" data-id="${c.id}">${ic('pencil')}</button></div>` : ''}</div>`).join('')}</div>`; }).join('')}</div>`;
  S.cands = cands.items;
}
on('rec:tab', (el) => { S.tab = el.dataset.tab; render($('#main'), C); });
on('rec:job', (el) => { S.job = el.value; render($('#main'), C); });
on('rec:move', async (el) => { await api.post(`/api/candidates/${el.dataset.id}/stage`, { stage: el.dataset.s }); render($('#main'), C); });
async function candidateForm(id) {
  const row = id ? S.cands.find((c) => c.id === id) : { job_id: S.job, stage: 'Applied' };
  modal(id ? 'Edit candidate' : 'Add candidate', await formHTML(CAND_F, row), {
    onSave: async () => { const d = readForm(CAND_F, $('#modal')); if (!d) return false; if (id) await api.put(`/api/candidates/${id}`, d); else await api.post('/api/candidates', d); toast('Candidate saved', 'ok'); render($('#main'), C); },
  });
}
on('rec:add', () => candidateForm());
on('rec:edit', (el) => candidateForm(Number(el.dataset.id)));
on('rec:hire', (el) => {
  const c = S.cands.find((x) => x.id === Number(el.dataset.id));
  editEmployee(null, { full_name: c.name, phone: c.phone, email: c.email, dept_id: c.dept_id, unit_id: c.unit_id, gross_salary: c.expected_salary,
    emp_type: c.emp_type === 'Intern' ? 'Intern' : 'Probation', join_date: new Date().toISOString().slice(0, 10) }, (emp) => { toast(`${emp.full_name} onboarded as ${emp.code}`, 'ok'); location.hash = `#/employees/${emp.id}`; });
});
