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

function showSessionProgress(data) {
  fullSession.data = data;
  fullSession.busy = ['detecting', 'preparing', 'rendering'].includes(data.status);
  $('#sessionCancel').hidden = !fullSession.busy;
  $('#sessionBack').disabled = fullSession.busy;
  $('#sessionProgress').hidden = !fullSession.busy;
  $('#sessionProgress').value = Math.max(0, Math.min(100, Number(data.progress?.progress || 0)));
  $('#sessionStatus').textContent = data.error || data.progress?.stage_detail || data.progress?.current_stage || data.status;
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
    faders: Object.fromEntries(mix.plan.tracks.map(t => [t.file, MixLevels.offset(t)])),
    base_gains: Object.fromEntries(mix.plan.tracks.map(t => [t.file, Number(t.base_gain_db || 0)])),
    mutes: Object.fromEntries(mix.plan.tracks.map(t => [t.file, Boolean(t.mute)])),
    effects: Object.fromEntries(mix.plan.tracks.map(t => [t.file, Object.fromEntries(['reverb', 'delay'].map(key => [key, t.fx?.[key]?.enabled ? t.fx[key].amount / 100 : 0]))]))
  };
  show('sessionReview'); $('#sessionSongs').hidden = true; $('#sessionMix').hidden = true;
  try {
    const data = await waitSession(await api(`/montara/session/${fullSession.id}/render`, payload));
    $('#sessionStatus').textContent = 'Your selected songs are ready.';
    drawSessionResults(data);
  } catch (error) { toast(error.message, true); }
  finally { $('#sessionSongs').hidden = false; $('#useMix').disabled = false; }
}

function drawSessionResults(data) {
    $('#sessionResults').innerHTML = data.results.map(song => `<div class="session-song"><b>${escapeHtml(song.name)}</b>
      <audio controls preload="none" src="/montara/session/${fullSession.id}/result/${song.id}"></audio>
      <a class="btn ghost small" href="/montara/session/${fullSession.id}/result/${song.id}?download=1" download>Download</a></div>`).join('');
}
