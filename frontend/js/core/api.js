/**
 * API client: wraps fetch with the session token, JSON handling, errors,
 * authenticated file downloads and a small cache for dropdown lookups.
 */
const TOKEN_KEY = 'hrmis.token';
let onUnauthorized = () => {};

export const session = {
  get token() { try { return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set(token, remember) {
    try { (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token); } catch { /* storage blocked */ }
  },
  clear() { try { sessionStorage.removeItem(TOKEN_KEY); localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } },
  onUnauthorized(fn) { onUnauthorized = fn; },
};

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function request(method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  if (session.token) headers.Authorization = 'Bearer ' + session.token;
  let res;
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, 'Cannot reach the HR-MIS server. Is it still running?');
  }
  const type = res.headers.get('Content-Type') || '';
  const data = type.includes('application/json') ? await res.json() : await res.blob();
  if (res.status === 401 && path !== '/api/auth/login') { onUnauthorized(); }
  if (!res.ok) throw new ApiError(res.status, (data && data.error) || `Request failed (${res.status})`);
  if (method !== 'GET') cache.clear();
  return data;
}

export const api = {
  get: (path, params) => request('GET', params ? `${path}?${new URLSearchParams(clean(params))}` : path),
  post: (path, body = {}) => request('POST', path, body),
  put: (path, body = {}) => request('PUT', path, body),
  del: (path) => request('DELETE', path),
  /** Download a protected file (CSV, backup, document) with the session token. */
  async download(path, params, fallbackName = 'download') {
    const url = params ? `${path}?${new URLSearchParams(clean(params))}` : path;
    const res = await fetch(url, { headers: { Authorization: 'Bearer ' + session.token } });
    if (!res.ok) {
      let msg = 'Download failed';
      try { msg = (await res.json()).error || msg; } catch { /* not json */ }
      throw new ApiError(res.status, msg);
    }
    const name = (res.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/)?.[1] || fallbackName;
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 3000);
    return name;
  },
};

function clean(params) {
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
}

/** Cached GETs for lookup lists (employees, departments …). Any write clears the cache. */
const cache = new Map();
export function cached(path, params) {
  const key = path + JSON.stringify(params || {});
  if (!cache.has(key)) cache.set(key, api.get(path, params).catch((e) => { cache.delete(key); throw e; }));
  return cache.get(key);
}

export const lookups = {
  employees: async (all) => (await cached('/api/employees/lookup', all ? { all: 1 } : null)).items,
  units: async () => (await cached('/api/units')).items,
  departments: async () => (await cached('/api/departments')).items,
  designations: async () => (await cached('/api/designations')).items,
  leaveTypes: async () => (await cached('/api/leave-types')).items,
  jobs: async () => (await cached('/api/jobs')).items,
};
