/* Optional Stage session flow; the single-song journey stays unchanged. */
const fullSession = { id: null, active: false, data: null, busy: false };
try { $('#sessionResume').hidden = !localStorage.getItem('montara-session'); } catch { /* private storage unavailable */ }
$('#sessionResume').onclick = async () => {
  try {
    fullSession.id = localStorage.getItem('montara-session');
    fullSession.active = true;
    show('sessionReview'); $('#sessionSongs').hidden = false; $('#sessionResults').replaceChildren();
    const data = await waitSession(await api(`/montara/session/${fullSession.id}`));
    if (data.songs) drawSessionSongs(data.songs);
    if (data.results?.length) drawSessionResults(data);
  } catch (error) {
    if (error.session?.songs) drawSessionSongs(error.session.songs);
    if (error.session?.results?.length) drawSessionResults(error.session);
    toast(error.message, true);
  }
};
$('#stageAudioOnly').addEventListener('change', renderFiles);
$('#fullSessionOn').addEventListener('change', renderFiles);
$('#sessionBack').onclick = () => {
  if (fullSession.busy) return toast('Cancel the session job first.');
  fullSession.active = false;
  show('footage');
};
$('#sessionCancel').onclick = async () => {
  try { await api(`/montara/session/${fullSession.id}/cancel`, {}); $('#sessionStatus').textContent = 'Cancelling…'; }
  catch (error) { toast(error.message, true); }
};

const SESSION_STAGE = {
  detecting: ['Finding the songs in your session', 'Listening to every track to find where each song starts and ends.'],
  preparing: ['Preparing the mixer preview', 'Cutting a short excerpt of the first selected song for the mixer.'],
  rendering: ['Mixing and mastering each song', 'Every selected song gets its own automatic mix and master.'],
};
const sessionClock = { status: null, started: 0, songStarted: 0, songIndex: -1, perSong: [] };

const minutesLeft = seconds => seconds < 50 ? 'less than a minute left' : `about ${Math.round(seconds / 60)} min left`;

function showSessionProgress(data) {
  fullSession.data = data;
  fullSession.busy = ['detecting', 'preparing', 'rendering'].includes(data.status);
  const now = performance.now() / 1000;
  if (sessionClock.status !== data.status) Object.assign(sessionClock, { status: data.status, started: now, songStarted: now, songIndex: -1, perSong: [] });
  const [title, hint] = SESSION_STAGE[data.status] || [];
  $('#sessionHint').textContent = hint || 'Review the suggested boundaries and choose the songs. Each song gets its own automatic mix; your fader moves apply on top.';
  $('#sessionCancel').hidden = !fullSession.busy;
  $('#sessionBack').disabled = fullSession.busy;
  $('#sessionWorking').hidden = !fullSession.busy && !data.error;
  $('#sessionWorking').classList.toggle('done', !fullSession.busy);
  $('#sessionProgress').hidden = !fullSession.busy;
  const percent = Math.max(0, Math.min(100, Number(data.progress?.progress || 0)));
  $('#sessionProgress').value = percent;
  const detail = data.progress?.stage_detail || '';
  $('#sessionStatus').textContent = data.error || (fullSession.busy ? `${title}${detail && detail !== data.status ? ' · ' + detail : ''}…` : '');
  // Remaining time from the pace so far; songs are timed one by one while rendering.
  let eta = '';
  const selected = (data.songs || []).filter(s => s.selected);
  if (data.status === 'rendering' && selected.length) {
    const done = (data.results || []).length;
    if (done !== sessionClock.songIndex) { if (sessionClock.songIndex >= 0) sessionClock.perSong.push(now - sessionClock.songStarted); sessionClock.songIndex = done; sessionClock.songStarted = now; }
    const seconds = song => Math.max(1, song.end - song.start);
    const pace = sessionClock.perSong.length ? sessionClock.perSong.reduce((a, b) => a + b, 0) / selected.slice(0, sessionClock.perSong.length).reduce((a, s) => a + seconds(s), 0) : null;
    const current = selected[done];
    const currentShare = pace && current ? Math.min(.97, (now - sessionClock.songStarted) / (pace * seconds(current))) : 0;
    if (pace) eta = minutesLeft(Math.max(0, pace * selected.slice(done).reduce((a, s) => a + seconds(s), 0) - (now - sessionClock.songStarted)));
    else eta = current ? `Song ${done + 1} of ${selected.length} · timing the first song…` : '';
    const bars = $('#sessionBars');
    if (bars.children.length !== selected.length) bars.innerHTML = selected.map(() => '<i></i>').join('');
    [...bars.children].forEach((bar, i) => bar.style.setProperty('--p', i < done ? '1' : i === done ? (currentShare || .06).toFixed(3) : '0'));
    bars.hidden = false;
  } else {
    const bars = $('#sessionBars');
    bars.hidden = data.status !== 'done' || !bars.children.length;
    // Finished: every exported song is green (the last poll may arrive after the final song).
    if (data.status === 'done') [...bars.children].forEach((bar, i) => bar.style.setProperty('--p', i < (data.results || []).length ? '1' : '0'));
    if (fullSession.busy && percent > 2) {
      const elapsed = now - sessionClock.started;
      eta = minutesLeft(elapsed * (100 - percent) / percent);
    }
  }
  $('#sessionEta').textContent = fullSession.busy ? eta : '';
}

