/* Source roles and sync review policy. A confidence peak is not proof of sync. */
const SyncSelection = (() => {
  function review(files, clips, {start = 0, end = Infinity} = {}) {
    const result = {ready: [], silent: [], uncertain: []};
    for (const file of files) {
      if (file.usage === 'filler') continue;
      const clip = Object.values(clips || {}).find(c => [c.source_path, c.path].includes(file.path));
      if (clip?.no_audio) {result.silent.push(file); continue;}
      const overlap = clip && Math.min(end, clip.offset_sec + clip.duration_sec) - Math.max(start, clip.offset_sec);
      if (!clip || clip.low_confidence || clip.unstable_sync || clip.error || !Number.isFinite(clip.offset_sec) || !(overlap > .5)) {
        result.uncertain.push(file);
      } else result.ready.push(file);
    }
    return result;
  }
  return {review};
})();
