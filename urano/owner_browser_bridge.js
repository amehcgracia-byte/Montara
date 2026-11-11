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
    '/api/v1/wizard/prepare': 'wizard/prepare',
    '/api/v1/wizard/start': 'wizard/start',
    '/api/v1/settings/fillers': 'settings/fillers',
    '/api/v1/artifacts/sync': 'artifacts/sync',
    '/api/v1/wizard/status': 'wizard/status',
    '/api/v1/project': 'project',
    '/montara/branding': 'branding',
    '/montara/version': 'version',
    '/api/v1/wizard/review': 'wizard/review',
    '/api/v1/wizard/review/replace': 'wizard/review/replace',
    '/api/v1/wizard/review/render': 'wizard/review/render',
    '/api/v1/edit/native-recipe': 'edit/native-recipe',
    '/api/v1/edit/native-master': 'edit/native-master',
    '/api/v1/edit/timeline': 'edit/timeline',
    '/api/v1/edit/shot': 'edit/shot',
    '/api/v1/edit/shot/frame': 'edit/shot/frame',
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
    const uploadPart = new RegExp("^/montara/uploads/([a-f0-9]{32})(/finish)?$").exec(path);
    const shotPreview = /^\/api\/v1\/wizard\/review\/preview\/([0-9]{1,5})$/.exec(path);
    const shotThumbnail = /^\/api\/v1\/wizard\/review\/thumbnail\/(assets-v2|[a-f0-9]{16,128})\/([A-Za-z0-9_.-]{1,180})$/.exec(path);
    const operation = routes[path] ||
      (uploadPart ? 'uploads/' + uploadPart[1] + (uploadPart[2] || '') :
      shotPreview ? 'wizard/review/preview/' + shotPreview[1] :
      shotThumbnail ? 'wizard/review/thumbnail/' + shotThumbnail[1] + '/' + shotThumbnail[2] : null);
    const isStatusPoll = operation === 'wizard/status' &&
      parsed.searchParams.size === 1 &&
      parsed.searchParams.has('project_id') &&
      parsed.searchParams.get('project_id').length > 0;
    // Status is intentionally bound to this worker; discard the browser's
    // physical path query rather than forwarding it to a global JM catalog.
    const reviewQuery = operation === 'wizard/review' &&
      [...parsed.searchParams.keys()].every(k => k === 'render' || k === 'shot') &&
      (!parsed.searchParams.has('render') || ['0','1'].includes(parsed.searchParams.get('render'))) &&
      (!parsed.searchParams.has('shot') || /^[0-9]{1,5}$/.test(parsed.searchParams.get('shot'))) &&
      [...parsed.searchParams.keys()].length <= 2;
    const recipeQuery = operation === 'edit/native-recipe' &&
      parsed.searchParams.size === 1 && parsed.searchParams.has('project_id') &&
      parsed.searchParams.get('project_id').length > 0;
    const masterQuery = operation === 'edit/native-master' &&
      parsed.searchParams.size === 2 &&
      parsed.searchParams.has('project_id') &&
      parsed.searchParams.get('project_id').length > 0 &&
      /^[0-9]{1,10}$/.test(parsed.searchParams.get('revision') || '');
    const timelineQuery = operation === 'edit/timeline' &&
      parsed.searchParams.size === 1 && parsed.searchParams.get('kind') === 'music';
    const shotQuery = operation === 'edit/shot' &&
      parsed.searchParams.size === 1 && /^[0-9]{1,5}$/.test(parsed.searchParams.get('index') || '');
    const frameQuery = operation === 'edit/shot/frame' &&
      parsed.searchParams.size === 3 &&
      ['index','choice','revision'].every(k =>
        /^[0-9]{1,9}$/.test(parsed.searchParams.get(k) || ''));
    const videoVersion = Boolean(shotPreview) &&
      parsed.searchParams.size === 1 && /^[A-Za-z0-9_.-]{0,80}$/.test(parsed.searchParams.get('v') || '');
    if (!operation || parsed.hash ||
        (parsed.search && !isStatusPoll && !reviewQuery && !recipeQuery &&
         !timelineQuery && !shotQuery && !frameQuery && !masterQuery && !videoVersion)) {
      return { blocked: true };
    }
    return { path: base + operation +
      (isStatusPoll || recipeQuery ? '?project_id=owner-worker' :
       masterQuery ? '?project_id=owner-worker&revision=' + encodeURIComponent(parsed.searchParams.get('revision')) :
       reviewQuery || timelineQuery || shotQuery || frameQuery || videoVersion ?
       parsed.search : ''), operation };
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

  // Chema renders shot thumbnails through <img>, which cannot carry the
  // Owner CSRF header. Resolve reviewed, owner-scoped media using fetch and
  // display a browser-local blob URL; never expose an unauthenticated media
  // endpoint. Keep a tiny cache across review polling iterations.
  const reviewBlobs = new Map();
  const getReviewBlob = async (url) => {
    if (!reviewBlobs.has(url)) {
      const job = (async () => {
        const response = await window.fetch(url);
        if (!response.ok) throw new Error('Private Stage preview unavailable');
        const blob = await response.blob();
        return URL.createObjectURL(blob);
      })();
      reviewBlobs.set(url, job);
      job.catch(() => { if (reviewBlobs.get(url) === job) reviewBlobs.delete(url); });
    }
    return reviewBlobs.get(url);
  };

  const decorateReview = async (response) => {
    if (!response.ok) return response;
    const body = await response.clone().json();
    if (!Array.isArray(body.items) || body.items.length > 200) return response;
    await Promise.all(body.items.map(async (item) => {
      if (typeof item.thumbnail === 'string' &&
          /^\/api\/v1\/wizard\/review\/thumbnail\//.test(item.thumbnail)) {
        try { item.thumbnail = await getReviewBlob(item.thumbnail); }
        catch { item.thumbnail = null; }
      }
    }));
    return new Response(JSON.stringify(body), {
      status: response.status, headers: response.headers,
    });
  };

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
    if (target.operation === 'wizard/review' && method === 'GET') {
      return decorateReview(response);
    }
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

  // Hover previews are inserted directly as <video src=...> by JM.
  // Convert the URL on demand using the same Owner+CSRF fetch contract,
  // never a shared Engine media endpoint.
  if (typeof HTMLVideoElement !== 'undefined' && typeof HTMLMediaElement !== 'undefined') {
    const descriptor = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'src');
    if (descriptor && descriptor.get && descriptor.set) {
      const latest = new WeakMap();
      Object.defineProperty(HTMLVideoElement.prototype,'src', {
        configurable: true, enumerable: descriptor.enumerable,
        get() { return latest.get(this)?.original || descriptor.get.call(this); },
        set(value) {
          const original = String(value);
          const target = resolve(original);
          if (!target || target.blocked || !target.operation.startsWith('wizard/review/preview/')) {
            latest.delete(this);
            return descriptor.set.call(this,value);
          }
          const job = { original };
          latest.set(this,job);
          descriptor.set.call(this,'');
          getReviewBlob(original).then((url) => {
            if (latest.get(this) !== job) return;
            descriptor.set.call(this,url);
            this.load();
          }).catch(() => {
            if (latest.get(this) === job) this.dispatchEvent(new Event('error'));
          });
        },
      });
    }
  }

  // Stage 360 shot editor loads a frame directly in <img>; use the
  // same scoped, CSRF-protected blob conversion as for review thumbnails.
  if (typeof HTMLImageElement !== 'undefined') {
    const descriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,'src');
    if (descriptor && descriptor.get && descriptor.set) {
      const latest = new WeakMap();
      Object.defineProperty(HTMLImageElement.prototype,'src',{
        configurable:true,enumerable:descriptor.enumerable,
        get(){return latest.get(this)?.original || descriptor.get.call(this);},
        set(value){
          const original=String(value);
          const target=resolve(original);
          if (!target || target.blocked || target.operation!=='edit/shot/frame') {
            latest.delete(this);
            return descriptor.set.call(this,value);
          }
          const job={original};
          latest.set(this,job);
          descriptor.set.call(this,'');
          getReviewBlob(original).then(url=>{
            if(latest.get(this)===job)descriptor.set.call(this,url);
          }).catch(()=>{
            if(latest.get(this)===job)this.dispatchEvent(new Event('error'));
          });
        },
      });
    }
  }

  // Stable exposed inspection data (not an authentication credential).
  Object.defineProperty(window, 'MontaraOwnerBridge', {
    value: Object.freeze({ projectId: project, reviewedStagePilot: true }),
    writable: false, configurable: false,
  });
})();