async function waitSession(initial) {
  let data = initial;
  while (['detecting', 'preparing', 'rendering'].includes(data.status)) {
    showSessionProgress(data);
    await new Promise(resolve => setTimeout(resolve, 800));
    data = await api(`/montara/session/${fullSession.id}`);
  }
  showSessionProgress(data);
  if (data.status === 'failed' || data.status === 'cancelled') {
    const error = new Error(data.error || 'Session stopped.'); error.session = data; throw error;
  }
  return data;
}

async function openFullSession() {
  if (!audioTracks().length) return toast('Add the audio tracks of your session first.', true);
  fullSession.active = true;
  show('sessionReview');
  $('#sessionSongs').hidden = false;
  $('#sessionSongs').replaceChildren(); $('#sessionResults').replaceChildren();
  $('#sessionMix').hidden = true;
  try {
    const job = await api('/montara/session', { tracks: audioTracks().map(f => f.path) });
    fullSession.id = job.id;
    try { localStorage.setItem('montara-session', job.id); $('#sessionResume').hidden = false; } catch { /* optional */ }
    const data = await waitSession(job);
    drawSessionSongs(data.songs);
    $('#sessionStatus').textContent = data.ai_review?.status === 'reviewed' ? `AI reviewed ${data.ai_review.submitted_cuts} of ${data.ai_review.total_cuts} cuts · ${data.ai_review.value.summary}` : 'Acoustic suggestions — check each song before continuing.';
  } catch (error) { toast(error.message, true); }
}

function drawSessionSongs(songs) {
  fullSession.data.songs = songs;
  $('#sessionSongs').innerHTML = songs.map((song, i) => `<div class="session-song" data-session-song="${i}">
    <label><input data-song-field="selected" type="checkbox" ${song.selected ? 'checked' : ''}> ${String(i + 1).padStart(2, '0')}</label>
    <input aria-label="Song name" data-song-field="name" value="${escapeHtml(song.name)}" maxlength="80">
    <label>From <input aria-label="Song start in seconds" data-song-field="start" type="number" step=".1" min="0" max="${fullSession.data.duration}" value="${song.start.toFixed(1)}"></label>
    <label>To <input aria-label="Song end in seconds" data-song-field="end" type="number" step=".1" min="0" max="${fullSession.data.duration}" value="${song.end.toFixed(1)}"></label>
    <button class="btn ghost small" data-song-split="${i}" type="button">Split</button>
    <button class="btn ghost small" data-song-remove="${i}" type="button" ${songs.length === 1 ? 'disabled' : ''}>Remove</button>
    ${song.review_note ? `<p class="hint">${song.needs_review ? 'Review · ' : ''}${escapeHtml(song.review_note)}</p>` : ''}
  </div>`).join('');
  $('#sessionMix').hidden = false;
}

function readSessionSongs() {
  return [...document.querySelectorAll('[data-session-song]')].map(row => Object.fromEntries(
    [...row.querySelectorAll('[data-song-field]')].map(input => [input.dataset.songField,
      input.type === 'checkbox' ? input.checked : input.type === 'number' ? Number(input.value) : input.value])
  ));
}

$('#sessionSongs').onclick = event => {
  const split = event.target.closest('[data-song-split]'), remove = event.target.closest('[data-song-remove]');
  if (!split && !remove) return;
  const songs = readSessionSongs(), index = Number((split || remove).dataset[split ? 'songSplit' : 'songRemove']);
  if (split) {
    const song = songs[index], middle = (song.start + song.end) / 2;
    if (song.end - song.start < 1) return toast('This interval is too short to split.');
    songs.splice(index, 1, {...song, end: middle}, {...song, start: middle, name: `${song.name} · 2`});
  } else songs.splice(index, 1);
  drawSessionSongs(songs);
};

