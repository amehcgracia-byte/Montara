# Cruce de la PR #6 con auditoría de arquitectura Montara

Fecha: 2026-10-28. Documento de trabajo en `fernando/continuacion-montara` exclusivamente. Fuente PR #6 commit `15aa4d612f9bb94f43a0fea2cfb6c8ad94c4453d`, `docs/BENCHMARKS_HISTORICOS.md`. La PR está abierta y aún no fusionada; **no se ejecutaron benchmarks nuevos** para este cruce.

## Evidencia que cambia las prioridades
- Render A/B ronda 3 en Mac Intel 4C/8T, 32GiB: misma fuente/montaje 233 segmentos, 675.2s output, 1080p/30fps H264 18Mb/s; frío anterior 1942.755s, nuevo 1512.506s (-22.15%), masters idénticos. RSS agregado muestreado ~4.923 GiB antiguo y 5.829 GiB nuevo. Una pareja por condición; origen implementado Metal en Mac, no evidencia en Windows/Oracle ARM/GPU remota.
- Cache caliente nueva 313.773s; 233/233 segmentos reutilizados. No confundir con primer render, y el efecto de mux añade variabilidad. Objetivo cold render <420 s no conseguido.
- En `If u want to stay`, un proxy esférico completo gastó ~866 s que 65 tomas no necesitaron. **Potencial alto**: estudiar demanda real, política de precomputación e invalidación, no ajustar únicamente preset.
- Auditado 7 octubre: proceso 191.708s secuencial vs 142.203s solapado en tres fuentes de 20s, interferencia con otra aplicación y sin inverso: no declarar 25.8% ganancia estable.
- Mixer stems sintéticos 60s x 4: 0.685s serial, 0.406s paralelo y 0.023s desde caché; no reflejan masterización, sesiones reales ni discos USB.
- 4h synthetic detector 8.42s cold/3.77s warm (two mono WAV 8kHz, 460.8MB); not full render nor real session or 30GB proof.
- Montara local prototype 4s 1080p -> 960x540 proxy shrank 97.7%, but no wall time/RAM. Independent Windows Jupiter 835.384s source 41.48MiB -> ultrafast proxy 73.72MiB in 63.509s: different inputs/presets/quality and **not directly comparable**.
- 100.2s Stage output is duration, no render wall time known. Historical project ingest and export times exist but hardware/input/duration details N/D, not valid A/B.
- Negative results: one hung render, interrupted round, rejected image-quality alternative VMAF 71.61, YouTube remote LOGIN_REQUIRED, sandbox disk shortage. These are performance and architecture acceptance constraints rather than hidden failures.

## Rank of research hypotheses
1. **P1 — Waste-elimination and demand-driven preprocessing.** Trace spherical full-proxy generation vs actual segment needs. Measurable: full wall time, bytes written, preview readiness, clip reuse, input formats, final quality. A protective test ensures no missing projection/frames. Likely higher priority than preset-only tuning because an existing incident cost 866s.
2. **P1 — Memory-per-worker budget vs free infrastructure.** Historical cold render used 5.829GiB aggregated RSS on a Mac; memory share/double-counting and macOS Metal differences mean cannot assert Oracle 12GiB sufficient for 2 concurrent workers. Benchmark peak process-tree RSS and swap on target Linux arm64, with ffmpeg support, original formats and headroom, start with concurrency 1.
3. **P2 — Separate warm/cold and media/output quality.** Reuse existing `zucker_videos/tools/benchmarks/render_ab.py`, `segment_costs.py`, source-specific fidelity/sync checks. Cold means segment cache empty, not OS cache empty. Repeat paired A/B and alternating order.
4. **P2 — Proxy compression policy only when real cache occupancy merits it.** Compare `show_playback.py` ultrafast CRF24 vs veryfast CRF24 in same source/segments, with time-to-first-preview, bits-per-minute, CPU/RAM, seek/audio quality. Do not assume low-byte output if original is extremely compressed.
5. **P3 — Hybrid deploy/GPU feasibility.** Only after the above, estimate total end-to-end time incl upload, queue, processing, return and storage, with 10min/1h/5h and real input bitrate; no remote GPU timings currently.

## Evidence boundaries
The source explicitly marks N/D for missing commit/hardware/RAM details, and separates validations from timed measurements. Its Mac Metal values do not prove GPU acceleration on ARM/Oracle. 30GB real uploads, cloud-user concurrency and price remain unmeasured. PR #6 is documentary only; do not cherry-pick or merge to main without author review.

## Recommended next deliverable
Static code audit of proxy scheduling/consumption under `core/stages/` and `core/review_previews.py` to identify the **precise condition that created unconsumed 866s sphere proxy**, then a tiny focused instrumented benchmark using existing project's data. Only build code if a failing reproducible case is found. User-provided sources and original recordings never uploaded into Git.
