/* Native Chema Owner adapter.
 * Runs BEFORE Chema's unmodified scripts. No dashboard, catalog or extra UI.
 * A browser never supplies owner_id, workspace UUID, PID, socket or unit.
 * A verified Google session/CSRF selects the workspace at the Owner server;
 * the root broker repeats the identity check for every worker descriptor.
 * Unknown native APIs are blocked, not accidentally sent to a shared Engine.
 */
(() => {
  'use strict';
  const originalFetch = window.fetch.bind(window);
  const routes = new Set([
    'api/v1/wizard/projects', 'api/v1/wizard/projects/new',
    'api/v1/wizard/projects/open', 'api/v1/wizard/projects/delete',
    'api/v1/wizard/draft', 'api/v1/wizard/prepare', 'api/v1/wizard/start',
    'api/v1/wizard/cancel', 'api/v1/wizard/status',
    'api/v1/project', 'montara/recovery/latest'
  ]);
  const nativePrefix = '/urano/v1/native/rpc/';
  let csrfPromise = null;
  let ensurePromise = null;
  let generation = null;

  const token = () => {
    if (!csrfPromise) {
      csrfPromise = originalFetch('/urano/v1/session/refresh', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Origin': location.origin }
      }).then(async response => {
        if (!response.ok) throw new Error('Montara session expired');
        const value = await response.json();
        if (!/^[a-f0-9]{64}$/.test(value.csrf || ''))
          throw new Error('Montara CSRF unavailable');
        return value.csrf;
      }).catch(error => { csrfPromise = null; throw error; });
    }
    return csrfPromise;
  };

  const ensure = () => {
    if (!ensurePromise) {
      ensurePromise = token().then(async csrf => {
        const response = await originalFetch('/urano/v1/native/ensure', {
          method:'POST', cache:'no-store', credentials:'same-origin',
          headers: { 'X-Urano-CSRF':csrf, 'Origin':location.origin }
        });
        if (!response.ok) {
          const msg = (await response.json().catch(() => ({}))).error;
          throw new Error(typeof msg === 'string' ? msg :
            'Your private Montara workspace is unavailable');
        }
        const value = await response.json();
        if (value.state !== 'ready' ||
            !Number.isSafeInteger(value.generation) ||
            value.generation < 1)
          throw new Error('Private worker verification failed');
        generation = value.generation;
        return generation;
      }).catch(error => { ensurePromise = null; throw error; });
    }
    return ensurePromise;
  };

  const route = input => {
    const raw = typeof input === 'string' ? input :
      input instanceof URL ? input.href : input?.url;
    if (typeof raw !== 'string') return null;
    const address = new URL(raw, location.href);
    if (address.origin !== location.origin) return null;
    const p = address.pathname;
    if (!p.startsWith('/api/v1/') && !p.startsWith('/montara/'))
      return null;
    if (p === '/montara/version')
      return { kind:'metadata', data:{version:'Montara Owner Beta'} };
    if (p === '/montara/branding')
      return { kind:'metadata', data:{mode:'montara',has_logo:false} };
    const operation = p.substring(1);
    if (address.hash || !routes.has(operation))
      return {kind:'blocked'};
    if (address.search) {
      const params = address.searchParams;
      if (operation !== 'api/v1/wizard/status' ||
          params.size !== 1 || !params.has('project_id') ||
          (params.get('project_id')||'').length > 4096)
        return {kind:'blocked'};
    }
    return {kind:'worker', path:nativePrefix + operation + address.search};
  };

  function authHeaders(base, csrf) {
    const h = new Headers(base || {});
    h.set('X-Urano-CSRF', csrf);
    if (generation) h.set('X-Montara-Engine-Generation', String(generation));
    return h;
  }

  // Chema probes Latest at JS startup. Do not wake a cloud worker merely
  // because Google login displayed the Home/Music/Video intro. Resolve the
  // original promise when the genuine Footage/Stage screen is entered.
  let footagePromise = null;
  const whenFootageIsVisible = () => {
    const element = document.getElementById('footage');
    if (!element || !element.hidden) return Promise.resolve();
    if (!footagePromise) {
      footagePromise = new Promise(resolve => {
        const observer = new MutationObserver(() => {
          if (element.hidden) return;
          observer.disconnect();
          resolve();
        });
        observer.observe(element, {attributes:true,attributeFilter:['hidden']});
      });
    }
    return footagePromise;
  };

  window.fetch = async (input, init={}) => {
    const selected = route(input);
    if (!selected) return originalFetch(input, init);
    if (selected.kind === 'blocked')
      throw new Error('Original Montara operation not enabled in this private beta');
    if (selected.kind === 'metadata')
      return new Response(JSON.stringify(selected.data), {
        status:200, headers:{'Content-Type':'application/json',
                            'Cache-Control':'no-store'}
      });
    // Initial GET from full-session.js is a non-blocking probe. It must not
    // start a VM worker while Home/Video/Music navigation is still visible.
    if (selected.path.startsWith(nativePrefix + 'montara/recovery/latest')) {
      await whenFootageIsVisible();
    }
    const csrf = await token();
    await ensure();
    const headers = authHeaders(init.headers || input?.headers, csrf);
    const method = String(init.method || input?.method || 'GET').toUpperCase();
    const response = await originalFetch(selected.path, {
      ...init, method, headers, credentials:'same-origin', cache:'no-store'
    });
    const next = Number(response.headers.get('X-Montara-Engine-Generation'));
    if (Number.isSafeInteger(next) && next > 0) generation = next;
    return response;
  };

  // Chema also uses XHR for imported media. Keep the original XHR event
  // semantics; no replacement uploader or form is created here.
  if (typeof XMLHttpRequest !== 'undefined') {
    const open = XMLHttpRequest.prototype.open;
    const send = XMLHttpRequest.prototype.send;
    const abort = XMLHttpRequest.prototype.abort;
    const selection = new WeakMap();
    XMLHttpRequest.prototype.open = function(method, url, ...other) {
      const target = route(url);
      const nativeMethod = String(method).toUpperCase();
      const asynchronous = other[0] !== false;
      if (target && (!asynchronous || target.kind === 'blocked' ||
                     target.kind === 'metadata')) {
        throw new Error('Original Montara operation not enabled in this private beta');
      }
      selection.set(this, {target, method:nativeMethod, cancelled:false});
      return open.call(this, nativeMethod,
                       target?.kind === 'worker' ? target.path : url, ...other);
    };
    XMLHttpRequest.prototype.send = function(body) {
      const current = selection.get(this);
      if (!current?.target) return send.call(this,body);
      Promise.all([token(),ensure()]).then(([csrf]) => {
        if (current.cancelled) return;
        this.setRequestHeader('X-Urano-CSRF', csrf);
        if (generation)
          this.setRequestHeader('X-Montara-Engine-Generation',String(generation));
        send.call(this,body);
      }).catch(() => {
        if (!current.cancelled) abort.call(this);
      });
    };
    XMLHttpRequest.prototype.abort = function() {
      const current = selection.get(this);
      if (current) current.cancelled = true;
      return abort.call(this);
    };
  }
})();
