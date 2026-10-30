/** Users & roles — accounts, role assignment, password resets, permission matrix. */
import { api } from '../core/api.js';
import { $, badge, esc, fmtDateTime, formHTML, ic, modal, on, readForm, table, tabs, toast } from '../core/ui.js';

let C;
const S = { tab: 'users' };

export async function render(main, ctx) {
  C = ctx;
  const roles = await api.get('/api/roles');
  S.roles = roles;
  main.innerHTML = `${tabs('usr:tab', [['users', 'User accounts'], ['matrix', 'Roles & permissions']], S.tab)}<div id="usrBody" style="margin-top:16px"></div>`;
  if (S.tab === 'matrix') return matrix();
  const { items } = await api.get('/api/users');
  S.users = items;
  const label = (k) => roles.roles.find((r) => r.key === k)?.label || k;
  $('#usrBody').innerHTML = `<div class="card"><div class="card-head"><h3>User accounts</h3><span class="muted">${items.length}</span><span class="grow"></span><button class="btn" data-act="usr:new">${ic('user-plus')}New user</button></div>
    ${table([{ l: 'Username', fmt: (u) => `<b>${esc(u.username)}</b>` }, { l: 'Employee', fmt: (u) => (u.emp_id ? `<a class="link" href="#/employees/${u.emp_id}">${esc(u.full_name)}</a> <small class="muted">${esc(u.emp_code)}</small>` : '<span class="muted">Not linked</span>') },
      { l: 'Role', fmt: (u) => esc(label(u.role)) }, { l: 'Status', fmt: (u) => badge(u.is_active ? 'Active' : 'Disabled') + (u.must_change_pw ? ' <span class="badge warn">must change password</span>' : '') },
      { l: 'Last sign-in', fmt: (u) => (u.last_login ? fmtDateTime(u.last_login) : '<span class="muted">Never</span>') },
      { l: '', cls: 'r nowrap', fmt: (u) => `<button class="btn sm ghost" data-act="usr:edit" data-id="${u.id}">Edit</button> <button class="btn sm ghost" data-act="usr:pw" data-id="${u.id}">Reset password</button>` }], items)}
    <p class="note">Every employee can be given a login. Employees only see their own records (My Workspace). Line managers also see and approve their direct reports. Default demo passwords should be changed before real use.</p></div>`;
}
on('usr:tab', (el) => { S.tab = el.dataset.tab; render($('#main'), C); });

const roleOpts = () => S.roles.roles.map((r) => [r.key, r.label]);
on('usr:new', async () => {
  const f = [{ k: 'username', l: 'Username', req: 1, hint: 'e.g. employee ID or first.last' }, { k: 'role', l: 'Role', t: 'select', o: roleOpts(), req: 1, d: 'employee' },
    { k: 'emp_id', l: 'Linked employee', t: 'emp', w: 2, hint: 'Required for self-service and line-manager access' },
    { k: 'password', l: 'Temporary password', t: 'text', req: 1, hint: 'At least 8 characters with letters and numbers. The user must change it at first sign-in.', w: 2 }];
  modal('New user', await formHTML(f), { saveLabel: 'Create user', onSave: async () => { const d = readForm(f, $('#modal')); if (!d) return false; await api.post('/api/users', d); toast('User created', 'ok'); render($('#main'), C); } });
});
on('usr:edit', async (el) => {
  const u = S.users.find((x) => x.id === Number(el.dataset.id));
  const f = [{ k: 'role', l: 'Role', t: 'select', o: roleOpts(), req: 1 }, { k: 'emp_id', l: 'Linked employee', t: 'emp', all: 1 }, { k: 'is_active', l: 'Status', t: 'checkbox', cl: 'Account active' }];
  modal(`Edit ${u.username}`, await formHTML(f, u), { onSave: async () => { const d = readForm(f, $('#modal')); if (!d) return false; await api.put(`/api/users/${u.id}`, d); toast('User updated', 'ok'); render($('#main'), C); } });
});
on('usr:pw', async (el) => {
  const u = S.users.find((x) => x.id === Number(el.dataset.id));
  const f = [{ k: 'password', l: 'New temporary password', req: 1, w: 2, hint: 'The user will be asked to change it after signing in. All their sessions are signed out.' }];
  modal(`Reset password — ${u.username}`, await formHTML(f), { saveLabel: 'Reset password', size: 'narrow', onSave: async () => { const d = readForm(f, $('#modal')); if (!d) return false; await api.post(`/api/users/${u.id}/reset-password`, d); toast('Password reset', 'ok'); render($('#main'), C); } });
});

function matrix() {
  const { roles, permissions } = S.roles;
  const groups = {};
  Object.keys(permissions).forEach((p) => (groups[p.split('.')[0]] ||= []).push(p));
  $('#usrBody').innerHTML = `<div class="card"><h3>Permission matrix</h3><div class="tw"><table class="t"><thead><tr><th>Permission</th>${roles.map((r) => `<th class="c">${esc(r.label)}</th>`).join('')}</tr></thead><tbody>
    ${Object.entries(groups).map(([g, list]) => `<tr><td colspan="${roles.length + 1}" style="background:#fafbfc;font-weight:650;text-transform:capitalize">${esc(g)}</td></tr>` +
      list.map((p) => `<tr><td>${esc(permissions[p])}<br><small class="muted mono">${esc(p)}</small></td>${roles.map((r) => `<td class="c">${r.permissions.includes(p) ? `<span style="color:var(--ok)">${ic('check', 16)}</span>` : '<span class="muted" aria-label="not granted">–</span>'}</td>`).join('')}</tr>`).join('')).join('')}
    </tbody></table></div><p class="note">Roles are defined in backend/core/rbac.py. See docs/08-roles-and-permissions.md to add or change a role.</p></div>`;
}
