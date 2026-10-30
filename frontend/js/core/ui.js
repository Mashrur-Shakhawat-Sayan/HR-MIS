/**
 * UI toolkit: formatting, event delegation, modal, toasts, forms, tables, badges, tabs.
 *
 * Event delegation: markup uses data-act="name" (click), data-change="name", data-input="name".
 * Handlers are registered with on('name', (el, event) => …). No inline JS is used anywhere,
 * which lets the server send a strict Content-Security-Policy.
 */
import { lookups } from './api.js';
import { icon } from './icons.js';

export const ic = icon;
let currentUser = null;
/** app.js registers the signed-in user so form helpers can scope choices (e.g. a manager's team). */
export const setUser = (u) => { currentUser = u; };

/* ------------------------------------------------------------ formatting */
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pad = (n) => String(n).padStart(2, '0');
export const isoDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const today = () => isoDate(new Date());
export const thisMonth = () => today().slice(0, 7);
export const parseDate = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d || 1); };
export const addDays = (s, n) => { const d = parseDate(s); d.setDate(d.getDate() + n); return isoDate(d); };
export const addMonths = (m, n) => { const d = parseDate(m + '-01'); d.setMonth(d.getMonth() + n); return isoDate(d).slice(0, 7); };
export const fmtDate = (s) => (s ? parseDate(s.slice(0, 10)).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '');
export const fmtShort = (s) => (s ? parseDate(s.slice(0, 10)).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : '');
export const fmtDateTime = (s) => (s ? new Date(s).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
export const monthName = (m) => (m ? parseDate(m + '-01').toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }) : '');
export const num = (n, dp = 0) => (n === null || n === undefined || n === '' ? '' : Number(n).toLocaleString('en-IN', { maximumFractionDigits: dp, minimumFractionDigits: dp }));
export const money = (n) => (n === null || n === undefined || n === '' ? '' : '৳' + Math.round(Number(n)).toLocaleString('en-IN'));
/** plural(3, 'claim') → '3 claims'; plural(1, 'day') → '1 day'. */
export const plural = (n, word, many = word + 's') => `${num(n, Number.isInteger(+n) ? 0 : 1)} ${+n === 1 ? word : many}`;
export const initials = (n) => String(n || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
export const yearsSince = (s) => { if (!s) return 0; const a = parseDate(s), b = new Date(); let y = b.getFullYear() - a.getFullYear(); if (b.getMonth() < a.getMonth() || (b.getMonth() === a.getMonth() && b.getDate() < a.getDate())) y--; return y; };

export function inWords(n) {
  n = Math.round(n || 0);
  if (!n) return 'Zero';
  const a = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
  const b = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];
  const two = (x) => (x < 20 ? a[x] : b[Math.floor(x / 10)] + (x % 10 ? ' ' + a[x % 10] : ''));
  const three = (x) => (x >= 100 ? a[Math.floor(x / 100)] + ' Hundred' + (x % 100 ? ' ' : '') : '') + (x % 100 ? two(x % 100) : '');
  let s = '';
  const cr = Math.floor(n / 1e7); n %= 1e7; const lk = Math.floor(n / 1e5); n %= 1e5; const th = Math.floor(n / 1e3); n %= 1e3;
  if (cr) s += three(cr) + ' Crore '; if (lk) s += two(lk) + ' Lakh '; if (th) s += two(th) + ' Thousand '; if (n) s += three(n);
  return s.trim();
}

