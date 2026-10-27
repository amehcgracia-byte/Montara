/* Files are sliced on disk; never read a multi-GB original into one ArrayBuffer. */
let activePartUploads = 0;
const waitingPartUploads = [];
async function sendResumableUpload(file, progress, registered = () => {}) {
  if (activePartUploads >= 2) await new Promise(resolve => waitingPartUploads.push(resolve));
  else activePartUploads += 1;
  try {
    const limits = await api('/montara/uploads');
    if (file.size > limits.max_file_bytes) throw new Error(`This test environment accepts up to ${Math.round(limits.max_file_bytes / 1048576)} MiB per file.`);
    const edges = await new Blob([file.slice(0, 65536), file.slice(Math.max(0, file.size - 65536))]).arrayBuffer();
    const fingerprint = [...new Uint8Array(await crypto.subtle.digest('SHA-256', edges))].map(n => n.toString(16).padStart(2, '0')).join('');
    let job = await api('/montara/uploads', {name: file.name, size: file.size, fingerprint});
    registered(job.id);
    let offset = job.received;
    progress(offset / file.size);
    while (!job.complete && offset < file.size) {
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
    return await api(`/montara/uploads/${job.id}/finish`, {});
  } finally {
    const next = waitingPartUploads.shift();
    if (next) next(); else activePartUploads -= 1;
  }
}
