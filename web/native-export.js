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
      if (!alternative) {
        diagnostics.push({shot:index + 1, source:s.source, status:'required', name:source?.original?.name || source?.path?.split('/').pop(), reason:source?.optional ? 'No synchronized camera covers this optional insert.' : 'This shot needs its original.'});
        return s;
      }
      diagnostics.push({shot:index + 1, source:s.source, replacement:alternative.source, status:'omitted', name:source.original?.name || source.path?.split('/').pop(), reason:'Optional insert unavailable; synchronized camera retained for the same interval.'});
      return alternative;
    });
    const used = new Set(segments.map(s => s.source));
    return {recipe:{...recipe, segments, sources:recipe.sources.filter(s => used.has(s.key)), diagnostics, fallbacks:undefined}, diagnostics, blocked:diagnostics.some(d => d.status === 'required')};
  }
  return {originalFor, plan};
})();
if (typeof module !== 'undefined') module.exports = NativeExport;
