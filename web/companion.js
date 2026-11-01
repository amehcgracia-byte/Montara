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
    const controller = new AbortController();
    const timer = timeout ? setTimeout(() => controller.abort(), timeout) : null;
    try { return await fetch(BASE + path, {...options, signal: controller.signal}); }
    finally { if (timer) clearTimeout(timer); }
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
    /* Resolves to {file, original} with the small version, or null to upload the original. */
    async smallVersion(file, onProgress, cancelled = () => false, {preview = false} = {}) {
      if (!info || !this.helps(file)) return null;
      const audio = this.isAudio(file);
      preview = preview && audio && !!info.audio_preview;
      try {
        onProgress('Finding it on your computer', 0);
        const print = await fingerprint(file);
        const located = await call('/locate', json({name: file.name, size: file.size, fingerprint: print}));
        if (!located.ok) return null;
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
        const wavpack = blob.type === 'audio/x-wavpack';  // float originals: WavPack instead of FLAC
        const name = preview ? file.name + '.opus' : audio ? file.name + (wavpack ? '.wv' : '.flac') : file.name.replace(/\.[^.]+$/, '') + '.small.mp4';
        const type = preview ? 'audio/ogg' : audio ? blob.type || 'audio/flac' : 'video/mp4';
        return {file: new File([blob], name, {type}), preview, original: {name: file.name, size: file.size, lastModified: file.lastModified, fingerprint: print, companion: id}};
      } catch (error) {
        console.warn('Companion unavailable for this file', error);
        return null;
      }
    },
    /* One range of an original audio file; resolves to a Blob. 'opus' (Fast, high bitrate) when this
       companion can, otherwise lossless (FLAC, or WavPack for float). */
    canFastSegments() { return Boolean(info?.segment_formats?.includes('opus')); },
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
