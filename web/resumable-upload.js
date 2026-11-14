/* Files are sliced on disk; never read a multi-GB original into one ArrayBuffer. */
// Audio and video have separate lanes so tracks upload alongside long videos
// instead of queueing behind them. Keep transfer concurrency bounded independently of media preparation.
const partLanes = { audio: { limit: 3, active: 0, waiting: [] }, video: { limit: 4, active: 0, waiting: [] } };
const AUDIO_NAME = /\.(wav|mp3|m4a|aiff?|flac|ogg|opus|wv)$/i;
const partLane = file => partLanes[AUDIO_NAME.test(file.name) ? 'audio' : 'video'];
async function sendResumableUpload(file, progress, registered = () => {}, cancelled = () => false, extra = {}, signal) {
  const lane = partLane(file);
  const transferTiming = {started: performance.now(), prepared: null, uploaded: null};
  if (lane.active >= lane.limit) await new Promise(resolve => lane.waiting.push(resolve));
  else lane.active += 1;
  const stopIfCancelled = () => { if (cancelled() || signal?.aborted) throw new Error('Upload removed.'); };
  const requestSignal = timeoutMs => {
    const timeout = AbortSignal.timeout(timeoutMs);
    return signal ? AbortSignal.any([signal, timeout]) : timeout;
  };
  try {
    stopIfCancelled();
    const limits = await api('/montara/uploads', undefined, requestSignal(90000));
    if (file.size > limits.max_file_bytes) throw new Error(`This test environment accepts up to ${Math.round(limits.max_file_bytes / 1048576)} MiB per file.`);
    const edges = await new Blob([file.slice(0, 65536), file.slice(Math.max(0, file.size - 65536))]).arrayBuffer();
    const fingerprint = [...new Uint8Array(await crypto.subtle.digest('SHA-256', edges))].map(n => n.toString(16).padStart(2, '0')).join('');
    let job = await api('/montara/uploads', {...extra, name: file.name, size: file.size, fingerprint}, requestSignal(90000));
    registered(job.id);
    let offset = job.received;
    const startingOffset = offset;
    let chunks = 0, retries = 0, attemptedBytes = 0;
    transferTiming.prepared = performance.now();
    progress(offset / file.size, "Uploading");
    while (!job.complete && offset < file.size) {
      stopIfCancelled();
      const end = Math.min(file.size, offset + job.chunk_size);
      let lastError;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          chunks++;
          attemptedBytes += end - offset;
          const response = await fetch(`/montara/uploads/${job.id}`, {method: 'PUT', signal: requestSignal(90000), headers: {'Upload-Offset': String(offset), 'Content-Type': 'application/octet-stream'}, body: file.slice(offset, end)});
          const data = await response.json();
          if (!response.ok) throw new Error(data.error?.message || 'Upload paused. Choose this file again to resume.');
          if (!Number.isSafeInteger(data.received) || data.received <= offset || data.received > file.size) throw new Error('Upload did not advance. Choose this file again to resume.');
          offset = data.received; lastError = null; break;
        } catch (error) {
          stopIfCancelled();
          lastError = error.name === 'TimeoutError'
            ? new Error('No upload progress. Add this file again to resume.')
            : error;
          if (attempt < 2) { retries++; progress(offset / file.size, "Connection interrupted · retrying"); }
          if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1)));
        }
      }
      if (lastError) throw lastError;
      progress(offset / file.size, "Uploading");
    }
    stopIfCancelled();
    transferTiming.uploaded = performance.now();
    progress(1, 'Preparing file');
    const completed = await api(`/montara/uploads/${job.id}/finish`, {}, requestSignal(120000));
    const finished = performance.now();
    const uploadSec = (transferTiming.uploaded - transferTiming.prepared) / 1000;
    console.info('[Montara upload timing]', {
      step: 'server transfer',
      source: extra.video_preview ? 'video proxy' : extra.original_video_consent ? 'explicit video original' : 'other',
      file_mib: +(file.size / 1048576).toFixed(1),
      resumed_mib: +(startingOffset / 1048576).toFixed(1),
      chunk_mib: +(job.chunk_size / 1048576).toFixed(1),
      chunks, retries,
      // Attempted payload includes retransmissions; TCP/HTTP overhead is not measured.
      attempted_mib: +(attemptedBytes / 1048576).toFixed(1),
      setup_sec: +((transferTiming.prepared - transferTiming.started) / 1000).toFixed(2),
      upload_sec: +uploadSec.toFixed(2),
      finalize_sec: +((finished - transferTiming.uploaded) / 1000).toFixed(2),
      total_sec: +((finished - transferTiming.started) / 1000).toFixed(2),
      transferred_mib: +((file.size - startingOffset) / 1048576).toFixed(1),
      throughput_mib_sec: +(((file.size - startingOffset) / 1048576) / Math.max(uploadSec, .001)).toFixed(2)
    });
    return completed;
  } finally {
    const next = lane.waiting.shift();
    if (next) next(); else lane.active -= 1;
  }
}
