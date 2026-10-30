/**
 * Application shell: sign-in, navigation (filtered by permissions), page header, routing,
 * search palette (Ctrl+K), theme switch and the user menu.
 * Each page lives in js/pages/<module>.js and exports `render(main, ctx)`.
 */
import { api, lookups, session } from './core/api.js';
import { $, closeModal, esc, formHTML, ic, initials, modal, on, readForm, setUser, showError, toast } from './core/ui.js';

/* group, route, label, icon, permissions (any-of; null = everyone), page module, palette keywords */
const ROUTES = [
  ['Overview', 'dashboard', 'Dashboard', 'dashboard', null, 'dashboard', 'home summary kpi'],
  ['My workspace', 'me/profile', 'My profile', 'user', ['self.profile'], 'me', 'details address phone'],
  ['My workspace', 'me/attendance', 'My attendance', 'clock', ['self.attendance'], 'me', 'check in out clock'],
  ['My workspace', 'me/leave', 'My leave', 'sun', ['self.leave'], 'me', 'apply holiday vacation balance'],
  ['My workspace', 'me/pay', 'My payslips', 'wallet', ['self.payroll'], 'me', 'salary payslip loan advance'],
  ['My workspace', 'me/claims', 'My claims', 'receipt', ['self.claims'], 'me', 'expense reimbursement'],
  ['People', 'employees', 'Employees', 'users', ['employees.view', 'team.view'], 'employees', 'staff directory people team'],
  ['People', 'organization', 'Organization', 'building', ['org.view'], 'organization', 'units departments designations grades chart'],
  ['People', 'lifecycle', 'Lifecycle', 'route', ['lifecycle.view'], 'lifecycle', 'promotion transfer onboarding offboarding disciplinary confirmation'],
  ['Time and leave', 'attendance', 'Attendance', 'calendar-check', ['attendance.view_all', 'team.view'], 'attendance', 'register daily import device'],
  ['Time and leave', 'leave', 'Leave', 'sun', ['leave.view_all', 'leave.approve'], 'leave', 'approve requests balances types'],
  ['Time and leave', 'holidays', 'Holidays', 'flag', null, 'holidays', 'calendar public eid'],
  ['Compensation', 'payroll', 'Payroll', 'wallet', ['payroll.view'], 'payroll', 'salary payslip bank advice pf bonus'],
  ['Compensation', 'loans', 'Loans and advances', 'landmark', ['loans.view'], 'loans', 'advance repayment'],
  ['Compensation', 'claims', 'Expense claims', 'receipt', ['claims.view_all', 'claims.approve'], 'claims', 'reimbursement travel'],
  ['Talent', 'recruitment', 'Recruitment', 'briefcase', ['recruitment.view'], 'recruitment', 'jobs candidates hiring pipeline'],
  ['Talent', 'performance', 'Performance', 'star', ['performance.view'], 'performance', 'reviews appraisal rating'],
  ['Talent', 'training', 'Training', 'graduation', ['training.view'], 'training', 'courses programs'],
  ['Administration', 'assets', 'Assets', 'laptop', ['assets.view'], 'assets', 'laptop phone equipment'],
  ['Administration', 'notices', 'Notice board', 'megaphone', null, 'notices', 'announcements'],
  ['Administration', 'reports', 'Reports', 'chart', ['reports.view'], 'reports', 'export csv analytics'],
  ['Administration', 'users', 'Users and roles', 'shield', ['users.manage'], 'users', 'accounts permissions login password'],
  ['Administration', 'audit', 'Audit trail', 'history', ['audit.view'], 'audit', 'log activity changes'],
  ['Administration', 'settings', 'Settings', 'sliders', ['settings.manage'], 'settings', 'company payroll rules backup'],
];

