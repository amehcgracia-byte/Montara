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
    fullSession.id = job.id; fullSession.mixes = {};
    try { localStorage.setItem('montara-session', job.id); $('#sessionResume').hidden = false; } catch { /* optional */ }
    const data = await waitSession(job);
    drawSessionSongs(data.songs);
    $('#sessionStatus').textContent = data.ai_review?.status === 'reviewed' ? `AI reviewed ${data.ai_review.submitted_cuts} of ${data.ai_review.total_cuts} cuts · ${data.ai_review.value.summary}` : 'Acoustic suggestions — check each song before continuing.';
  } catch (error) { toast(error.message, true); }
}

// ---------- song list: waveform, handles, listen, per-song mixer ----------
// Songs live in fullSession.data.songs; the page edits that list directly.
const sessionWave = { id: null, data: null, loading: null };
const sessionPlayer = { audio: null, index: -1, raf: 0 };
fullSession.mixes = fullSession.mixes || {};   // song id -> changes made in that song's mixer

// clock() comes from montara.js (m:ss).
const songList = () => fullSession.data.songs;

async function loadSessionWave() {
  if (sessionWave.id === fullSession.id && (sessionWave.data || sessionWave.loading)) return sessionWave.loading || sessionWave.data;
  sessionWave.id = fullSession.id; sessionWave.data = null;
  sessionWave.loading = api(`/montara/session/${fullSession.id}/waveform`).then(data => (sessionWave.data = data)).catch(() => null).finally(() => { sessionWave.loading = null; });
  return sessionWave.loading;
}

// What each row shows: the song plus a margin, so a handle can be dragged outwards.
function songView(i) {
  const songs = songList(), song = songs[i], length = song.end - song.start;
  const pad = Math.min(90, Math.max(12, length * .15));
  return { from: Math.max(0, song.start - pad), to: Math.min(fullSession.data.duration, song.end + pad) };
}

function drawSessionSongs(songs) {
  if (songs) fullSession.data.songs = songs;
  stopSongPreview();
  const list = songList();
  $('#sessionSongs').innerHTML = list.map((song, i) => `<div class="session-song" data-session-song="${i}">
    <div class="song-head">
      <input data-song-field="selected" type="checkbox" ${song.selected ? 'checked' : ''} aria-label="Export song ${i + 1}">
      <button class="song-play" type="button" data-song-play="${i}" aria-label="Listen to song ${i + 1}">▶</button>
      <span class="song-num">${String(i + 1).padStart(2, '0')}</span>
      <input aria-label="Song name" data-song-field="name" value="${escapeHtml(song.name)}" maxlength="80">
      ${fullSession.mixes[song.id] ? '<span class="song-tag">Own mix</span>' : ''}
      ${fullSession.data.uses_previews ? `<span class="song-tag confirm-state" data-confirm-state="${song.id}"></span>
      <button class="btn ghost small" data-song-confirm="${i}" type="button" ${song.confirmed ? 'hidden' : ''} title="These cuts are final: start sending this song's original audio now">Confirm</button>` : ''}
      <button class="btn ghost small" data-song-mixer="${i}" type="button">Mixer</button>
      <button class="btn ghost small" data-song-split="${i}" type="button">Split</button>
      <button class="btn ghost small" data-song-remove="${i}" type="button" ${list.length === 1 ? 'disabled' : ''}>Remove</button>
    </div>
    <div class="song-wave" data-song-wave="${i}">
      <canvas aria-hidden="true"></canvas>
      <i class="song-cut start" data-handle="start" role="slider" tabindex="0" aria-label="Start of song ${i + 1}" aria-valuetext="${clock(song.start)}"></i>
      <i class="song-cut end" data-handle="end" role="slider" tabindex="0" aria-label="End of song ${i + 1}" aria-valuetext="${clock(song.end)}"></i>
      <i class="song-playhead" hidden></i>
      <span class="song-time">${clock(song.start)} – ${clock(song.end)} · ${clock(song.end - song.start)}</span>
    </div>
    ${song.review_note ? `<p class="hint">${song.needs_review ? 'Review · ' : ''}${escapeHtml(song.review_note)}</p>` : ''}
  </div>`).join('');
  list.forEach((_, i) => paintSong(i));
  paintUploadState();
  loadSessionWave().then(() => list.forEach((_, i) => paintSong(i)));
  $('#sessionMix').hidden = false;
  $('#sessionMix').textContent = 'Export selected songs';
}