const hue = (n) => { let h = 0; for (const c of String(n)) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
export const avatar = (name, cls = '') => `<span class="av ${cls}" style="background:hsl(${hue(name)} 34% 38%)" aria-hidden="true">${esc(initials(name))}</span>`;
/** Join meta details with a hairline divider instead of punctuation: meta('Casual', '3 days'). */
export const meta = (...parts) => parts.filter((p) => p !== null && p !== undefined && p !== '').map((p) => esc(p)).join('<i class="sep"></i>');
export const who = (name, sub, href) => `<${href ? `a href="${href}"` : 'div'} class="who">${avatar(name, 'sm')}<span><b>${esc(name)}</b>${sub ? `<small>${esc(sub)}</small>` : ''}</span></${href ? 'a' : 'div'}>`;

const BADGES = {
  ok: ['Active', 'Approved', 'Paid', 'Hired', 'Completed', 'Assigned', 'Acknowledged', 'Present', 'Yes', 'Done'],
  info: ['Finalized', 'Submitted', 'Scheduled', 'Open', 'In Stock', 'Interview', 'Offer', 'Screening', 'Replied'],
  warn: ['Pending', 'Draft', 'On Notice', 'On Hold', 'Under Repair', 'Probation', 'Not generated', 'Contract', 'Important'],
  bad: ['Rejected', 'Resigned', 'Terminated', 'Damaged', 'Overdue'],
  violet: ['Intern', 'Part-time'],
};
export function badge(v) {
  if (!v) return '';
  const cls = Object.keys(BADGES).find((k) => BADGES[k].includes(v)) || 'mute';
  return `<span class="badge ${cls}">${esc(v)}</span>`;
}
export const stars = (n) => `<span class="stars">${'★'.repeat(n || 0)}<i>${'★'.repeat(5 - (n || 0))}</i></span>`;
export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];

/* ------------------------------------------------------------ events */
const handlers = {};
export const on = (name, fn) => { handlers[name] = fn; };
for (const [evt, attr] of [['click', 'act'], ['change', 'change'], ['input', 'input']]) {
  document.addEventListener(evt, (e) => {
    const el = e.target.closest(`[data-${attr}]`);
    if (!el) return;
    const fn = handlers[el.dataset[attr]];
    if (!fn) return;
    if (evt === 'click' && el.tagName !== 'INPUT') e.preventDefault();
    Promise.resolve(fn(el, e)).catch(showError);
  });
}

/* ------------------------------------------------------------ toasts & modal */
export function toast(msg, type = '') {
  const d = document.createElement('div');
  d.className = type;
  d.innerHTML = icon(type === 'bad' ? 'alert' : type === 'ok' ? 'check-circle' : 'info', 18);
  const span = document.createElement('span');
  span.textContent = msg;
  d.appendChild(span);
  $('#toasts').appendChild(d);
  setTimeout(() => d.remove(), type === 'bad' ? 5200 : 3200);
}
export function showError(e) {
  // Validation and permission messages from the server are expected: show them, but don't log them as errors.
  if (e && typeof e.status === 'number' && e.status > 0 && e.status < 500) console.warn(e.message);
  else console.error(e);
  toast(e?.message || String(e), 'bad');
}

let modalSave = null;
let modalLocked = false;
/** Open the dialog. `locked: true` hides close/cancel and ignores Escape (used for forced password changes). */
export function modal(title, html, { onSave, saveLabel = 'Save', size = '', danger = false, footer, locked = false } = {}) {
  const m = $('#modal');
  modalLocked = locked;
  m.innerHTML = `<div class="mbox ${size}" role="dialog" aria-modal="true" aria-labelledby="mTitle"><div class="mhead"><h3 id="mTitle">${esc(title)}</h3>${locked ? '' : `<button class="x" data-act="modal:close" aria-label="Close">${icon('x', 18)}</button>`}</div>
    <div class="mbody">${html}</div>${onSave ? `<div class="mfoot">${footer || ''}<span class="grow"></span>${locked ? '' : '<button class="btn ghost" data-act="modal:close">Cancel</button>'}<button class="btn ${danger ? 'bad' : ''}" data-act="modal:save">${esc(saveLabel)}</button></div>` : ''}</div>`;
  m.classList.add('open');
  modalSave = onSave;
  const first = m.querySelector('.mbody input:not([type=hidden]):not([type=checkbox]), .mbody select, .mbody textarea');
  if (first) setTimeout(() => first.focus(), 40);
  return m.querySelector('.mbox');
}
export function closeModal() { const m = $('#modal'); m.classList.remove('open'); m.innerHTML = ''; modalSave = null; modalLocked = false; }
on('modal:close', closeModal);
on('modal:save', async (btn) => {
  if (!modalSave) return;
  btn.disabled = true;
  try { if ((await modalSave()) !== false) closeModal(); } catch (e) { showError(e); } finally { btn.disabled = false; }
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modalLocked && $('#modal').classList.contains('open')) closeModal(); });
$('#modal').addEventListener('mousedown', (e) => { if (e.target.id === 'modal' && !modalLocked) closeModal(); });

