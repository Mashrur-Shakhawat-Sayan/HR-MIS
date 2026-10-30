/** Settings — company profile, working time, payroll rules, backups and system information. */
import { api } from '../core/api.js';
import { $, esc, ic, num, on, toast } from '../core/ui.js';

let C;
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']; // backend weekday(): Mon = 0

export async function render(main, ctx) {
  C = ctx;
  const [s, info] = await Promise.all([api.get('/api/settings'), api.get('/api/system/info')]);
  const inp = (k, l, type = 'text', hint = '') => `<label class="fld"><span>${l}</span><input data-k="${k}" type="${type}" value="${esc(s[k])}" ${type === 'number' ? 'step="any" min="0"' : ''}>${hint ? `<span class="hint">${hint}</span>` : ''}</label>`;
  main.innerHTML = `<div class="card"><h3>Company profile</h3><div class="sform">${inp('company_name', 'Company name')}${inp('company_short', 'Short name (logo text)')}${inp('company_address', 'Address')}
      ${inp('company_phone', 'Phone')}${inp('company_email', 'HR email', 'email')}${inp('employee_code_prefix', 'Employee ID prefix', 'text', 'ST- gives IDs like ST-1001')}${inp('currency_symbol', 'Currency symbol')}</div></div>
    <div class="card"><h3>Working time & attendance</h3><div class="sform">${inp('work_start', 'Office start', 'time')}${inp('work_end', 'Office end', 'time')}${inp('grace_minutes', 'Late grace (minutes)', 'number')}
      ${inp('late_per_lwp_day', 'Late arrivals per 1 day LWP', 'number', '0 = do not deduct for late arrival')}${inp('probation_months', 'Probation period (months)', 'number')}
      <div class="fld"><span>Weekly holidays</span><div class="chips" style="padding-top:6px">${DAYS.map((d, i) => `<label class="chk"><input type="checkbox" class="wk" value="${i}" ${s.weekend_days.includes(i) ? 'checked' : ''}>${d}</label>`).join('')}</div></div></div></div>
    <div class="card"><h3>Payroll rules</h3><div class="sform">${inp('basic_pct', 'Basic (% of gross)', 'number')}${inp('house_rent_pct', 'House rent (% of gross)', 'number')}${inp('medical_pct', 'Medical (% of gross)', 'number')}
      ${inp('pf_employee_pct', 'PF employee (% of basic)', 'number')}${inp('pf_employer_pct', 'PF employer (% of basic)', 'number')}${inp('tax_pct', 'Income tax TDS (% of gross)', 'number', 'Flat estimate — set per NBR rules')}
      ${inp('tax_min_gross', 'Apply TDS when gross ≥ (৳)', 'number')}${inp('ot_multiplier', 'Overtime multiplier', 'number', 'Labour Act: 2× basic hourly rate')}${inp('ot_divisor_hours', 'Hours per month for OT rate', 'number')}
      ${inp('lwp_divisor_days', 'Days per month for LWP rate', 'number')}${inp('festival_bonus_pct', 'Festival bonus (% of basic)', 'number')}${inp('fiscal_year_start_month', 'Fiscal year starts (month no.)', 'number', 'Bangladesh: 7 (July)')}</div>
      <p class="note">Conveyance = gross − basic − house rent − medical. Changes apply to payroll generated after saving; finalized months are not changed.</p></div>
    <div class="toolbar"><button class="btn" data-act="set:save">${ic('save')}Save settings</button></div>
    <div class="card"><h3>Backup & system</h3><div class="dl"><div><small>Version</small>HR-MIS ${esc(info.version)}, Python ${esc(info.python)}</div><div><small>Database</small><span class="mono" style="font-size:12px">${esc(info.database)}</span></div><div><small>Database size</small>${num(info.db_size_kb)} KB</div>
      ${Object.entries(info.counts).map(([k, v]) => `<div><small>${esc(k.replace('_', ' '))}</small>${num(v)}</div>`).join('')}</div>
      <div class="toolbar" style="margin-top:14px"><button class="btn" data-act="set:dl">${ic('download')}Download backup</button><button class="btn ghost" data-act="set:srv">${ic('save')}Save a backup on the server</button></div>
      ${info.backups.length ? `<div class="sec">Recent server backups (data/backups)</div><div class="chips">${info.backups.map((b) => `<span class="chip mono">${esc(b)}</span>`).join('')}</div>` : ''}
      <p class="note">To restore: stop HR-MIS, replace <span class="mono">data/hrmis.db</span> with a backup file, and start it again. See docs/10-operations.md.</p></div>`;
}
on('set:save', async () => {
  const body = {};
  document.querySelectorAll('#main [data-k]').forEach((i) => { body[i.dataset.k] = i.type === 'number' ? Number(i.value) : i.value; });
  body.weekend_days = [...document.querySelectorAll('#main .wk:checked')].map((x) => Number(x.value));
  await api.put('/api/settings', body);
  toast('Settings saved. Sign in again to refresh the company name everywhere.', 'ok');
});
on('set:dl', async () => { const n = await api.download('/api/system/backup'); toast(`Downloaded ${n}`, 'ok'); });
on('set:srv', async () => { const r = await api.post('/api/system/backup'); toast(`Saved ${r.file}`, 'ok'); render($('#main'), C); });
