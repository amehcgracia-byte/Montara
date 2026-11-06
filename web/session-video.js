/* Match already-synchronized cameras to one detected session song. No new DSP. */
const SessionVideo = (() => {
  function songForClips(songs, clips) {
    const votes = [];
    for (const clip of Object.values(clips || {})) {
      if (clip.low_confidence || clip.unstable_sync || clip.error || !Number.isFinite(clip.offset_sec) || !(clip.duration_sec > 0)) continue;
      const start = clip.offset_sec, end = start + clip.duration_sec;
      const ranked = songs.map(song => ({song, overlap: Math.max(0, Math.min(end, song.end) - Math.max(start, song.start))}))
        .sort((a, b) => b.overlap - a.overlap);
      if (!ranked[0] || ranked[0].overlap < Math.min(3, clip.duration_sec * .5)) continue;
      if (ranked[1] && ranked[1].overlap >= ranked[0].overlap * .8) throw new Error('A camera spans several songs. Review the song boundaries before making this video.');
      votes.push(ranked[0].song);
    }
    if (!votes.length) throw new Error('Could not confidently locate the camera audio in this session. Review the song boundaries; no song was mixed automatically.');
    if (new Set(votes.map(song => song.id)).size !== 1) throw new Error('These videos belong to different songs. Make one song video at a time.');
    return votes[0];
  }
  function excerptForClips(duration, clips) {
    const items = Object.values(clips || {});
    if (!(duration > 0) || !items.length || items.some(clip => clip.low_confidence || clip.unstable_sync || clip.error ||
        !Number.isFinite(clip.offset_sec) || !Number.isFinite(clip.duration_sec) || !(clip.duration_sec > 0))) {
      throw new Error('Could not confidently locate every camera in the tracks. Review the audio range before mixing.');
    }
    const ranges = items.map(clip => ({start:Math.max(0,clip.offset_sec), end:Math.min(duration,clip.offset_sec+clip.duration_sec)}))
      .sort((a,b) => a.start-b.start);
    let start=ranges[0].start, end=ranges[0].end;
    for (const range of ranges) {
      if (range.end-range.start<.5 || range.start>end+1) {
        throw new Error('These cameras cover separate sections. Review the audio range before mixing.');
      }
      end=Math.max(end,range.end);
    }
    if (end-start<.5 || end-start>3600) throw new Error('Choose one camera section of up to one hour before mixing.');
    return {id:1,name:'Video excerpt',start,end,selected:true,confirmed:true};
  }
  return {songForClips,excerptForClips};
})();