export function confirmBox(title, message, { okLabel = 'Confirm', danger = false } = {}) {
  return new Promise((resolve) => {
    modal(title, `<p style="margin:0">${message}</p>`, { onSave: () => { resolve(true); }, saveLabel: okLabel, size: 'narrow', danger });
    const m = $('#modal');
    const obs = new MutationObserver(() => { if (!m.classList.contains('open')) { obs.disconnect(); resolve(false); } });
    obs.observe(m, { attributes: true });
  });
}

/* ------------------------------------------------------------ forms
 * Field spec: {k, l, t: text|number|date|month|time|email|select|emp|unit|dept|desig|leave|job|textarea|checkbox|section,
 *              o: options (array | [[value,label]]), req, w: 2|3, hint, d: default, min, max, step, ph}
 */
async function optionsFor(f) {
  switch (f.t) {
    case 'emp': return (await lookups.employees(f.all))
      .filter((e) => !f.team || !currentUser || e.manager_id === currentUser.emp_id)
      .map((e) => [e.id, `${e.full_name} (${e.code})`]);
    case 'unit': return (await lookups.units()).map((u) => [u.id, u.name]);
    case 'dept': return (await lookups.departments()).map((d) => [d.id, d.unit_name ? `${d.name} — ${d.unit_name}` : d.name]);
    case 'desig': return (await lookups.designations()).map((d) => [d.id, `${d.title}${d.grade ? ` (${d.grade})` : ''}`]);
    case 'leave': return (await lookups.leaveTypes()).filter((t) => t.active).map((t) => [t.id, t.name]);
    case 'job': return (await lookups.jobs()).map((j) => [j.id, j.title]);
    default: return (typeof f.o === 'function' ? await f.o() : f.o || []).map((o) => (Array.isArray(o) ? o : [o, o]));
  }
}
const SELECTS = ['select', 'emp', 'unit', 'dept', 'desig', 'leave', 'job'];

export async function formHTML(fields, values = {}, cls = '') {
  const parts = [];
  for (const f of fields) {
    if (f.t === 'section') { parts.push(`<h4>${esc(f.l)}</h4>`); continue; }
    const v = values[f.k] ?? f.d ?? '';
    const id = `f_${f.k}`;
    let input;
    if (SELECTS.includes(f.t)) {
      const opts = await optionsFor(f);
      const hasV = opts.some(([ov]) => String(ov) === String(v));
      input = `<select id="${id}" name="${f.k}">${f.req && hasV ? '' : `<option value="">${f.ph || '— Select —'}</option>`}${!hasV && v !== '' ? `<option value="${esc(v)}" selected>${esc(values[f.k + '_label'] || v)}</option>` : ''}${opts.map(([ov, ol]) => `<option value="${esc(ov)}" ${String(ov) === String(v) ? 'selected' : ''}>${esc(ol)}</option>`).join('')}</select>`;
    } else if (f.t === 'textarea') {
      input = `<textarea id="${id}" name="${f.k}" rows="${f.rows || 3}" placeholder="${esc(f.ph || '')}">${esc(v)}</textarea>`;
    } else if (f.t === 'checkbox') {
      input = `<label class="chk"><input type="checkbox" id="${id}" name="${f.k}" ${v && v !== '0' ? 'checked' : ''}> ${esc(f.cl || 'Yes')}</label>`;
    } else {
      const type = f.t === 'number' ? 'number' : f.t || 'text';
      input = `<input id="${id}" name="${f.k}" type="${type}" value="${esc(v)}" placeholder="${esc(f.ph || '')}"${f.min != null ? ` min="${f.min}"` : ''}${f.max != null ? ` max="${f.max}"` : ''}${type === 'number' ? ` step="${f.step || 'any'}"` : ''}>`;
    }
    parts.push(`<label class="fld${f.w ? ' w' + f.w : ''}"><span>${esc(f.l)}${f.req ? ' *' : ''}</span>${input}${f.hint ? `<span class="hint">${esc(f.hint)}</span>` : ''}</label>`);
  }
  return `<div class="form ${cls}">${parts.join('')}</div>`;
}

