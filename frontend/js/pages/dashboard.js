/** Dashboard — adapts to the signed-in user's permissions. */
import { api } from '../core/api.js';
import { bars, columns, donut } from '../core/charts.js';
import { avatar, badge, esc, fmtDate, fmtShort, ic, kpi, meta, money, on, parseDate, plural, toast } from '../core/ui.js';

let C;

const greeting = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; };
const dateTile = (s) => `<span class="date-tile"><b>${parseDate(s).getDate()}</b><small>${parseDate(s).toLocaleDateString('en-GB', { month: 'short' })}</small></span>`;

export async function render(main, ctx) {
  C = ctx;
  const d = await api.get('/api/dashboard');
  const longDate = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
  ctx.setTitle(d.me ? `${greeting()}, ${d.me.full_name.split(' ')[0]}` : 'Dashboard', `${longDate}${d.holiday ? `, ${d.holiday}` : !d.workday ? ', weekly holiday' : ''}`);
  const parts = [];

  // personal strip
  if (d.me) {
    const t = d.my_today;
    const leave = (d.my_leave || []).filter((b) => b.remaining !== null);
    parts.push(`<div class="card"><div class="clock">${avatar(d.me.full_name, 'lg')}
      <div class="grow" style="min-width:220px"><div class="hello"><h2>${esc(d.me.full_name)}</h2></div>
        <div class="muted">${meta(d.me.designation, d.me.department, d.me.code)}</div>
        <div class="chips" style="margin-top:10px">${leave.map((b) => `<span class="chip">${esc(b.leave_type)} <b>${b.remaining}</b> left</span>`).join('')}
          ${d.my_pending ? `<span class="chip">${d.my_pending} leave request${d.my_pending > 1 ? 's' : ''} pending</span>` : ''}</div></div>
      <div style="display:flex;flex-direction:column;gap:10px;align-items:flex-end">
        ${!d.workday ? `<span class="banner info">${ic('sun', 17)}<span>${esc(d.holiday || 'Weekly holiday')}. No check-in needed.</span></span>`
          : t && t.check_in ? `<div class="r"><small class="muted">Checked in at</small><div class="clock"><span class="time">${t.check_in}</span>${t.check_out ? `<span class="muted">out ${t.check_out}</span>` : `<button class="btn ghost" data-act="dash:clock" data-a="out">${ic('logout')}Check out</button>`}</div></div>`
          : `<button class="btn" data-act="dash:clock" data-a="in">${ic('login')}Check in now</button>`}
        <div class="chips"><a class="btn ghost sm" href="#/me/leave">${ic('sun')}Apply for leave</a><a class="btn ghost sm" href="#/me/pay">${ic('wallet')}Payslips</a></div></div></div></div>`);
  }

  if (d.kpi) {
    const k = d.kpi;
    const pending = (d.approvals.leave?.length || 0) + (d.approvals.claims?.length || 0) + (d.approvals.loans?.length || 0);
    const cells = [
      kpi(k.team_only ? 'People in my team' : 'Active employees', k.headcount, k.team_only ? 'direct reports' : `${k.units} business units, ${k.departments} departments`),
      kpi('Present today', d.workday ? `${k.present}<small> of ${k.headcount}</small>` : '—', d.workday ? `${k.late} late, ${k.on_leave} on leave` : esc(d.holiday || 'Weekly holiday')),
      kpi('Waiting for your decision', pending, pending ? [d.approvals.leave?.length && `${d.approvals.leave.length} leave`, d.approvals.claims?.length && plural(d.approvals.claims.length, 'claim'), d.approvals.loans?.length && plural(d.approvals.loans.length, 'loan')].filter(Boolean).join(', ') : 'Nothing to approve', pending ? 'accent' : ''),
    ];
    if (k.monthly_gross !== undefined) cells.push(kpi('Monthly gross payroll', money(k.monthly_gross), k.last_payroll ? `Last run ${k.last_payroll.month}, ${k.last_payroll.status.toLowerCase()}` : 'No payroll run yet'));
    if (k.joiners_month !== undefined) cells.push(kpi('Joined this month', k.joiners_month, `${k.leavers_year} left this year`));
    if (k.open_jobs !== undefined) cells.push(kpi('Open positions', k.vacancies, `${k.open_jobs} job openings, ${k.pipeline} candidates`));
    parts.push(`<div class="kpis">${cells.join('')}</div>`);

    parts.push(`<div class="grid2"><div class="card"><div class="card-head"><h3>Attendance, last 7 working days</h3><span class="grow"></span>${ctx.canAny(['attendance.view_all', 'team.view']) ? `<a class="btn ghost sm" href="#/attendance">Open register</a>` : ''}</div>
        ${columns(d.trend.map((x) => ({ label: fmtShort(x.date), value: x.pct })), { suffix: '%', max: 100, target: 95 })}</div>
      <div class="card"><h3>Headcount by department</h3>${bars(d.by_department.map((x) => ({ label: x.name, value: x.n })))}</div></div>`);

    const leaveA = (d.approvals.leave || []).map((l) => `<li>${avatar(l.full_name, 'sm')}<div class="grow"><b>${esc(l.full_name)}</b><small>${meta(`${l.leave_type} leave`, `${fmtShort(l.from_date)}${l.to_date !== l.from_date ? ' to ' + fmtShort(l.to_date) : ''}`, `${l.days} day${l.days === 1 ? '' : 's'}`)}</small></div>
      <button class="ib good" title="Approve" aria-label="Approve" data-act="dash:leave" data-id="${l.id}" data-d="Approved">${ic('check')}</button><button class="ib danger" title="Reject" aria-label="Reject" data-act="dash:leave" data-id="${l.id}" data-d="Rejected">${ic('x')}</button></li>`).join('');
    const claimA = (d.approvals.claims || []).map((c) => `<li>${avatar(c.full_name, 'sm')}<div class="grow"><b>${esc(c.full_name)}</b><small>${meta(`${c.category} claim`, money(c.amount), fmtShort(c.claim_date))}</small></div>
      <button class="ib good" title="Approve" aria-label="Approve" data-act="dash:claim" data-id="${c.id}" data-d="Approved">${ic('check')}</button><button class="ib danger" title="Reject" aria-label="Reject" data-act="dash:claim" data-id="${c.id}" data-d="Rejected">${ic('x')}</button></li>`).join('');
    const loanA = (d.approvals.loans || []).map((l) => `<li>${avatar(l.full_name, 'sm')}<div class="grow"><b>${esc(l.full_name)}</b><small>${meta(`${l.loan_type} request`, money(l.principal))}</small></div><a class="btn sm ghost" href="#/loans">Review</a></li>`).join('');

    parts.push(`<div class="grid3">
      <div class="card"><h3>Your approvals</h3><ul class="list">${leaveA + claimA + loanA || `<li><div class="empty" style="padding:18px 0;width:100%">${ic('check-circle', 22)}<b>You're all caught up</b><span>New leave and claim requests will appear here.</span></div></li>`}</ul></div>
      <div class="card"><h3>Workforce mix</h3>${donut(d.by_gender.map((x) => ({ label: x.name, value: x.n })))}
        <div class="sec">Employment type</div><div class="chips">${d.by_type.map((x) => `<span class="chip">${esc(x.name)} <b>${x.n}</b></span>`).join('')}</div>
        ${d.open_tasks !== undefined && d.open_tasks ? `<div class="sec">Checklists</div><a href="#/lifecycle" class="link">${d.open_tasks} onboarding or offboarding task${d.open_tasks > 1 ? 's are' : ' is'} still open</a>` : ''}</div>
      <div class="card"><h3>Upcoming holidays</h3>${holidayList(d.holidays)}</div></div>`);
  }

  parts.push(`<div class="grid2e"><div class="card"><div class="card-head"><h3>Notice board</h3><span class="grow"></span><a href="#/notices" class="btn ghost sm">All notices</a></div>
      ${d.notices.map((n) => `<div class="notice ${n.priority === 'Important' ? 'imp' : ''}"><b>${esc(n.title)}</b><small>${meta(fmtDate(n.posted_on), n.audience)}${n.priority === 'Important' ? ' ' + badge('Important') : ''}</small><p>${esc(n.body || '')}</p></div>`).join('') || `<div class="empty">${ic('megaphone', 22)}<b>No notices right now</b></div>`}</div>
    ${d.celebrations ? `<div class="card"><h3>Celebrations this month</h3><ul class="list">${d.celebrations.map((c) => `<li>${avatar(c.name, 'sm')}<div class="grow"><b>${esc(c.name)}</b><small>${c.kind === 'Birthday' ? 'Birthday' : `${c.years}-year work anniversary`} on ${fmtShort(new Date().getFullYear() + c.date.slice(4))}</small></div>${ic(c.kind === 'Birthday' ? 'cake' : 'award', 20, 'muted')}</li>`).join('') || `<li class="muted">No birthdays or anniversaries this month.</li>`}</ul></div>`
      : `<div class="card"><h3>Upcoming holidays</h3>${holidayList(d.holidays)}</div>`}</div>`);

  main.innerHTML = parts.join('');
}

function holidayList(list) {
  return `<ul class="list">${list.map((h) => `<li>${dateTile(h.date)}<div class="grow"><b>${esc(h.name)}</b><small>${meta(parseDate(h.date).toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric' }), h.type)}</small></div></li>`).join('') || '<li class="muted">No upcoming holidays are on the calendar.</li>'}</ul>`;
}

on('dash:clock', async (el) => {
  const r = await api.post('/api/attendance/clock', { action: el.dataset.a });
  toast(`${el.dataset.a === 'in' ? 'Checked in' : 'Checked out'} at ${r.time}`, 'ok');
  render(document.getElementById('main'), C);
});
on('dash:leave', async (el) => {
  await api.post(`/api/leave/requests/${el.dataset.id}/decision`, { decision: el.dataset.d });
  toast(`Leave ${el.dataset.d.toLowerCase()}`, 'ok');
  C.refreshNav();
  render(document.getElementById('main'), C);
});
on('dash:claim', async (el) => {
  await api.post(`/api/claims/${el.dataset.id}/decision`, { status: el.dataset.d });
  toast(`Claim ${el.dataset.d.toLowerCase()}`, 'ok');
  C.refreshNav();
  render(document.getElementById('main'), C);
});
