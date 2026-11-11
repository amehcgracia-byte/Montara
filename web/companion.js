/* Talks to the Montara companion on the person's computer (companion/companion.py).
   When it is running, a dropped video is not uploaded: the companion finds the
   original by name, size and edge fingerprint, makes a small version (720p H.264,
   constant frame rate, SDR) and only that small version is uploaded. A WAV/AIFF becomes
   a lossless FLAC (name.wav.flac); the server restores the identical WAV. For a full session
   it becomes a light Opus preview (name.wav.opus); at export only the song ranges of the
   originals are sent, lossless (segment). Without the
   companion, the video original requires explicit user consent. */
const montaraCompanion = (() => {
  const BASE = 'http://127.0.0.1:47820';
  const EDGE = 65536;
  let info = null;
  async function call(path, options = {}, timeout = 0) {
    // A mix returns its bytes after the headers: keep the caller's signal
    // attached for the entire body transfer, not just until fetch resolves.
    if(options.signal && !timeout)return fetch(BASE+path,options);
    const controller = new AbortController();
    const timer = timeout ? setTimeout(() => controller.abort(), timeout) : null;
    const abort=()=>controller.abort();
    options.signal?.addEventListener('abort',abort,{once:true});
    if(options.signal?.aborted)abort();
    try { return await fetch(BASE + path, {...options, signal: controller.signal}); }
    finally { if (timer) clearTimeout(timer);options.signal?.removeEventListener('abort',abort); }
  }
  async function readProxy(id, cancelled) {
    for (let attempt = 0; attempt < 3 && !cancelled(); attempt++) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 120000);
      try {
        const response = await call(`/proxies/${id}/file`, {cache: 'no-store', signal: controller.signal});
        if (response.ok) {
          const blob = await response.blob();
          if (cancelled()) return null;
          if (blob.size && (!response.headers?.get('Content-Length') || blob.size === Number(response.headers.get('Content-Length'))))
            return {blob, retries: attempt};
        } else if (![408, 429, 502, 503, 504].includes(response.status)) {
          return null;
        }
      } catch (error) {
        if (!controller.signal.aborted && !(error instanceof TypeError) && error.name !== 'TypeError') throw error;
      } finally {
        clearTimeout(timeout);
      }
      if (attempt < 2 && !cancelled()) await new Promise(resolve => setTimeout(resolve, 250 * (attempt + 1)));
    }
    return null;
  }
  async function fingerprint(file) {
    const edges = await new Blob([file.slice(0, EDGE), file.slice(Math.max(0, file.size - EDGE))]).arrayBuffer();
    return [...new Uint8Array(await crypto.subtle.digest('SHA-256', edges))].map(n => n.toString(16).padStart(2, '0')).join('');
  }
  const json = (body) => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  return {
    get info() { return info; },
    async detect() {
      try {
        const response = await call('/health', {cache: 'no-store'}, 2500);
        const data = await response.json();
        info = response.ok && data.app === 'montara-companion' && data.ffmpeg ? data : null;
      } catch { info = null; }
      return info;
    },
    isVideo(file) { return /^video\//.test(file.type) || /\.(mp4|mov|m4v|mts|mkv|avi|webm)$/i.test(file.name); },
    isAudio(file) { return /\.(wav|aiff?)$/i.test(file.name); },
    helps(file) { return this.isVideo(file) || (this.isAudio(file) && !!info?.lossless_audio); },
    /* Asks on the computer where to keep the project; resolves to {id, folder} or null. */
    async projectFolder(name, sources) {
      if (!info) return null;
      try {
        const response = await call('/projects', json({name, sources}));
        return response.ok ? await response.json() : null;
      } catch { return null; }
    },
    async saveInProject(projectId, name, blob) {
      const response = await call(`/projects/${projectId}/save?name=${encodeURIComponent(name)}`, {method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: blob});
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        const message = typeof detail.error === 'string' ? detail.error : 'Could not save the video';
        const error = new Error('Companion could not save the video (' + response.status + '): ' + message);
        error.status = response.status;
        error.companionError = message;
        throw error;
      }
      return (await response.json()).saved;
    },
    async locateOriginal(original) {
      const response = await call('/locate', json(original));
      if (response.status === 404) return false;
      if (!response.ok) throw new Error('Could not check the original: ' + original.name);
      return true;
    },
    async startVideo(body) {
      const response=await call('/video-renders',json(body));const data=await response.json();
      if(!response.ok){const error=new Error(data.error || 'Could not start original-quality export');error.status=response.status;throw error;}return data.id;
    },
    async videoStatus(id) {
      const response=await call(`/video-renders/${id}`);if(!response.ok)throw new Error('The companion video export is unavailable');return response.json();
    },
    async cancelVideo(id) {if(id){const response=await call(`/video-renders/${id}/cancel`,json({}));if(!response.ok)throw new Error('Could not confirm video cancellation.');}},
    videoUrl(id,download=false){return BASE+`/video-renders/${id}/file`+(download?'?download=1':'');},
    /* Resolves to {file, original} with the small version, {missing: true} if it is not on this
       computer, or null when the companion cannot help with this file. */
    async smallVersion(file, onProgress, cancelled = () => false, {preview = false} = {}) {
      if (!info || !this.helps(file)) return null;
      const audio = this.isAudio(file);
      preview = preview && audio && !!info.audio_preview;
      const nowMs = () => typeof performance !== 'undefined' && typeof performance.now === 'function' ? performance.now() : Date.now();
      const timings = {started: nowMs(), located: null, proxyReady: null, downloaded: null};
      let cacheHit = null;
      const proxyRequest = (path, options = {}) => call(path, {...options, signal: AbortSignal.timeout(30000)});
      try {
        onProgress('Finding it on your computer', 0);
        const print = await fingerprint(file);
        const located = await proxyRequest('/locate', json({name: file.name, size: file.size, fingerprint: print}));
        if (!located.ok) return located.status === 404 ? {missing: true} : null;
        const located_ = await located.json();
        timings.located = nowMs();
        const queued = await proxyRequest('/proxies', json({id: located_.id, preview}));
        if (!queued.ok) return null;
        const {id, reused} = await queued.json();
        if (!id) return null;
        for (;;) {
          if (cancelled()) return null;
          const response = await proxyRequest(`/proxies/${id}`);
          if (!response.ok) return {downloadFailed: true};
          const state = await response.json();
          if (state.status === 'ready') { cacheHit = reused === true || state.cache_hit === true ? true : state.cache_hit ?? null; timings.proxyReady = nowMs(); break; }
          if (state.status === 'skipped' || state.status === 'failed') { console.info('Companion:', state.reason || state.error); return null; }
          onProgress(preview ? 'Light preview' : audio ? 'Lossless copy' : 'Small version', state.progress || 0);
          await new Promise(resolve => setTimeout(resolve, 800));
        }
        const download = await readProxy(id, cancelled);
        if (!download) return cancelled() ? null : {downloadFailed: true};
        const {blob, retries} = download;
        timings.downloaded = nowMs();
        // Stage performance diagnostics: durations only; no filenames or local paths.
        console.info('[Montara upload timing]', {
          step: 'local proxy',
          cache_hit: cacheHit,
          local_read_retries: retries,
          original_mib: +(file.size / 1048576).toFixed(1),
          locate_sec: +((timings.located - timings.started) / 1000).toFixed(2),
          convert_sec: +((timings.proxyReady - timings.located) / 1000).toFixed(2),
          local_read_sec: +((timings.downloaded - timings.proxyReady) / 1000).toFixed(2),
          total_sec: +((timings.downloaded - timings.started) / 1000).toFixed(2),
          proxy_mib: +(blob.size / 1048576).toFixed(1)
        });
        const wavpack = blob.type === 'audio/x-wavpack';  // float originals: WavPack instead of FLAC
        const name = preview ? file.name + '.opus' : audio ? file.name + (wavpack ? '.wv' : '.flac') : file.name.replace(/\.[^.]+$/, '') + '.small.mp4';
        const type = preview ? 'audio/ogg' : audio ? blob.type || 'audio/flac' : 'video/mp4';
        return {file: new File([blob], name, {type}), preview, audioIdentityRevision: audio ? info?.audio_identity_revision : undefined, original: {name: file.name, size: file.size, lastModified: file.lastModified, fingerprint: print, companion: id}};
      } catch (error) {
        if (error.name === 'TimeoutError') return {downloadFailed: true};
        console.warn('Companion unavailable for this file', error);
        return null;
      }
    },
    /* One range of an original audio file; resolves to a Blob. 'opus' (Fast, high bitrate) when this
       companion can, otherwise lossless (FLAC, or WavPack for float). */
    canFastSegments() { return Boolean(info?.segment_formats?.includes('opus')); },
    /* Local mixer (install.sh --mixer): the mixer commit it has, or null. */
    localMixer() { return info?.local_mix?.mixer || null; },
    /* Mix one song on this computer with the server's plan; resolves to {blob, seconds}. */
    async mixSong(plan, mix, onProgress = () => {}, signal) {
      const progressId = crypto.randomUUID().replaceAll('-', '');
      let finished = false;
      let cancellation;
      const cancel=()=>{cancellation=call(`/mix-progress/${progressId}/cancel`,json({})).then(response=>{if(!response.ok)throw new Error('Could not confirm mix cancellation.');});cancellation.catch(console.warn);};
      signal?.addEventListener('abort',cancel,{once:true});
      if(signal?.aborted){signal.removeEventListener('abort',cancel);throw new DOMException('Mix cancelled','AbortError');}
      const polling = (async () => {
        while (!finished && info?.mix_progress) {
          try {
            const response = await call(`/mix-progress/${progressId}`, {}, 3000);
            if (response.ok && !finished) onProgress(await response.json());
          } catch { /* the result request reports a lost connection */ }
          if (!finished) await new Promise(resolve => setTimeout(resolve, 500));
        }
      })();
      try {
        const response = await call('/mix-song', {...json({plan, mix, progress_id: progressId}),signal});
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          const error = new Error(data.error || 'The local mix failed');
          error.status = response.status;
          throw error;
        }
        return {blob: await response.blob(), seconds: Number(response.headers.get('X-Mix-Seconds')) || null};
      } finally { finished = true;signal?.removeEventListener('abort',cancel);await polling;if(cancellation)await cancellation; }
    },
    async segment(original, start, duration, format = 'lossless') {
      if (!info?.audio_preview) throw new Error('Open the companion on this computer to export with your original audio.');
      const located = await call('/locate', json({name: original.name, size: original.size, fingerprint: original.fingerprint}));
      if (!located.ok) throw new Error(`${original.name} was not found on this computer.`);
      const {id} = await located.json();
      const response = await call('/segment', json({id, start, duration, format}));
      if (!response.ok) throw new Error(`Could not read ${original.name} on this computer.`);
      return await response.blob();
    },
  };
})();