/** Read form values; returns null (and focuses the field) when a required value is missing. */
export function readForm(fields, root = document) {
  const out = {};
  for (const f of fields) {
    if (f.t === 'section') continue;
    const el = root.querySelector(`#f_${f.k}`);
    if (!el) continue;
    let v = f.t === 'checkbox' ? el.checked : el.value.trim();
    if (f.t === 'number' && v !== '') v = Number(v);
    if (f.req && (v === '' || v === null)) { toast(`${f.l} is required`, 'bad'); el.focus(); return null; }
    out[f.k] = v === '' ? null : v;
  }
  return out;
}

/* ------------------------------------------------------------ tables */
/**
 * cols: [{k, l, fmt(row) → html, num:true, cls}]  rows: array  opts: {empty, foot(rows) → html, rowAttr(row)}
 */
export function table(cols, rows, opts = {}) {
  if (!rows.length) return emptyState(opts.empty || 'Nothing here yet', opts.emptyHint, opts.emptyIcon);
  const head = cols.map((c) => `<th class="${c.num ? 'num' : ''} ${c.cls || ''}">${esc(c.l)}</th>`).join('');
  const body = rows.map((r) => `<tr ${opts.rowAttr ? opts.rowAttr(r) : ''}>${cols.map((c) => `<td class="${c.num ? 'num' : ''} ${c.cls || ''}">${c.fmt ? c.fmt(r) : esc(r[c.k])}</td>`).join('')}</tr>`).join('');
  return `<div class="tw"><table class="t ${opts.cls || ''}"><thead><tr>${head}</tr></thead><tbody>${body}</tbody>${opts.foot ? `<tfoot>${opts.foot(rows)}</tfoot>` : ''}</table></div>`;
}

export const emptyState = (title, hint = '', iconName = 'inbox') => `<div class="empty">${icon(iconName, 22)}<b>${esc(title)}</b>${hint ? `<span>${esc(String(hint).trim())}</span>` : ''}</div>`;

export const tabs = (name, list, cur) => `<div class="tabs">${list.map(([k, l]) => `<button class="${k === cur ? 'on' : ''}" data-act="${name}" data-tab="${k}">${esc(l)}</button>`).join('')}</div>`;

/** One cell of the ledger strip. cls 'accent' marks a figure that needs someone's attention. */
export function kpi(label, value, sub = '', cls = '') {
  return `<div class="kpi ${cls}"><small>${esc(label)}</small><b>${value}</b><span>${sub}</span></div>`;
}

export function selectHTML(name, options, current, attrs = '') {
  return `<select ${attrs} data-change="${name}">${options.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return `<option value="${esc(v)}" ${String(v) === String(current) ? 'selected' : ''}>${esc(l)}</option>`; }).join('')}</select>`;
}

/** Debounce helper for search boxes. */
export function debounce(fn, ms = 250) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

/** Read a File as base64 (without the data: prefix). */
export const fileToBase64 = (file) => new Promise((res, rej) => {
  const r = new FileReader();
  r.onload = () => res(String(r.result).split(',')[1] || '');
  r.onerror = () => rej(new Error('Could not read the file'));
  r.readAsDataURL(file);
});

/** Open a print window with the given body (uses the app stylesheet). */
export function printHTML(title, body) {
  const w = window.open('', '_blank');
  if (!w) { toast('Allow pop-ups to print', 'bad'); return; }
  w.document.write(`<!doctype html><html data-theme="light"><head><meta charset="utf-8"><title>${esc(title)}</title><link rel="stylesheet" href="${location.origin}/css/app.css">
    <style>body{background:#fff;padding:24px} .slip{margin-bottom:28px;page-break-after:always} .slip:last-child{page-break-after:auto} @media print{body{padding:0}.slip{border:0}}</style></head><body>${body}</body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 450);
}