export const ctx = {
  user: null,
  can: (p) => !!ctx.user && ctx.user.permissions.includes(p),
  canAny: (ps) => !ps || ps.some((p) => ctx.can(p)),
  /** Set the page header. `back` = [href, label] shows a link above the title. */
  setTitle(title, sub = '', back = null) {
    $('#pageTitle').textContent = title;
    $('#pageSub').textContent = sub;
    $('#pageSub').classList.toggle('hidden', !sub);
    const head = $('#pageHead > div');
    head.querySelector('.back')?.remove();
    if (back) head.insertAdjacentHTML('afterbegin', `<a class="back" href="${back[0]}">${ic('arrow-left', 15)}${esc(back[1])}</a>`);
    document.title = `${title} | ${ctx.user?.company?.name || 'HR-MIS'}`;
  },
  refreshNav: () => refreshCounts(),
};

const visible = () => ROUTES.filter(([g, , , , perms]) => ctx.canAny(perms) && (g !== 'My workspace' || ctx.user.emp_id));

/* ------------------------------------------------------------ boot */
session.onUnauthorized(() => { if (ctx.user) { ctx.user = null; session.clear(); showLogin('Your session has ended. Please sign in again.'); } });

function paintStatic() {
  $('#menuBtn').innerHTML = ic('menu', 20);
  $('#searchBtn').innerHTML = `${ic('search', 17)}<span>Search people and pages</span><kbd>Ctrl K</kbd>`;
  $('#loginPoints').innerHTML = [
    ['users', 'Employee records, documents and career history for every unit'],
    ['calendar-check', 'Attendance, leave and approvals that flow to line managers'],
    ['wallet', 'Bangladesh-ready payroll with PF, tax, loans and payslips'],
    ['briefcase', 'Recruitment, performance reviews, training and assets'],
  ].map(([i, t]) => `<li>${ic(i, 18)}<span>${esc(t)}</span></li>`).join('');
  $('#todayPill').textContent = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  paintThemeButton();
}

async function boot() {
  paintStatic();
  if (!session.token) return showLogin();
  try {
    ctx.user = await api.get('/api/auth/me');
    startApp();
  } catch { session.clear(); showLogin(); }
}

function showLogin(message) {
  $('#app').classList.add('hidden');
  $('#login').classList.remove('hidden');
  closeModal();
  const err = $('#loginError');
  err.innerHTML = message ? `${ic('alert', 17)}<span>${esc(message)}</span>` : '';
  err.classList.toggle('hidden', !message);
  document.title = 'Sign in | HR-MIS';
}

$('#loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target;
  const btn = f.querySelector('button[type=submit]');
  btn.disabled = true;
  btn.textContent = 'Signing in…';
  try {
    const res = await api.post('/api/auth/login', { username: f.username.value, password: f.password.value });
    session.set(res.token, false);
    ctx.user = res.user;
    f.password.value = '';
    startApp();
  } catch (err) {
    $('#loginError').innerHTML = `${ic('alert', 17)}<span>${esc(err.message)}</span>`;
    $('#loginError').classList.remove('hidden');
  } finally { btn.disabled = false; btn.textContent = 'Sign in'; }
});
$('#demoAccounts').addEventListener('click', (e) => {
  const tr = e.target.closest('tr');
  if (!tr) return;
  $('#loginForm').username.value = tr.dataset.u;
  $('#loginForm').password.value = tr.dataset.p;
  $('#loginForm').querySelector('button[type=submit]').focus();
});

function startApp() {
  $('#login').classList.add('hidden');
  $('#app').classList.remove('hidden');
  const u = ctx.user;
  setUser(u);
  $('#brandName').textContent = u.company.name;
  $('#brandLogo').textContent = u.company.short || initials(u.company.name);
  $('#userName').textContent = u.full_name;
  $('#userRole').textContent = u.role_label;
  $('#userAv').textContent = initials(u.full_name);
  $('#roleFoot').textContent = u.role_label;
  $('#userDrop').innerHTML = `${u.emp_id ? `<a href="#/me/profile">${ic('user', 17)}My profile</a>` : ''}
    <button data-act="app:password">${ic('key', 17)}Change password</button><hr><button data-act="app:logout">${ic('logout', 17)}Sign out</button>`;
  buildNav();
  if (!location.hash || location.hash === '#/') location.hash = '#/dashboard';
  route();
  if (u.must_change_pw) changePassword(true);
}