function paintSong(i) {
  const row = document.querySelector(`[data-song-wave="${i}"]`);
  if (!row) return;
  const song = songList()[i], view = songView(i), canvas = row.querySelector('canvas');
  const width = row.clientWidth || 600, height = row.clientHeight || 64, ratio = devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio;
  const g = canvas.getContext('2d'); g.scale(ratio, ratio); g.clearRect(0, 0, width, height);
  const x = t => (t - view.from) / Math.max(.001, view.to - view.from) * width;
  const wave = sessionWave.data, styles = getComputedStyle(document.documentElement);
  const accent = styles.getPropertyValue('--accent').trim() || '#FF4F2E', muted = styles.getPropertyValue('--muted').trim() || '#8a8a8f';
  if (wave) {
    for (let px = 0; px < width; px++) {
      const t0 = view.from + px / width * (view.to - view.from), t1 = view.from + (px + 1) / width * (view.to - view.from);
      let peak = 0;
      for (let c = Math.floor(t0 / wave.step); c <= Math.floor(t1 / wave.step); c++) peak = Math.max(peak, wave.peaks[c] || 0);
      const h = Math.max(1, peak / 255 * (height - 8));
      const inside = t1 > song.start && t0 < song.end;
      g.fillStyle = inside ? accent : muted; g.globalAlpha = inside ? .9 : .35;
      g.fillRect(px, (height - h) / 2, 1, h);
    }
    g.globalAlpha = 1;
  } else {
    g.fillStyle = muted; g.globalAlpha = .25; g.fillRect(0, height / 2 - 1, width, 2); g.globalAlpha = 1;
  }
  row.querySelector('.start').style.left = `${x(song.start)}px`;
  row.querySelector('.end').style.left = `${x(song.end)}px`;
  row.querySelector('.song-time').textContent = `${clock(song.start)} – ${clock(song.end)} · ${clock(song.end - song.start)}`;
}

