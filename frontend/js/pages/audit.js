/** Audit trail — every sign-in and change, with who/when/what. */
import { api } from '../core/api.js';
import { $, badge, esc, fmtDateTime, ic, modal, on, table } from '../core/ui.js';

let C;
const S = { q: '', entity: '', action: '', from: '', to: '' };

export async function render(main, ctx) {
  C = ctx;
  const d = await api.get('/api/audit', S);
  S.items = d.items;
  main.innerHTML = `<div class="card"><div class="card-head"><input class="search" placeholder="Search summary or details" value="${esc(S.q)}" data-change="aud:f" data-k="q">
      <select data-change="aud:f" data-k="entity"><option value="">All records</option>${d.entities.map((e) => `<option ${e === S.entity ? 'selected' : ''}>${esc(e)}</option>`).join('')}</select>
      <select data-change="aud:f" data-k="action"><option value="">All actions</option>${['login', 'create', 'update', 'delete', 'export'].map((a) => `<option ${a === S.action ? 'selected' : ''}>${a}</option>`).join('')}</select>
      <label class="inl">From <input type="date" value="${S.from}" data-change="aud:f" data-k="from"></label><label class="inl">To <input type="date" value="${S.to}" data-change="aud:f" data-k="to"></label>
      <span class="grow"></span><span class="muted">latest ${d.items.length}</span></div>
    ${table([{ l: 'When', fmt: (a) => `<span class="nowrap">${fmtDateTime(a.ts)}</span>` }, { l: 'User', fmt: (a) => `<b>${esc(a.username || 'system')}</b>` },
      { l: 'Action', fmt: (a) => `<span class="badge ${{ create: 'ok', update: 'info', delete: 'bad', login: 'mute', export: 'violet' }[a.action] || 'mute'}">${esc(a.action)}</span>` },
      { l: 'Record', fmt: (a) => `${esc(a.entity || '')}${a.entity_id ? ` #${a.entity_id}` : ''}` }, { l: 'Summary', k: 'summary' }, { l: 'IP', k: 'ip' },
      { l: '', fmt: (a) => (a.details ? `<button class="ib" title="Show details" aria-label="Show details" data-act="aud:show" data-id="${a.id}">${ic('eye')}</button>` : '') }], d.items, { empty: 'No matching activity' })}</div>`;
}
on('aud:f', (el) => { S[el.dataset.k] = el.value; render($('#main'), C); });
on('aud:show', (el) => {
  const a = S.items.find((x) => x.id === Number(el.dataset.id));
  let pretty = a.details;
  try { pretty = JSON.stringify(JSON.parse(a.details), null, 2); } catch { /* keep raw */ }
  modal(`${a.action[0].toUpperCase() + a.action.slice(1)}: ${a.entity} #${a.entity_id || ''}`, `<p class="muted">${esc(a.summary)}<i class="sep"></i>${esc(a.username)}<i class="sep"></i>${fmtDateTime(a.ts)}</p><pre style="background:var(--mute-s);padding:12px;border-radius:8px;overflow:auto;max-height:420px;font-size:12.5px">${esc(pretty)}</pre>`);
});