/* ------------------------------------------------------------ navigation */
function buildNav() {
  const groups = {};
  for (const r of visible()) (groups[r[0]] ||= []).push(r);
  $('#nav').innerHTML = Object.entries(groups).map(([g, items]) => `${g === 'Overview' ? '' : `<h6>${esc(g)}</h6>`}` +
    items.map(([, path, label, icon]) => `<a href="#/${path}" data-path="${path}">${ic(icon, 18)}<span>${esc(label)}</span><span class="cnt hidden" data-count="${path}"></span></a>`).join('')).join('');
  refreshCounts();
}

async function refreshCounts() {
  const set = (path, n) => { const el = document.querySelector(`[data-count="${path}"]`); if (el) { el.textContent = n; el.classList.toggle('hidden', !n); el.title = `${n} waiting for you`; } };
  try {
    if (ctx.can('leave.approve')) {
      const r = await api.get('/api/leave/requests', { status: 'Pending' });
      set('leave', r.items.filter((x) => x.can_decide).length);
    }
    if (ctx.can('claims.approve')) {
      const r = await api.get('/api/claims', { status: 'Pending' });
      set('claims', r.items.filter((x) => x.emp_id !== ctx.user.emp_id).length);
    }
  } catch { /* counts are best-effort */ }
}

let lastPath = '';
async function route() {
  if (!ctx.user) return;
  const path = (location.hash.replace(/^#\/?/, '') || 'dashboard').split('?')[0];
  const segs = path.split('/');
  let match = visible().find((r) => r[1] === path) || visible().find((r) => r[1] === segs[0]);
  if (segs[0] === 'employees' && segs[1]) match = ['People', 'employees', 'Employee profile', '', null, 'employees'];
  if (!match) { location.hash = '#/dashboard'; return; }
  document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('on', a.dataset.path === (path.startsWith('me/') ? path : segs[0])));
  document.body.classList.remove('nav-open');
  ctx.setTitle(match[2]);
  const main = $('#main');
  if (lastPath.split('/')[0] !== segs[0] || segs[1]) main.innerHTML = '<div class="empty">Loading…</div>';
  lastPath = path;
  try {
    const mod = await import(`./pages/${match[5]}.js`);
    await mod.render(main, { ...ctx, path, segs });
    if (lastPath !== path) return;
    window.scrollTo(0, 0);
  } catch (e) {
    showError(e);
    main.innerHTML = `<div class="card empty">${ic('alert', 22)}<b>This page couldn't be loaded</b><span>${esc(e.message)}</span></div>`;
  }
}
window.addEventListener('hashchange', route);

/* ------------------------------------------------------------ theme */
function currentTheme() {
  const set = document.documentElement.getAttribute('data-theme');
  if (set) return set;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
function paintThemeButton() {
  const dark = currentTheme() === 'dark';
  $('#themeBtn').innerHTML = ic(dark ? 'sun' : 'moon', 19);
  $('#themeBtn').title = dark ? 'Switch to light theme' : 'Switch to dark theme';
}
on('app:theme', () => {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('hrmis.theme', next); } catch { /* not saved; still applied for this visit */ }
  paintThemeButton();
});

/* ------------------------------------------------------------ search palette (Ctrl+K) */
let pal = { items: [], index: 0 };
async function openPalette() {
  if (!ctx.user) return;
  const box = modal('Search', '', {});
  box.classList.add('palette');
  box.innerHTML = `<div class="pal-input">${ic('search', 20)}<input id="palQ" placeholder="Type a name, employee ID or page" autocomplete="off" aria-label="Search"><kbd>Esc</kbd></div>
    <div class="pal-list" id="palList" role="listbox"></div>
    <div class="pal-foot"><span><kbd>↑</kbd> <kbd>↓</kbd> to move</span><span><kbd>Enter</kbd> to open</span></div>`;
  const people = ctx.canAny(['employees.view', 'team.view']) ? await api.get('/api/employees', { status: 'Active' }).then((r) => r.items).catch(() => []) : [];
  const input = $('#palQ');
  const draw = () => {
    const q = input.value.trim().toLowerCase();
    const pages = visible().filter((r) => !q || (r[2] + ' ' + r[6]).toLowerCase().includes(q)).slice(0, q ? 8 : 6)
      .map((r) => ({ kind: 'Pages', icon: r[3], label: r[2], sub: r[0], href: `#/${r[1]}` }));
    const ppl = q ? people.filter((p) => `${p.full_name} ${p.code} ${p.designation || ''} ${p.department || ''}`.toLowerCase().includes(q)).slice(0, 8)
      .map((p) => ({ kind: 'People', icon: 'user', label: p.full_name, sub: `${p.code}, ${p.designation || p.department || ''}`, href: `#/employees/${p.id}` })) : [];
    pal.items = [...pages, ...ppl];
    pal.index = Math.min(pal.index, Math.max(0, pal.items.length - 1));
    let last = '';
    $('#palList').innerHTML = pal.items.map((it, i) => {
      const head = it.kind !== last ? `<div class="pal-group">${it.kind}</div>` : '';
      last = it.kind;
      return `${head}<div class="pal-item ${i === pal.index ? 'on' : ''}" data-act="pal:go" data-href="${it.href}" role="option">${ic(it.icon, 17)}<span>${esc(it.label)}</span><small>${esc(it.sub)}</small></div>`;
    }).join('') || `<div class="empty">${ic('search', 22)}<b>No matches</b><span>Try a first name, an employee ID like ST-1004, or a page name.</span></div>`;
  };
  input.addEventListener('input', () => { pal.index = 0; draw(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { pal.index = Math.min(pal.items.length - 1, pal.index + 1); draw(); e.preventDefault(); }
    if (e.key === 'ArrowUp') { pal.index = Math.max(0, pal.index - 1); draw(); e.preventDefault(); }
    if (e.key === 'Enter' && pal.items[pal.index]) { closeModal(); location.hash = pal.items[pal.index].href; }
  });
  draw();
  input.focus();
}
on('app:palette', openPalette);
on('pal:go', (el) => { closeModal(); location.hash = el.dataset.href; });
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k' && ctx.user) { e.preventDefault(); openPalette(); }
  if (e.key === '/' && ctx.user && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName) && !$('#modal').classList.contains('open')) { e.preventDefault(); openPalette(); }
});

