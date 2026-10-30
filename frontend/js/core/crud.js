/**
 * Generic list + form page for any backend Resource.
 *
 *   crudView({ id, endpoint, title, single, fields, cols, filters, canManage, rowActions, toolbar, prefill })
 *
 * Returns {html(), refresh(container)} — pages embed it and call refresh to (re)load.
 */
import { api } from './api.js';
import { $, closeModal, confirmBox, debounce, esc, formHTML, ic, modal, on, readForm, table, toast } from './ui.js';

const views = {};

export function crudView(cfg) {
  const state = { q: '', filters: { ...(cfg.initialFilters || {}) }, rows: [] };
  views[cfg.id] = { cfg, state, _load: () => load() };

  async function load() {
    const params = { q: state.q, ...state.filters, ...(cfg.params || {}) };
    const data = await api.get(cfg.endpoint, params);
    state.rows = data.items;
    draw();
  }

  function draw() {
    const el = document.getElementById(`crud_${cfg.id}`);
    if (!el) return;
    const cols = [...cfg.cols];
    if (cfg.canManage || cfg.rowActions) {
      cols.push({ l: '', cls: 'r nowrap', fmt: (r) => `${cfg.rowActions ? cfg.rowActions(r) : ''}${cfg.canManage && (!cfg.canEdit || cfg.canEdit(r)) ? `<button class="ib" title="Edit" aria-label="Edit" data-act="crud:edit" data-view="${cfg.id}" data-id="${r.id}">${ic('pencil')}</button><button class="ib danger" title="Delete" aria-label="Delete" data-act="crud:del" data-view="${cfg.id}" data-id="${r.id}">${ic('trash')}</button>` : ''}` });
    }
    el.innerHTML = table(cols, state.rows, { empty: cfg.empty || `No ${cfg.title.toLowerCase()} yet`, emptyHint: cfg.canManage ? `Use “Add ${cfg.single.toLowerCase()}” to create the first one.` : '', emptyIcon: cfg.icon, rowAttr: cfg.rowAttr });
    const cnt = document.getElementById(`crudn_${cfg.id}`);
    if (cnt) cnt.textContent = `${state.rows.length} ${state.rows.length === 1 ? 'record' : 'records'}`;
  }

  return {
    state,
    html() {
      const filters = (cfg.filters || []).map((f) => `<select data-change="crud:filter" data-view="${cfg.id}" data-key="${f.k}"><option value="">${esc(f.all)}</option>${f.o.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return `<option value="${esc(v)}" ${String(state.filters[f.k] ?? '') === String(v) ? 'selected' : ''}>${esc(l)}</option>`; }).join('')}</select>`).join('');
      return `<div class="card"><div class="card-head">${cfg.hideTitle ? '' : `<h3>${esc(cfg.title)}</h3>`}<span class="count" id="crudn_${cfg.id}"></span><span class="grow"></span>
        <label class="search-box">${ic('search')}<input placeholder="Search ${esc(cfg.title.toLowerCase())}" aria-label="Search" value="${esc(state.q)}" data-input="crud:search" data-view="${cfg.id}"></label>${filters}${cfg.toolbar || ''}
        ${cfg.canManage ? `<button class="btn" data-act="crud:edit" data-view="${cfg.id}">${ic('plus')}Add ${esc(cfg.single.toLowerCase())}</button>` : ''}</div>
        <div id="crud_${cfg.id}"><div class="empty">Loading…</div></div></div>`;
    },
    load,
    draw,
  };
}

const searchLater = debounce((id) => views[id]._load(), 250);

function view(el) { const v = views[el.dataset.view]; return v; }

on('crud:search', (el) => { const v = view(el); v.state.q = el.value; searchLater(el.dataset.view); });
on('crud:filter', (el) => { const v = view(el); v.state.filters[el.dataset.key] = el.value; v._load(); });

on('crud:edit', async (el) => {
  const { cfg, state } = view(el);
  const id = el.dataset.id ? Number(el.dataset.id) : null;
  const row = id ? state.rows.find((r) => r.id === id) : { ...(cfg.prefill ? cfg.prefill() : {}) };
  modal(`${id ? 'Edit' : 'Add'} ${cfg.single.toLowerCase()}`, await formHTML(cfg.fields, row), {
    size: cfg.fields.length > 8 ? 'wide' : '',
    onSave: async () => {
      const data = readForm(cfg.fields, $('#modal'));
      if (!data) return false;
      if (cfg.beforeSave) cfg.beforeSave(data, row);
      if (id) await api.put(`${cfg.endpoint}/${id}`, data); else await api.post(cfg.endpoint, data);
      toast(`${cfg.single} ${id ? 'updated' : 'added'}`, 'ok');
      await views[el.dataset.view]._load();
      if (cfg.afterSave) cfg.afterSave();
    },
  });
});

on('crud:del', async (el) => {
  const { cfg } = view(el);
  if (!(await confirmBox(`Delete this ${cfg.single.toLowerCase()}?`, 'It will be removed permanently. This cannot be undone.', { okLabel: 'Delete', danger: true }))) return;
  await api.del(`${cfg.endpoint}/${el.dataset.id}`);
  closeModal();
  toast(`${cfg.single} deleted`);
  await views[el.dataset.view]._load();
  if (cfg.afterSave) cfg.afterSave();
});

/** Mount helper: renders the view's shell into `container` and loads data. */
export async function mountCrud(container, v, before = '', after = '') {
  container.innerHTML = before + v.html() + after;
  await v.load();
}
