/* I53: opt-in browser route adapter for the ORIGINAL Chema editor.
 * NOT a replacement editor, no new uploader, no persistent user secrets.
 * Only approved initial Stage routes may leave the browser. Any other
 * original /api/v1 or /montara request is blocked, not sent to a shared
 * global Engine. This is a private pilot, NOT Stage/Push/Show E2E yet.
 */
(() => {
  'use strict';
  const script = document.currentScript;
  const project = script?.dataset?.ownerProject || '';
  if (!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(project)) {
    throw new Error('Invalid Montara Owner project');
  }
  const routes = Object.freeze({
    '/api/v1/wizard/upload': 'wizard/upload',
    '/api/v1/wizard/projects/new': 'wizard/projects/new',
    '/api/v1/wizard/draft': 'wizard/draft',
    '/api/v1/wizard/status': 'wizard/status',
    '/api/v1/project': 'project',
    '/montara/branding': 'branding',
    '/montara/uploads': 'uploads',
  });
  const nativeFetch = window.fetch.bind(window);
  const base = '/urano/v1/media/' + project + '/';
  let csrfJob = null;
  let ensureJob = null;
  let generation = null;

  const resolve = (input) => {
    const name = typeof input === 'string' ? input :
      input instanceof URL ? input.href : input?.url;
    if (typeof name !== 'string') return null;
    const parsed = new URL(name, location.href);
    if (parsed.origin !== location.origin) return null;
    const path = parsed.pathname;
    if (!path.startsWith('/api/v1/') && !path.startsWith('/montara/')) return null;
    const uploadPart = /^\\/montara\\/uploads\\/([a-f0-9]{32})(\\/finish)?$/.exec(path);
    const operation = routes[path] || (uploadPart
      ? 'uploads/' + uploadPart[1] + (uploadPart[2] || '') : null);
    if (!operation || parsed.search || parsed.hash) {
      return { blocked: true };
    }
    return { path: base + operation, operation };
  };

  const csrf = async () => {
    if (!csrfJob) {
      csrfJob = (async () => {
        const response = await nativeFetch('/urano/v1/session/refresh', {
          method: 'POST', credentials: 'same-origin', cache: 'no-store',
        });
        if (!response.ok) throw new Error('Montara login expired');
        const body = await response.json();
        if (!/^[0-9a-f]{64}$/.test(body.csrf || '')) {
          throw new Error('Montara CSRF unavailable');
        }
        return body.csrf;
      })();
    }
    return csrfJob;
  };

  const ensure = async () => {
    if (generation) return generation;
    if (!ensureJob) {
      ensureJob = (async () => {
        const token = await csrf();
        const response = await nativeFetch(
          '/urano/v1/projects/' + project + '/ensure', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'X-Urano-CSRF': token },
          });
        if (!response.ok) throw new Error('Montara private Engine unavailable');
        const body = await response.json();
        if (body.project_id !== project || body.state !== 'ready'
            || !Number.isSafeInteger(body.generation)
            || body.generation < 1) {
          throw new Error('Invalid private Engine generation');
        }
        generation = body.generation;
        return generation;
      })();
      ensureJob.catch(() => { ensureJob = null; });
    }
    return ensureJob;
  };

  const metadata = (headers, token) => {
    headers.set('X-Urano-CSRF', token);
    if (generation) headers.set('X-Montara-Engine-Generation', String(generation));
    return headers;
  };
  const uploadOperation = (operation, method) =>
    method === 'POST' &&
    (operation === 'wizard/upload' || operation === 'uploads');

  window.fetch = async function ownerScopedFetch(input, init = {}) {
    const target = resolve(input);
    if (!target) return nativeFetch(input, init);
    if (target.blocked) {
      throw new Error('This original Montara operation is not yet enabled in the private beta');
    }
    const method = String(init.method || input?.method || 'GET').toUpperCase();
    const token = await csrf();
    if (uploadOperation(target.operation, method)) await ensure();
    const headers = new Headers(init.headers || input?.headers || {});
    metadata(headers, token);
    const options = { ...init, method, headers, credentials: 'same-origin' };
    const response = await nativeFetch(target.path, options);
    const next = Number(response.headers.get('X-Montara-Engine-Generation'));
    if (Number.isSafeInteger(next) && next > 0) generation = next;
    return response;
  };

  if (typeof XMLHttpRequest !== 'undefined') {
    const oldOpen = XMLHttpRequest.prototype.open;
    const oldSend = XMLHttpRequest.prototype.send;
    const oldAbort = XMLHttpRequest.prototype.abort;
    const state = new WeakMap();
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
      const target = resolve(url);
      const action = String(method).toUpperCase();
      state.set(this, { target, method: action, cancelled: false });
      return oldOpen.call(this, action,
        target && !target.blocked ? target.path : url, ...rest);
    };
    XMLHttpRequest.prototype.send = function(body) {
      const entry = state.get(this);
      if (!entry || !entry.target) return oldSend.call(this, body);
      if (entry.target.blocked) {
        throw new Error('Private Montara route not available');
      }
      Promise.resolve().then(async () => {
        const token = await csrf();
        if (uploadOperation(entry.target.operation, entry.method)) await ensure();
        if (entry.cancelled) return;
        this.setRequestHeader('X-Urano-CSRF', token);
        if (generation) {
          this.setRequestHeader('X-Montara-Engine-Generation', String(generation));
        }
        oldSend.call(this, body);
      }).catch(() => { if (!entry.cancelled) oldAbort.call(this); });
    };
    XMLHttpRequest.prototype.abort = function() {
      const entry = state.get(this);
      if (entry) entry.cancelled = true;
      return oldAbort.call(this);
    };
  }

  // Stable exposed inspection data (not an authentication credential).
  Object.defineProperty(window, 'MontaraOwnerBridge', {
    value: Object.freeze({ projectId: project, reviewedStagePilot: true }),
    writable: false, configurable: false,
  });
})();
