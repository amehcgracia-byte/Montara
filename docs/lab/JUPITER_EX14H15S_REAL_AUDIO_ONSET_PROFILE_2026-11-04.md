# JÚPITER EX-14H-15S — perfil de análisis onset de originales iPhone y 360

Fecha: 2026-11-04. Motor aislado `0f9ec03`. Prueba manual no productiva: `ffmpeg` decodifica audio íntegro directamente a pipe PCM float mono 22050 Hz, `preprocess_sync_audio`, `librosa.onset.onset_strength` hop 512 y `normalize_envelope`. Sin archivos de salida ni cambios de código. No representa `SyncStage` completo, y el orden iPhone-360 introduce sesgo potencial de calentamiento.

| Etapa | iPhone IMG_0044.MOV (986.825s) | 360 VID_20260824_204524_00_004.mp4 (911.64s) |
|---|---:|---:|
| FFmpeg y transferencia a RAM | 4.007s | 6.191s |
| Preprocesamiento acústico | 0.557s | 0.582s |
| Librosa onset y normalización | 4.374s | 1.011s |
| **Total** | **8.938s** | **7.784s** |
| Frames | 42500 | 39261 |

La fase Librosa del primer archivo puede incluir coste de inicialización/caché JIT de bibliotecas; no inferir que iPhone requiera cuatro veces más cómputo acústico. La prueba procesa ambos archivos una única vez en orden fijo, y el método de FFmpeg a pipe difiere de WAV persistido de `SyncStage`.

**Lectura:** extracción+onset íntegros del iPhone no parecen explicar por sí mismos demoras de minutos en otros escenarios, pero falta perfil de `recover_offset()`, `normalized_overlap_correlation()` (lazo Python por desplazamiento), tres verificaciones, fallback spectral/HPSS si confianza baja, y normalización/proxies del ingest.

Referencia independiente de audio EX14H15I: `t_iphone ≈ t_360 - 19.0369s` (tres ventanas en ±32ms), aún no contrastada con SyncStage nativo. Cuidado con convención nativa `master_time=clip_time+offset`.

**Próximo**: benchmark del algoritmo de correlación nativo usando arrays de envolvente reales en memoria, con master iPhone y clip 360 o inverso, sin persistencia. Medir `recover_offset`, confianza, `verify_sync_stability` de tres tramos; no deducir fallos si los envelopes no son robustos por diferencias de micrófonos. Mantener >12GiB disco libre, no tocar proyecto de Chema.