$('#sessionMix').onclick = async () => {
  $('#sessionMix').disabled = true;
  try {
    const prepared = await waitSession(await api(`/montara/session/${fullSession.id}/prepare`, {songs: readSessionSongs()}));
    await openMixer(prepared.preview_tracks);
    $('#mixStatusText').textContent = `Preview: first ${Math.ceil(mix.plan.duration)} seconds of the first selected song. Fader adjustments apply to all selected songs.`;
  } catch (error) { toast(error.message, true); }
  finally { $('#sessionMix').disabled = false; }
};

async function renderFullSession() {
  stopMix();
  $('#useMix').disabled = true;
  const mixJob = await api(`/montara/mix/${mix.job}`);
  const payload = {
    reference: mixJob.reference,
    // Each song keeps its own automatic mix, computed from that song. Only what the
    // person changed travels: fader moves as offsets, mutes they toggled, effects they
    // switched on. The preview's own automatic values (a track it found silent, its
    // balance) must not be imposed on every song.
    faders: Object.fromEntries(mix.plan.tracks.map(t => [t.file, Number(t.fader_db || 0) - Number(t.auto_fader_db ?? t.fader_db ?? 0)]).filter(([, v]) => Math.abs(v) > .05)),
    mutes: Object.fromEntries(mix.plan.tracks.filter(t => Boolean(t.mute) !== Boolean(t.auto_mute ?? t.mute)).map(t => [t.file, Boolean(t.mute)])),
  };
  const effects = Object.fromEntries(mix.plan.tracks.filter(t => ['reverb', 'delay'].some(key => t.fx?.[key]?.enabled))
    .map(t => [t.file, Object.fromEntries(['reverb', 'delay'].map(key => [key, t.fx?.[key]?.enabled ? t.fx[key].amount / 100 : 0]))]));
  if (Object.keys(effects).length) payload.effects = effects;  // otherwise the mixer's automatic space and echo stay on
  show('sessionReview'); $('#sessionSongs').hidden = true; $('#sessionMix').hidden = true;
  try {
    await sendSessionOriginals();
    const data = await waitSession(await api(`/montara/session/${fullSession.id}/render`, payload));
    $('#sessionStatus').textContent = 'Your selected songs are ready.';
    drawSessionResults(data);
  } catch (error) { toast(error.message, true); }
  finally { $('#sessionSongs').hidden = false; $('#useMix').disabled = false; }
}

// Tracks sent as light previews: the export uses the originals, but only the song ranges.
async function sendSessionOriginals() {
  let {originals} = await api(`/montara/session/${fullSession.id}/originals`);
  const missing = originals.filter(w => !w.received);
  const started = performance.now();
  let bytes = 0;
  for (const [index, w] of missing.entries()) {
    $('#sessionWorking').hidden = false; $('#sessionWorking').classList.remove('done');
    $('#sessionHint').textContent = 'Sending only the song ranges of your original tracks, lossless, from this computer.';
    $('#sessionStatus').textContent = `Original audio ${index + 1} / ${missing.length} · ${w.song_name} · ${w.original.name}…`;
    $('#sessionProgress').hidden = false; $('#sessionProgress').value = 100 * index / missing.length;
    const spent = (performance.now() - started) / 1000;
    $('#sessionEta').textContent = index ? minutesLeft(spent / index * (missing.length - index)) : '';
    const blob = await montaraCompanion.segment(w.original, w.start, w.duration);
    bytes += blob.size;
    const ext = blob.type === 'audio/x-wavpack' ? '.wav.wv' : '.wav.flac';  // float originals: WavPack (FLAC has no float)
    const name = `${w.file.replace(/\.wav$/i, '')}${ext}`;
    let uploadId = null;
    await sendResumableUpload(new File([blob], name, {type: blob.type || 'audio/flac'}), () => {}, id => { uploadId = id; });
    originals = (await api(`/montara/session/${fullSession.id}/originals`, {song: w.song, file: w.file, upload_id: uploadId})).originals;
  }
  if (missing.length) console.info(`Montara: ${missing.length} original ranges, ${(bytes / 1e6).toFixed(0)} MB in ${((performance.now() - started) / 1000).toFixed(0)} s`);
}

function drawSessionResults(data) {
    $('#sessionResults').innerHTML = data.results.map(song => `<div class="session-song"><b>${escapeHtml(song.name)}</b>
      <audio controls preload="none" src="/montara/session/${fullSession.id}/result/${song.id}"></audio>
      <a class="btn ghost small" href="/montara/session/${fullSession.id}/result/${song.id}?download=1" download>Download</a></div>`).join('');
}
