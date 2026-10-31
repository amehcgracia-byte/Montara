/* Files are sliced on disk; never read a multi-GB original into one ArrayBuffer. */
// Audio and video have separate lanes so tracks upload alongside long videos
// instead of queueing behind them. Four files at a time per lane: no idle line while one file finishes.
const PART_LANE_LIMIT = 4;
const partLanes = { audio: { active: 0, waiting: [] }, video: { active: 0, waiting: [] } };
const AUDIO_NAME = /\.(wav|mp3|m4a|aiff?|flac|ogg|opus|wv)$/i;
const partLane = file => partLanes[AUDIO_NAME.test(file.name) ? 'audio' : 'video'];
async function sendResumableUpload(file, progress, registered = () => {}, cancelled = () => false, extra = {}) {
  const lane = partLane(file);
  if (lane.active >= PART_LANE_LIMIT) await new Promise(resolve => lane.waiting.push(resolve));
  else lane.active += 1;
  const stopIfCancelled = () => { if (cancelled()) throw new Error('Upload removed.'); };
  try {
    stopIfCancelled();
    const limits = await api('/montara/uploads');
    if (file.size > limits.max_file_bytes) throw new Error(`This test environment accepts up to ${Math.round(limits.max_file_bytes / 1048576)} MiB per file.`);
    const edges = await new Blob([file.slice(0, 65536), file.slice(Math.max(0, file.size - 65536))]).arrayBuffer();
    const fingerprint = [...new Uint8Array(await crypto.subtle.digest('SHA-256', edges))].map(n => n.toString(16).padStart(2, '0')).join('');
    let job = await api('/montara/uploads', {...extra, name: file.name, size: file.size, fingerprint});
    registered(job.id);
    let offset = job.received;
    progress(offset / file.size);
    while (!job.complete && offset < file.size) {
      stopIfCancelled();
      const end = Math.min(file.size, offset + job.chunk_size);
      let lastError;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          const response = await fetch(`/montara/uploads/${job.id}`, {method: 'PUT', headers: {'Upload-Offset': String(offset), 'Content-Type': 'application/octet-stream'}, body: file.slice(offset, end)});
          const data = await response.json();
          if (!response.ok) throw new Error(data.error?.message || 'Upload paused. Choose this file again to resume.');
          offset = data.received; lastError = null; break;
        } catch (error) {
          lastError = error;
          if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1)));
        }
      }
      if (lastError) throw lastError;
      progress(offset / file.size);
    }
    stopIfCancelled();
    return await api(`/montara/uploads/${job.id}/finish`, {});
  } finally {
    const next = lane.waiting.shift();
    if (next) next(); else lane.active -= 1;
  }
}
