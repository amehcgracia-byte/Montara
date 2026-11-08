/* Original identity comes from the saved upload, never a guessed proxy basename. */
const NativeExport = (() => {
  function originalFor(source, files) {
    if (source.original) return source.original;
    const exact = files.filter(f => f.path === source.path && f.original).map(f => f.original);
    const unique = [...new Map(exact.map(o => [[o.size, o.fingerprint].join('|'), o])).values()];
    return unique.length === 1 ? unique[0] : null;
  }
  function plan(recipe, unavailable) {
    const missing = new Set(unavailable);
    const byKey = new Map(recipe.sources.map(s => [s.key, s]));
    const diagnostics = [];
    const segments = recipe.segments.map((s, index) => {
      if (!missing.has(s.source)) return s;
      const source = byKey.get(s.source);
      const alternative = source?.optional === true && (recipe.fallbacks?.[index] || []).find(c =>
        !missing.has(c.source) && byKey.has(c.source) && byKey.get(c.source).optional !== true &&
        c.master_start_sec === s.master_start_sec && c.duration_sec === s.duration_sec);
      if (!alternative && source?.optional !== true) {
        diagnostics.push({shot:index + 1, source:s.source, status:'required', name:source?.original?.name || source?.path?.split('/').pop(), reason:!source?.original && /\.small\.mp4$/i.test(source?.path || '') ? 'Original association unavailable or ambiguous. Locate the original in Footage; the saved edit can be retained.' : 'This shot needs its original.'});
        return s;
      }
      diagnostics.push({shot:index + 1, source:s.source, replacement:alternative?.source ?? null, placeholder:alternative ? undefined : 'black', status:'omitted', name:source.original?.name || source.path?.split('/').pop(), reason:alternative ? 'Optional insert unavailable; synchronized camera retained for the same interval.' : 'Optional insert unavailable; black interval preserves duration and master audio.'});
      return alternative || {placeholder:'black', master_start_sec:s.master_start_sec, duration_sec:s.duration_sec, clip_start_sec:0, playback_speed:1};
    });
    const used = new Set(segments.map(s => s.source));
    return {recipe:{...recipe, segments, sources:recipe.sources.filter(s => used.has(s.key)), diagnostics, fallbacks:undefined}, diagnostics, blocked:diagnostics.some(d => d.status === 'required')};
  }
  function warnings(diagnostics) {
    const groups = new Map();
    for (const row of diagnostics || []) {
      const key = `${row.status}:${row.source}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    }
    return [...groups.values()].map(rows => {
      const row = rows[0];
      if (row.status === 'required') return `${row.name || 'Camera'}: ${rows.length} shot(s) need this original. ${row.reason || 'Locate it in Footage.'}`;
      const black = rows.filter(r => r.placeholder === 'black').length;
      return `${row.name || 'Optional insert'} omitted in ${rows.length} shot(s). ${black ? `${black} interval(s) use black. ` : ''}${rows.length > black ? 'Verified synchronized cameras cover the other intervals. ' : ''}Duration and master audio are unchanged.`;
    });
  }
  return {originalFor, plan, warnings};
})();
if (typeof module !== 'undefined') module.exports = NativeExport;