// Drag a handle: the start can not pass the previous song's end, nor the end the next song's start.
$('#sessionSongs').addEventListener('pointerdown', event => {
  const handle = event.target.closest('[data-handle]');
  if (!handle) return;
  const row = handle.closest('[data-song-wave]'), i = Number(row.dataset.songWave), view = songView(i);
  const songs = songList(), song = songs[i], rect = row.getBoundingClientRect();
  handle.setPointerCapture(event.pointerId);
  const move = e => {
    const t = view.from + Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)) * (view.to - view.from);
    if (handle.dataset.handle === 'start') song.start = Math.max(i ? songs[i - 1].end : 0, Math.min(t, song.end - 1));
    else song.end = Math.min(i < songs.length - 1 ? songs[i + 1].start : fullSession.data.duration, Math.max(t, song.start + 1));
    song.start = Math.round(song.start * 10) / 10; song.end = Math.round(song.end * 10) / 10;
    if (song.confirmed) { song.confirmed = false; const button = document.querySelector(`[data-song-confirm="${i}"]`); if (button) button.hidden = false; paintUploadState(); }
    handle.setAttribute('aria-valuetext', clock(song[handle.dataset.handle]));
    paintSong(i);
  };
  const up = () => { handle.removeEventListener('pointermove', move); handle.removeEventListener('pointerup', up); paintSong(i); };
  handle.addEventListener('pointermove', move); handle.addEventListener('pointerup', up);
});
// Keyboard: arrows move a handle by one second (shift: ten).
$('#sessionSongs').addEventListener('keydown', event => {
  const handle = event.target.closest('[data-handle]');
  if (!handle || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
  event.preventDefault();
  const i = Number(handle.closest('[data-song-wave]').dataset.songWave), songs = songList(), song = songs[i];
  const step = (event.shiftKey ? 10 : 1) * (event.key === 'ArrowLeft' ? -1 : 1);
  if (handle.dataset.handle === 'start') song.start = Math.max(i ? songs[i - 1].end : 0, Math.min(song.start + step, song.end - 1));
  else song.end = Math.min(i < songs.length - 1 ? songs[i + 1].start : fullSession.data.duration, Math.max(song.end + step, song.start + 1));
  paintSong(i);
});
$('#sessionSongs').addEventListener('input', event => {
  const row = event.target.closest('[data-session-song]'), field = event.target.dataset.songField;
  if (!row || !field) return;
  songList()[Number(row.dataset.sessionSong)][field] = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
});
addEventListener('resize', () => { if (!$('#sessionReview').hidden && fullSession.data?.songs) songList().forEach((_, i) => paintSong(i)); });

// One listening copy of the whole session, made once on the server; the page only
// seeks in it, so moving cuts, switching songs or jumping to a point never waits.
function sessionAudio() {
  if (sessionPlayer.audio?.dataset.session !== fullSession.id) {
    sessionPlayer.audio?.pause();
    const audio = new Audio(`/montara/session/${fullSession.id}/listen`);
    audio.preload = 'auto'; audio.dataset.session = fullSession.id;
    audio.addEventListener('error', () => { if (sessionPlayer.audio === audio) { stopSongPreview(); toast('Could not play the session. Try again in a moment.', true); } });
    sessionPlayer.audio = audio;
  }
  return sessionPlayer.audio;
}

function stopSongPreview() {
  sessionPlayer.audio?.pause();
  cancelAnimationFrame(sessionPlayer.raf);
  document.querySelectorAll('.song-play.on').forEach(b => { b.classList.remove('on'); b.textContent = '▶'; });
  document.querySelectorAll('.song-playhead').forEach(p => { p.hidden = true; });
  sessionPlayer.index = -1;
}

// Play song i from `from` (seconds in the session) until its end, wherever its end is by then.
async function playSong(i, from = null) {
  if (sessionPlayer.index === i && from === null) return stopSongPreview();
  stopSongPreview();
  const songs = songList(), song = songs[i], audio = sessionAudio();
  const button = document.querySelector(`[data-song-play="${i}"]`);
  sessionPlayer.index = i; button?.classList.add('on'); if (button) button.textContent = '■';
  const start = from ?? song.start;
  if (audio.readyState < 1) await new Promise(resolve => audio.addEventListener('loadedmetadata', resolve, { once: true }));
  audio.currentTime = start;
  const tick = () => {
    if (sessionPlayer.index !== i) return;
    const t = audio.currentTime, row = document.querySelector(`[data-song-wave="${i}"]`);
    if (t >= songList()[i].end) return stopSongPreview();
    if (row) {
      const view = songView(i), head = row.querySelector('.song-playhead');
      head.hidden = false; head.style.left = `${(t - view.from) / (view.to - view.from) * row.clientWidth}px`;
    }
    sessionPlayer.raf = requestAnimationFrame(tick);
  };
  try { await audio.play(); tick(); } catch (error) { if (sessionPlayer.index === i) { stopSongPreview(); toast('Could not play this song.', true); } }
}

// Click on a waveform (not on a handle): play from that point.
$('#sessionSongs').addEventListener('click', event => {
  const row = event.target.closest('[data-song-wave]');
  if (!row || event.target.closest('[data-handle]')) return;
  const i = Number(row.dataset.songWave), view = songView(i), rect = row.getBoundingClientRect();
  const t = view.from + (event.clientX - rect.left) / rect.width * (view.to - view.from);
  playSong(i, Math.max(0, Math.min(t, songList()[i].end - .2)));
});

// Mixer for one song. The first time it prepares an excerpt of the busiest part of that
// song; afterwards it reopens at once, with the changes the person saved.
fullSession.mixCache = fullSession.mixCache || {};
const songKey = song => `${fullSession.id}:${song.start}-${song.end}`;

function applySavedMix(changes) {
  if (!changes) return;
  const keys = { eq_low_cut_hz: ['low', 'hz'], eq_mid_gain_db: ['mid', 'db'], eq_air_gain_db: ['air', 'db'], eq_high_cut_hz: ['high', 'hz'] };
  for (const t of mix.plan.tracks) {
    if (changes.faders?.[t.file] !== undefined) t.fader_db = Number(t.auto_fader_db) + Number(changes.faders[t.file]);
    if (changes.mutes?.[t.file] !== undefined) t.mute = changes.mutes[t.file];
    for (const [key, value] of Object.entries(changes.eq?.[t.file] || {})) { const [slot, field] = keys[key]; if (t.eq?.[slot]) t.eq[slot][field] = value; }
    for (const [effect, amount] of Object.entries(changes.effects?.[t.file] || {})) {
      t.fx ||= { reverb: { enabled: false, amount: 35 }, delay: { enabled: false, amount: 35 } };
      t.fx[effect] = { enabled: amount > 0, amount: amount > 0 ? Math.round(amount * 100) : t.fx[effect]?.amount ?? 35 };
    }
  }
}

async function openSongMixer(i) {
  const song = songList()[i];
  stopSongPreview();
  fullSession.mixSong = song.id;
  const cached = fullSession.mixCache[song.id];
  try {
    if (cached && cached.key === songKey(song)) {
      Object.assign(mix, { job: cached.job, plan: cached.plan, buffers: cached.buffers, fxBuffers: cached.fxBuffers, offset: 0 });
      show('mix'); stopMix();
      renderStrips();
      $$('#strips input, #strips button').forEach((el, index) => { el.disabled = false; });
      $$('#strips .strip').forEach((strip, index) => { if (mix.plan.tracks[index].active === false) strip.querySelectorAll('input,button').forEach(el => { el.disabled = true; }); });
      $('#mixStatus').classList.add('done'); $('#transport').hidden = false; $('#referenceRow').hidden = false;
      $('#useMix').disabled = false; $('#playMix').disabled = false; $('#resetMix').disabled = false; $('#mixBack').disabled = false;
    } else {
      const prepared = await waitSession(await api(`/montara/session/${fullSession.id}/prepare`, { songs: songList(), song: song.id }));
      drawSessionSongs(prepared.songs);
      await openMixer(prepared.preview_tracks);
      applySavedMix(fullSession.mixes[song.id]);
      renderStrips();
      $$('#strips .strip').forEach((strip, index) => { if (mix.plan.tracks[index].active === false) strip.querySelectorAll('input,button').forEach(el => { el.disabled = true; }); });
      fullSession.mixCache[song.id] = { key: songKey(song), job: mix.job, plan: mix.plan, buffers: mix.buffers, fxBuffers: mix.fxBuffers };
    }
    $('#useMix').textContent = 'Save mix for this song';
    $('#mixStatusText').textContent = `${song.name}: ${Math.ceil(mix.plan.duration)} s from the busiest part. Changes apply to this song only; the others keep their automatic mix.`;
  } catch (error) { toast(error.message, true); show('sessionReview'); }
}

$('#sessionSongs').onclick = event => {
  const play = event.target.closest('[data-song-play]');
  if (play) return playSong(Number(play.dataset.songPlay));
  const confirm = event.target.closest('[data-song-confirm]');
  if (confirm) return confirmSong(Number(confirm.dataset.songConfirm));
  const mixer = event.target.closest('[data-song-mixer]');
  if (mixer) return openSongMixer(Number(mixer.dataset.songMixer));
  const split = event.target.closest('[data-song-split]'), remove = event.target.closest('[data-song-remove]');
  if (!split && !remove) return;
  const songs = songList().map(s => ({...s})), index = Number((split || remove).dataset[split ? 'songSplit' : 'songRemove']);
  if (split) {
    const song = songs[index], middle = Math.round((song.start + song.end) / 2 * 10) / 10;
    if (song.end - song.start < 2) return toast('This song is too short to split.');
    songs.splice(index, 1, {...song, end: middle}, {...song, id: undefined, start: middle, name: `${song.name} · 2`});
  } else songs.splice(index, 1);
  // Songs are numbered by position on the server: keep each saved mix with its song.
  const mixes = {};
  songs.forEach((song, j) => { if (song.id !== undefined && fullSession.mixes[song.id]) mixes[j + 1] = fullSession.mixes[song.id]; song.id = j + 1; });
  fullSession.mixes = mixes;
  drawSessionSongs(songs);
};

$('#sessionMix').onclick = () => renderFullSession();

// The changes made in the mixer, relative to its automatic mix: nothing else travels.
function mixChanges() {
  const changes = {
    faders: Object.fromEntries(mix.plan.tracks.map(t => [t.file, Number(t.fader_db || 0) - Number(t.auto_fader_db ?? t.fader_db ?? 0)]).filter(([, v]) => Math.abs(v) > .05)),
    mutes: Object.fromEntries(mix.plan.tracks.filter(t => Boolean(t.mute) !== Boolean(t.auto_mute ?? t.mute)).map(t => [t.file, Boolean(t.mute)])),
  };
  const effects = Object.fromEntries(mix.plan.tracks.filter(t => ['reverb', 'delay'].some(key => t.fx?.[key]?.enabled))
    .map(t => [t.file, Object.fromEntries(['reverb', 'delay'].map(key => [key, t.fx?.[key]?.enabled ? t.fx[key].amount / 100 : 0]))]));
  if (Object.keys(effects).length) changes.effects = effects;  // otherwise the automatic space and echo stay on
  const eq = eqChanges();
  if (Object.keys(eq).length) changes.eq = eq;
  return changes;
}

// "Save mix for this song" in the mixer: keep the changes, back to the list.
async function saveSongMix() {
  stopMix();
  const mixJob = await api(`/montara/mix/${mix.job}`);
  fullSession.mixes[fullSession.mixSong] = { ...mixChanges(), ...(mixJob.reference ? { reference: mixJob.reference } : {}) };
  $('#useMix').textContent = 'Use this mix';
  show('sessionReview');
  drawSessionSongs();
  toast('Mix saved for this song.');
}

async function renderFullSession() {
  stopSongPreview();
  const songs = songList();
  if (!songs.some(s => s.selected)) return toast('Select at least one song.', true);
  $('#sessionMix').hidden = true;
  try {
    // Save the boundaries first: the original ranges and the per-song mixes follow them.
    const saved = await api(`/montara/session/${fullSession.id}/songs`, { songs });
    fullSession.data.songs = saved.songs.map((s, j) => ({ ...s, confirmed: songs[j]?.confirmed }));
    const ids = new Set(saved.songs.map(s => String(s.id)));
    const per_song = Object.fromEntries(Object.entries(fullSession.mixes).filter(([id]) => ids.has(String(id))));
    // Mixing starts at once: each song begins on the server as soon as its original ranges
    // arrive, while this computer keeps sending the next ones.
    const started = await api(`/montara/session/${fullSession.id}/render`, { songs: saved.songs, per_song });
    for (const song of saved.songs.filter(s => s.selected)) await queueSongOriginals(song.id);
    const data = await waitSession(started);
    $('#sessionStatus').textContent = 'Your selected songs are ready.';
    drawSessionResults(data);
  } catch (error) { toast(error.message, true); }
  finally { $('#sessionMix').hidden = false; }
}

// ---------- original ranges, sent in the background ----------
// Tracks sent as light previews: the export uses the originals, but only the song ranges.
// A confirmed song starts sending at once, while the person keeps editing the others.
const uploader = { queue: [], seen: new Set(), running: false, done: 0, total: 0, bytes: 0, started: 0, bySong: {} };

async function queueSongOriginals(songId) {
  const { originals } = await api(`/montara/session/${fullSession.id}/originals?song=${songId}`);
  const tally = uploader.bySong[songId] ||= { done: 0, total: 0 };
  for (const w of originals) {
    const key = `${w.file}@${w.window.join('-')}`;
    if (uploader.seen.has(key)) continue;
    uploader.seen.add(key); tally.total++;
    if (w.received) { tally.done++; continue; }
    uploader.queue.push(w); uploader.total++;
  }
  paintUploadState();
  runUploader();
}

async function runUploader() {
  if (uploader.running) return;
  uploader.running = true; fullSession.sending = true;
  uploader.started ||= performance.now();
  try {
    while (uploader.queue.length) {
      const w = uploader.queue.shift();
      paintUploadState(w);
      const blob = await montaraCompanion.segment(w.original, w.start, w.duration);
      uploader.bytes += blob.size;
      const ext = blob.type === 'audio/x-wavpack' ? '.wav.wv' : '.wav.flac';  // float originals: WavPack (FLAC has no float)
      const name = `${w.file.replace(/\.wav$/i, '')}${ext}`;
      let uploadId = null;
      await sendResumableUpload(new File([blob], name, { type: blob.type || 'audio/flac' }), () => {}, id => { uploadId = id; });
      await api(`/montara/session/${fullSession.id}/originals`, { song: w.song, file: w.file, upload_id: uploadId });
      uploader.done++; (uploader.bySong[w.song] ||= { done: 0, total: 1 }).done++;
      paintUploadState();
    }
  } catch (error) {
    toast(`Original audio: ${error.message}`, true);
    for (const w of uploader.queue) uploader.seen.delete(`${w.file}@${w.window.join('-')}`);
    uploader.queue = [];
  } finally {
    uploader.running = false; fullSession.sending = false;
    paintUploadState();
  }
}

function paintUploadState(current = null) {
  const line = $('#sessionUpload');
  if (!line) return;
  const left = uploader.total - uploader.done;
  if (!uploader.total) line.textContent = '';
  else if (!left && !uploader.running) line.textContent = `Original audio sent from this computer (${(uploader.bytes / 1e6).toFixed(0)} MB).`;
  else {
    const spent = (performance.now() - uploader.started) / 1000;
    const eta = uploader.done ? ` · ${minutesLeft(spent / uploader.done * left)}` : '';
    line.textContent = `Sending original audio from this computer: ${uploader.done} / ${uploader.total}${current ? ` · ${current.song_name} · ${current.original.name}` : ''}${eta}`;
  }
  for (const song of fullSession.data?.songs || []) {
    const tag = document.querySelector(`[data-confirm-state="${song.id}"]`), tally = uploader.bySong[song.id];
    if (!tag) continue;
    tag.textContent = !song.confirmed ? '' : !tally || !tally.total ? 'Confirmed' : tally.done >= tally.total ? 'Ready' : `Sending ${tally.done}/${tally.total}`;
  }
}

// Confirm: these cuts are final, start sending this song's original ranges now.
async function confirmSong(i) {
  const list = songList();
  try {
    const saved = await api(`/montara/session/${fullSession.id}/songs`, { songs: list });
    fullSession.data.songs = saved.songs.map((s, j) => ({ ...s, confirmed: j === i || list[j]?.confirmed }));
    drawSessionSongs();
    await queueSongOriginals(saved.songs[i].id);
  } catch (error) { toast(error.message, true); }
}

function drawSessionResults(data) {
  const songs = data.results.map(song => `<div class="session-song"><b>${escapeHtml(song.name)}</b>
      <audio controls preload="none" src="/montara/session/${fullSession.id}/result/${song.id}"></audio>
      <a class="btn ghost small" href="/montara/session/${fullSession.id}/result/${song.id}?download=1" download>Download</a></div>`).join('');
  const all = data.results.length > 1 ? `<div class="session-song"><a class="btn primary small" href="/montara/session/${fullSession.id}/results.zip" download>Download all (${data.results.length} songs)</a></div>` : '';
  $('#sessionResults').innerHTML = songs + all;
}
