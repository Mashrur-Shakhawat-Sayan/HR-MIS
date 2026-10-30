/** Reports — catalogue of standard HR reports with on-screen preview and CSV export. */
import { api } from '../core/api.js';
import { $, esc, ic, on, plural, thisMonth } from '../core/ui.js';

let C;
const S = { key: null, month: thisMonth(), year: String(new Date().getFullYear()), status: '', period: '' };

export async function render(main, ctx) {
  C = ctx;
  const { items } = await api.get('/api/reports');
  S.items = items;
  if (!S.key || !items.find((r) => r.key === S.key)) S.key = items[0]?.key;
  const groups = {};
  items.forEach((r) => (groups[r.group] ||= []).push(r));
  main.innerHTML = `<div class="grid2" style="grid-template-columns:280px minmax(0,1fr)"><div class="card rep-nav" style="align-self:start">
      ${Object.entries(groups).map(([g, list]) => `<div class="sec">${esc(g)}</div>${list.map((r) => `<a data-act="rep:pick" data-k="${r.key}" class="${r.key === S.key ? 'on' : ''}" href="#/reports">${esc(r.title)}</a>`).join('')}`).join('')}</div>
    <div id="repBody"><div class="card empty">Loading…</div></div></div>`;
  await run();
}

async function run() {
  const r = S.items.find((x) => x.key === S.key);
  if (!r) { $('#repBody').innerHTML = '<div class="card empty">No reports available for your role.</div>'; return; }
  const params = {};
  if (r.params.includes('month')) params.month = S.month;
  if (r.params.includes('year')) params.year = S.year;
  if (r.params.includes('status')) params.status = S.status;
  if (r.params.includes('period')) params.period = S.period;
  const d = await api.get(`/api/reports/${r.key}`, params);
  const ctl = [
    r.params.includes('month') ? `<label class="inl">Month <input type="month" value="${S.month}" data-change="rep:p" data-k="month"></label>` : '',
    r.params.includes('year') ? `<label class="inl">Year <input type="number" value="${S.year}" min="2000" max="2100" style="width:90px" data-change="rep:p" data-k="year"></label>` : '',
    r.params.includes('status') ? `<label class="inl">Employees <select data-change="rep:p" data-k="status"><option value="">Active only</option><option value="all" ${S.status === 'all' ? 'selected' : ''}>Everyone</option></select></label>` : '',
    r.params.includes('period') ? `<label class="inl">Period <input value="${esc(S.period)}" placeholder="all" style="width:100px" data-change="rep:p" data-k="period"></label>` : '',
  ].join('');
  const numeric = d.columns.map((_, i) => d.rows.length > 0 && d.rows.every((row) => row[i] === null || row[i] === '' || typeof row[i] === 'number'));
  $('#repBody').innerHTML = `<div class="card"><div class="card-head"><h3>${esc(d.title)}</h3><span class="count">${plural(d.rows.length, 'row')}</span><span class="grow"></span>${ctl}
      <button class="btn ghost" data-act="rep:print">${ic('printer')}Print</button><button class="btn" data-act="rep:csv">${ic('download')}Export CSV</button></div>
    ${d.rows.length ? `<div class="tw" id="repTable"><table class="t compact"><thead><tr>${d.columns.map((c, i) => `<th class="${numeric[i] ? 'num' : ''}">${esc(c)}</th>`).join('')}</tr></thead>
      <tbody>${d.rows.map((row) => `<tr>${row.map((v, i) => `<td class="${numeric[i] ? 'num' : ''}">${numeric[i] && v !== null && v !== '' ? Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : esc(v ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
      : '<div class="empty"><b>No data for this selection</b></div>'}</div>`;
}
on('rep:pick', (el) => { S.key = el.dataset.k; render($('#main'), C); });
on('rep:p', (el) => { S[el.dataset.k] = el.value; run(); });
on('rep:csv', () => {
  const r = S.items.find((x) => x.key === S.key);
  api.download(`/api/reports/${r.key}`, { format: 'csv', month: r.params.includes('month') ? S.month : '', year: r.params.includes('year') ? S.year : '', status: S.status, period: S.period });
});
on('rep:print', () => {
  const w = window.open('', '_blank');
  if (!w) return;
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(document.querySelector('#repBody h3').textContent)}</title><link rel="stylesheet" href="${location.origin}/css/app.css"><style>body{background:#fff;padding:20px}</style></head>
    <body><h2>${esc(C.user.company.name)}</h2><h3 style="margin:4px 0 14px">${esc(document.querySelector('#repBody h3').textContent)}</h3>${document.getElementById('repTable')?.innerHTML || ''}<p class="muted" style="font-size:11px">Printed ${new Date().toLocaleString('en-GB')} by ${esc(C.user.username)}</p></body></html>`);
  w.document.close();
  setTimeout(() => w.print(), 450);
});
