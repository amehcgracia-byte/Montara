/* Talks to the Montara companion on the person's computer (companion/companion.py).
   When it is running, a dropped video is not uploaded: the companion finds the
   original by name, size and edge fingerprint, makes a small version (720p H.264,
   constant frame rate, SDR) and only that small version is uploaded. A WAV/AIFF becomes
   a lossless FLAC (name.wav.flac); the server restores the identical WAV. For a full session
   it becomes a light Opus preview (name.wav.opus); at export only the song ranges of the
   originals are sent, lossless (segment). Without the
   companion, or if it cannot help with a file, Montara uploads the original as before. */
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
  async function fingerprint(file) {
    const edges = await new Blob([file.slice(0, EDGE), file.slice(Math.max(0, file.size - EDGE))]).arrayBuffer();
    return [...new Uint8Array(await crypto.subtle.digest('SHA-256', edges))].map(n => n.toString(16).padStart(2, '0')).join('');
  }
  const json = (body) => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  return {
    get info() { return info; },
    async detect() {
      try {
        const response = await call('/health', {}, 1200);
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
      if (!response.ok) throw new Error('The companion could not save the video.');
      return (await response.json()).saved;
    },
    /* Identity probe for an original explicitly selected by the user.
       Never uploads file bytes; SHA-256 runs in the browser and /locate resolves
       only on this person's Companion. No server receives the identity. */
    /* Local proxy receipt, computed by Companion from its original and the
       finished proxy bytes. An untrusted browser must never be the authority
       that certifies this receipt to Stage. */
    async localProxyReceipt(id, original) {
      if (!/^[a-f0-9]{24}$/.test(id || '')) throw new Error('Invalid Companion proxy identity');
      const response = await call(`/proxies/${id}/receipt`);
      if (!response.ok) throw new Error('Companion has no verified proxy receipt');
      const receipt = await response.json();
      if (!receipt?.original || !/^[a-f0-9]{64}$/.test(receipt.proxy_sha256 || '') ||
          receipt.original.name !== original.name ||
          receipt.original.size !== original.size ||
          receipt.original.fingerprint !== original.fingerprint)
        throw new Error('Companion original and proxy receipt do not match');
      return receipt;
    },
    async verifyLocalOriginal(file) {
      if (!file || !this.isVideo(file)) throw new Error('Choose a local video original');
      if (!info && !(await this.detect())) throw new Error('Montara Companion is not available');
      const identity = {name:file.name,size:file.size,fingerprint:await fingerprint(file)};
      const located = await this.locateOriginal(identity);
      return {identity,located};
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
    /* Exact existing local U21 handoff endpoint; never send originals to web server. */
    async startHandoffVideo(body) {
      if (!info && !(await this.detect())) throw new Error('Montara Companion is not available');
      if (!info?.local_video) throw new Error('Install the Companion local video renderer first');
      const response = await call('/video-renders/handoff', json(body));
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(result.error || 'Could not start local handoff export');
        error.status = response.status; throw error;
      }
      if (result.local_originals !== true || !/^[a-f0-9]{32}$/.test(result.id || ''))
        throw new Error('Unexpected Companion export response');
      return result.id;
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
      try {
        onProgress('Finding it on your computer', 0);
        const print = await fingerprint(file);
        const located = await call('/locate', json({name: file.name, size: file.size, fingerprint: print}));
        if (!located.ok) return located.status === 404 ? {missing: true} : null;
        const located_ = await located.json();
        const {id} = await (await call('/proxies', json({id: located_.id, preview}))).json();
        for (;;) {
          if (cancelled()) return null;
          const state = await (await call(`/proxies/${id}`)).json();
          if (state.status === 'ready') break;
          if (state.status === 'skipped' || state.status === 'failed') { console.info('Companion:', state.reason || state.error); return null; }
          onProgress(preview ? 'Light preview' : audio ? 'Lossless copy' : 'Small version', state.progress || 0);
          await new Promise(resolve => setTimeout(resolve, 800));
        }
        const download = await call(`/proxies/${id}/file`);
        if (!download.ok) return null;
        const blob = await download.blob();
        const receipt = !audio ? await this.localProxyReceipt(id, {name:file.name,size:file.size,fingerprint:print}) : null;
        const wavpack = blob.type === 'audio/x-wavpack';  // float originals: WavPack instead of FLAC
        const name = preview ? file.name + '.opus' : audio ? file.name + (wavpack ? '.wv' : '.flac') : file.name.replace(/\.[^.]+$/, '') + '.small.mp4';
        const type = preview ? 'audio/ogg' : audio ? blob.type || 'audio/flac' : 'video/mp4';
        return {file: new File([blob], name, {type}), preview, original: {name: file.name, size: file.size, lastModified: file.lastModified, fingerprint: print, companion: id}, provenance_receipt:receipt};
      } catch (error) {
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
