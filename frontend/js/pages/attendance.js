/** Attendance — daily sheet, monthly register, bulk import from biometric devices. */
import { api } from '../core/api.js';
import { $, addDays, addMonths, avatar, esc, fmtDate, ic, modal, monthName, on, parseDate, plural, tabs, thisMonth, toast, today } from '../core/ui.js';

let C;
const S = { tab: 'daily', date: today(), month: thisMonth(), q: '' };
const ST = [['', '—'], ['P', 'Present'], ['L', 'Late'], ['HD', 'Half day'], ['A', 'Absent'], ['LV', 'On leave'], ['WFH', 'Work from home'], ['OD', 'On duty']];

export async function render(main, ctx) {
  C = ctx;
  const T = [['daily', 'Daily attendance'], ['register', 'Monthly register']];
  if (ctx.can('attendance.manage')) T.push(['import', 'Import from device']);
  main.innerHTML = `${tabs('att:tab', T, S.tab)}<div id="attBody"><div class="empty">Loading…</div></div>`;
  if (S.tab === 'daily') await daily();
  else if (S.tab === 'register') await register();
  else importView();
}
on('att:tab', (el) => { S.tab = el.dataset.tab; render($('#main'), C); });

const hrs = (a, b) => { if (!a || !b) return ''; const [h1, m1] = a.split(':').map(Number), [h2, m2] = b.split(':').map(Number); const m = h2 * 60 + m2 - (h1 * 60 + m1); return m > 0 ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m` : ''; };

async function daily() {
  const d = await api.get('/api/attendance/daily', { date: S.date });
  S.daily = d;
  const edit = C.can('attendance.manage');
  const s = d.summary;
  const rows = d.rows.filter((r) => !S.q || (r.full_name + r.code + (r.department || '')).toLowerCase().includes(S.q.toLowerCase()));
  $('#attBody').innerHTML = `<div class="card" style="margin-top:16px"><div class="card-head">
      <button class="ib" title="Previous" aria-label="Previous" data-act="att:day" data-d="-1">${ic('chev-left')}</button><input type="date" value="${S.date}" data-change="att:date"><button class="ib" title="Next" aria-label="Next" data-act="att:day" data-d="1">${ic('chev-right')}</button>
      <button class="btn ghost sm" data-act="att:today">Today</button><b>${parseDate(S.date).toLocaleDateString('en-GB', { weekday: 'long' })}</b>
      <span class="grow"></span><input class="search" placeholder="Filter by name, ID, department" value="${esc(S.q)}" data-input="att:q">
      ${edit ? `<button class="btn ghost" data-act="att:all">${ic('check-circle')}Mark the rest present</button><button class="btn" data-act="att:save">${ic('save')}Save changes</button>` : ''}</div>
    ${d.holiday ? `<div class="banner" style="margin-bottom:14px">${ic('flag', 17)}<span>${esc(d.holiday)}, a public holiday</span></div>` : d.weekend ? `<div class="banner info" style="margin-bottom:14px">${ic('sun', 17)}<span>Weekly holiday. Attendance is optional; anything recorded counts as extra work.</span></div>` : ''}
    <div class="chips" style="margin-bottom:12px">${ST.slice(1).map(([k, l]) => `<span class="chip s-${k}">${l}<b>${s[k] || 0}</b></span>`).join('')}<span class="chip">Not marked<b>${s.unmarked}</b></span></div>
    <div class="tw"><table class="t"><thead><tr><th>Employee</th><th>Department</th><th>Status</th><th>Check-in</th><th>Check-out</th><th>Worked</th><th>Note</th></tr></thead><tbody>
    ${rows.map((r) => `<tr data-emp="${r.id}"><td><div class="who">${avatar(r.full_name, 'sm')}<span><b>${esc(r.full_name)}</b><small>${esc(r.code)}<i class="sep"></i>${esc(r.designation || '')}</small></span></div></td><td>${esc(r.department || '')}</td>
      <td>${edit ? `<select class="s-${r.status}" data-f="status">${ST.map(([k, l]) => `<option value="${k}" ${k === r.status ? 'selected' : ''}>${l}</option>`).join('')}</select>` : `<b class="s-${r.status}">${esc((ST.find((x) => x[0] === r.status) || ['', '—'])[1])}</b>`}</td>
      <td>${edit ? `<input type="time" value="${r.check_in || ''}" data-f="check_in">` : esc(r.check_in || '')}</td><td>${edit ? `<input type="time" value="${r.check_out || ''}" data-f="check_out">` : esc(r.check_out || '')}</td>
      <td class="nowrap">${hrs(r.check_in, r.check_out)}</td><td>${edit ? `<input value="${esc(r.note || '')}" data-f="note" placeholder="${esc(r.leave_type ? r.leave_type + ' leave' : '')}" style="width:150px">` : esc(r.note || r.leave_type || '')}</td></tr>`).join('') || '<tr><td colspan="7" class="empty">No employees</td></tr>'}
    </tbody></table></div><p class="note">Office hours ${esc(d.work_start)}–${esc(d.work_end)} with ${d.grace} minutes grace. A check-in after the grace period is marked Late automatically. Approved leave appears here as “On leave”.</p></div>`;
  document.querySelectorAll('#attBody tr[data-emp] [data-f]').forEach((i) => i.addEventListener('change', () => { i.closest('tr').dataset.dirty = '1'; if (i.dataset.f === 'status') i.className = 's-' + i.value; }));
}
on('att:day', (el) => { S.date = addDays(S.date, Number(el.dataset.d)); daily(); });
on('att:today', () => { S.date = today(); daily(); });
on('att:date', (el) => { if (el.value) { S.date = el.value; daily(); } });
on('att:q', (el) => { S.q = el.value; clearTimeout(S.t); S.t = setTimeout(daily, 300); });
on('att:all', async () => { const r = await api.post('/api/attendance/mark-all', { date: S.date }); toast(r.marked ? `${plural(r.marked, 'employee')} marked present` : 'Everyone already has attendance for this day', 'ok'); daily(); });
on('att:save', async () => {
  const records = [...document.querySelectorAll('#attBody tr[data-dirty]')].map((tr) => {
    const g = (f) => tr.querySelector(`[data-f="${f}"]`).value;
    return { emp_id: Number(tr.dataset.emp), status: g('status'), check_in: g('check_in'), check_out: g('check_out'), note: g('note') };
  });
  if (!records.length) { toast('No changes to save'); return; }
  await api.put('/api/attendance/daily', { date: S.date, records });
  toast(`${plural(records.length, 'record')} saved`, 'ok');
  daily();
});

async function register() {
  const d = await api.get('/api/attendance/register', { month: S.month });
  $('#attBody').innerHTML = `<div class="card" style="margin-top:16px"><div class="card-head"><button class="ib" title="Previous" aria-label="Previous" data-act="att:mon" data-d="-1">${ic('chev-left')}</button><b>${monthName(S.month)}</b>
      <button class="ib" title="Next" aria-label="Next" data-act="att:mon" data-d="1">${ic('chev-right')}</button><span class="grow"></span>
      <span class="legend-row">${[['P', 'Present'], ['L', 'Late'], ['HD', 'Half day'], ['A', 'Absent'], ['LV', 'Leave'], ['WFH', 'Remote'], ['W', 'Weekend'], ['H', 'Holiday']].map(([k, l]) => `<span><i class="tile s-${k}">${k === 'W' ? '' : k}</i>${l}</span>`).join('')}</span><button class="btn ghost" data-act="att:csv">${ic('download')}Export</button></div>
    <div class="tw"><table class="t reg"><thead><tr><th>Employee</th>${d.days.map((x) => `<th class="s-${x.type}" title="${esc(x.holiday || '')}">${x.day}<br>${x.dow}</th>`).join('')}<th class="tot">P</th><th class="tot">L</th><th class="tot">HD</th><th class="tot">A</th><th class="tot">LV</th><th class="tot">%</th></tr></thead><tbody>
    ${d.rows.map((r) => `<tr><td><b>${esc(r.full_name)}</b><small>${esc(r.code)}</small></td>${d.days.map((x) => { const v = r.cells[x.date]; const k = v || x.type; return `<td class="${k ? 'tile ' : ''}s-${k}" title="${x.date}${v ? ': ' + v : x.holiday ? ': ' + esc(x.holiday) : ''}">${v || ''}</td>`; }).join('')}
      <td class="tot"><b>${r.totals.P || 0}</b></td><td class="tot">${r.totals.L || 0}</td><td class="tot">${r.totals.HD || 0}</td><td class="tot">${r.totals.A || 0}</td><td class="tot">${r.totals.LV || 0}</td><td class="tot"><b>${r.totals.pct || 0}%</b></td></tr>`).join('')}
    </tbody></table></div></div>`;
}
on('att:mon', (el) => { S.month = addMonths(S.month, Number(el.dataset.d)); register(); });
on('att:csv', () => api.download('/api/attendance/export', { month: S.month }));

function importView() {
  $('#attBody').innerHTML = `<div class="card" style="margin-top:16px"><h3>Import attendance</h3>
    <p class="muted" style="margin-top:-4px">Paste rows exported from your fingerprint / face-recognition device or a spreadsheet. One row per employee per day:</p>
    <pre style="background:var(--mute-s);padding:10px 12px;border-radius:8px;font-size:12.5px;overflow-x:auto">employee_id,date,check_in,check_out,status(optional)
ST-1001,${today()},08:55,18:05
ST-1002,${today()},09:31,18:10
ST-1003,${today()},,,A</pre>
    <textarea id="impText" rows="10" style="width:100%;font-family:Consolas,monospace" placeholder="Paste CSV rows here, or choose a .csv file below"></textarea>
    <div class="toolbar" style="margin-top:10px"><input type="file" id="impFile" accept=".csv,.txt"><span class="grow"></span><button class="btn" data-act="att:import">${ic('upload')}Import</button></div>
    <div id="impResult"></div></div>`;
  $('#impFile').addEventListener('change', async (e) => { const f = e.target.files[0]; if (f) $('#impText').value = await f.text(); });
}
on('att:import', async () => {
  const csv = $('#impText').value.trim();
  if (!csv) { toast('Paste or choose a CSV first', 'bad'); return; }
  const r = await api.post('/api/attendance/import', { csv });
  $('#impResult').innerHTML = `<div class="banner ${r.errors.length ? '' : 'info'}" style="margin-top:12px">Imported ${plural(r.imported, 'row')}.${r.errors.length ? ` ${plural(r.errors.length, 'line')} could not be imported:<br>${r.errors.map(esc).join('<br>')}` : ''}</div>`;
  toast(`Imported ${plural(r.imported, 'row')}`, 'ok');
});