/* ------------------------------------------------------------ user menu */
on('app:menu', () => document.body.classList.toggle('nav-open'));
on('app:usermenu', () => $('#userDrop').classList.toggle('hidden'));
document.addEventListener('click', (e) => { if (!e.target.closest('.user-menu')) $('#userDrop').classList.add('hidden'); });
on('app:logout', async () => {
  try { await api.post('/api/auth/logout'); } catch { /* ignore */ }
  session.clear();
  ctx.user = null;
  location.hash = '';
  showLogin();
});
on('app:password', () => changePassword(false));

async function changePassword(forced) {
  $('#userDrop').classList.add('hidden');
  const fields = [{ k: 'current_password', l: forced ? 'Temporary password' : 'Current password', t: 'password', req: 1, w: 2 },
    { k: 'new_password', l: 'New password', t: 'password', req: 1, hint: 'At least 8 characters, with letters and numbers' },
    { k: 'confirm', l: 'Repeat new password', t: 'password', req: 1 }];
  modal(forced ? 'Choose your own password' : 'Change password',
    (forced ? `<div class="banner info" style="margin-bottom:14px">${ic('info', 17)}<span>You signed in with a temporary password. Choose a new one to continue.</span></div>` : '') + await formHTML(fields), {
      saveLabel: 'Save new password', size: 'narrow', locked: forced,
      onSave: async () => {
        const d = readForm(fields, $('#modal'));
        if (!d) return false;
        if (d.new_password !== d.confirm) { toast('The two new passwords are different. Type them again.', 'bad'); return false; }
        await api.post('/api/auth/change-password', d);
        ctx.user.must_change_pw = false;
        toast('Password changed', 'ok');
      },
    });
}

void lookups;
boot();
