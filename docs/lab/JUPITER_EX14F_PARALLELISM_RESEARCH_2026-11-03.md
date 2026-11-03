# JÚPITER EX-14F — Paralelismo anidado y diseño experimental

Fecha 2026-11-03. Lectura de ZuckerVideos `claude/recover-montara-engine/core/stages/export.py` y revisión de documentación técnica externa. **Hipótesis sin benchmark nuevo**, VM compartida con Chema; no cambiar main ni engine ni mixer.

## Evidencia directa en código
- `_segment_worker_count` (líneas aprox 676-695): valor `settings.export.segment_workers` > 2 es explícito hasta 8; valores <= 2 causan cálculo automático basado en `os.cpu_count() // 2`, limitado por memoria y 8. En GCP 8 vCPU / 31 GiB, automático sugiere 4 para >=4 segmentos. **Limitación de interfaz**: no fuerza 1 o 2 mediante ese ajuste.
- `_render_plan`: ordena planos por duración descendente, `ThreadPoolExecutor(max_workers=segment_workers)`, `as_completed`, workers concurrentes y verificación solapada opcional.
- `_render_segment`: si `native_motion` con equirect y movimiento, llama `run_reprojected_command` y entrega cuadros BGR por pipe a FFmpeg; no es correcto atribuir todos los costes a FFmpeg ni tratar 360 como un proceso de codificación ordinario. En el ramal no nativo, FFmpeg procesa vídeos por separado; en Linux prueba `h264_videotoolbox` con fallback a `libx264`, por lo que interesa distinguir fallo inicial y fallback al medir wall real. Para overlays Reel, el código fija `-filter_threads 1 -filter_complex_threads 1` como protección específica; no extrapolar a todos los planos.
- `_video_encode_args`: libx264 `veryfast`, no pasa un `-threads` fijo; FFmpeg puede aplicar threading automático según codec/filtros. El `cv2` del remap dinámico puede paralelizar internamente.
- En 3 manifiestos previos, una exportación de 6 planos registró `segment_workers=4`, wall segmentos 18.079s, `cached=false`, `rendered_from=original`, sin clasificación 360. No existe control A/B de distintos workers, ni se midió utilización/hilos.

## Investigación externa, fuentes concretas
- **Documentación oficial FFmpeg**: `-filter_threads` y `-filter_complex_threads` tienen pools propios; valor predeterminado puede ser CPUs disponibles. `-threads` (codificación/decodificación) permite `auto`. https://ffmpeg.org/ffmpeg.html ; https://ffmpeg.org/ffmpeg-all.html
- **OpenCV 4.10, setNumThreads**: controla paralelismo de regiones OpenCV, **no es thread-safe**; nunca cambiarlo globalmente mientras trabajadores concurrentes están ejecutando remap. https://docs.opencv.org/4.10.0/db/de0/group__core__utils.html
- **Meta SPDL 0.7 benchmark-video**: matriz de concurrencia `num_workers=1,2,4,8` y `decoder_options.threads=1,2,4` para distintos tamaños; evidencia de técnica de diseño de experimentos, resultados NO transferibles automáticamente a Montara. https://facebookresearch.github.io/spdl/main/generated/benchmark_video.html
- **Li et al., Expert Systems with Applications 298 (2026), 129700, DOI 10.1016/j.eswa.2025.129700**: optimización de asignación de recursos de transcodificación en streaming; valor conceptual, dominio distinto al editor offline. https://www.sciencedirect.com/science/article/abs/pii/S0957417425033159

## Hipótesis falsable
H1: para vídeos multicámara exportados con múltiples procesos FFmpeg/decodificación, mayor número de workers no reduce monotónicamente wall-clock debido a contención/oversubscription. H0: tiempos iguales o menores con workers superiores bajo mismas condiciones de entrada, caché y carga.

## Protocolo A/B futuro (NO ejecutado)
1. Coordinar ausencia de renders de Chema; preflight CPU, memoria, disco, procesos; registrar SHA exacto de Montara y submódulo, FFmpeg y OpenCV. Elegir fuente y plan idénticos con varios segmentos, incluir cuando sea posible 360 dinámica y otra familia flat como estrato distinto.
2. `segment_workers=2` es ignorado en la función actual (auto). Para comparar 1/2/4, añadir en **rama de laboratorio Montara propia**, bajo un interruptor nuevo explícito y por defecto desactivado, opción de respetar conteo configurado; nunca parchear main del motor ni cambiar globales CV2 concurrentemente. Si prueba en rama de motor, esperar revisión PR #51 y coordinación.
3. Ensayos cortos y reversibles: misma fuente, codecs, transiciones, bitrate, resolución, sin cache hit o con política de cache idéntica. ABBA con orden alternado por condición; usar al menos 2-3 repeticiones, prefiriendo >=3 si ruido alto.
4. Métricas por intento: wall total y fase, throughput cuadros/s, CPU% sistema e hilos/procesos por worker, memoria pico, recodificaciones/fallback, hit ratio, errores, salida visual/audio, duración/fps/frames/size y hashes cuando igualdad bit a bit es exigible. Descartar medidas con procesos ajenos concurrentes.
5. Con evidencia de H1, explorar FFmpeg codec threads y filter threads **como segunda variable**, no mezclar dos cambios en A/B inicial. Hardware Mac Metal es otra estratificación (no extrapolar resultados CPU GCP).
6. Criterio de aceptación: mejora repetible bajo condiciones comparables sin violar recursos compartidos, sin degradación de calidad/producción; revertible, tests y PR draft para Chema.

## Próxima acción segura
Un preflight de solo lectura de capacidades del entorno (FFmpeg codecs, OpenCV versión/getNumThreads, cgroup CPU quotas, settings export sin tocar archivos) y localizar un fixture corto cuyo uso esté autorizado, sin lanzar render. Avisar a Fernando **antes** de cualquier benchmark consumidor de CPU.

## Revisión de antecedentes 03-11-2026 — CORRECCIÓN DE PRIORIDAD

Fernando señaló que la investigación de hilos ya estaba hecha. Se leyeron íntegramente estos antecedentes versionados (no solo nombres):
- `docs/JUPITER_11_CONTAINER_RESOURCES_AND_TEST_GATES_2026-10-28.md`
- `docs/JUPITER_12_CGROUP_POLICY_PROTOTYPE_2026-10-28.md`
- `docs/JUPITER_14_FFMPEG_CGROUP_REAL_SAMPLE_2026-10-28.md`
- `docs/JUPITER_15_HANDOFF_FINAL_2026-10-28.md`
- `docs/SATURNO_07_FIRST_FFMPEG_STAGE_DIVERGENCE_2026-10-29.md`
- `docs/SATURNO_08_ENCODER_VBV_PROTOCOL_2026-10-29.md`
- `docs/SATURNO_08_ENCODER_VBV_RESULTS_2026-10-29.md`
- `docs/JUPITER_OPT_07_CPU_DUPLICATION_AUDIT_2026-10-30.md`
- `docs/JUPITER_OPT_07C_EXPORT_MANIFEST_DIAGNOSIS_2026-10-30.md`
- `docs/JUPITER_OPT_08_EXPORT_FFMPEG_COMMAND_AUDIT_2026-10-30.md`
- `docs/JUPITER_09_REPRODUCIBLE_MULTIPLATFORM_BENCHMARKS_2026-10-28.md`
- `docs/JUPITER_CPU_COMPARISON_4V_8V_2026-10-30.md`

### Resultados ya probados — no duplicar
1. JÚPITER-14 **ya ejecutó** FFmpeg 8 clips sintéticos, 720p, bajo 4 CPU/4 GiB cgroup y `-threads 1`: 1 worker 10.930s (n=1), 2 workers 6.116/6.181s (n=2), 4 workers 4.976/4.711s (n=2). **Cuatro ganaron en ese escenario** pese al techo de 4 CPU; memoria cgroup pico ~1.02 GiB (no es RSS FFmpeg). No es Stage, no es 360, no prueba configuración óptima en VM 8vCPU. Particularmente, NO recomendar reducir automáticamente a 1 o 2 trabajadores alegando sobresuscripción.
2. JÚPITER-11/12/15 **ya construyeron** `experiments/container_budget/resource_policy.py`, `cgroup_guard.py` y parche candidato de overlap con pruebas unitarias (7 pasadas para guard), sin validación integrada. Su hallazgo es riesgo cgroup cuando host>cuota, **no se observó OOM**. En VM sin límite cgroup restrictivo inferior al host no aplicar cambio preventivo al scheduler.
3. SATURNO-07/08 **ya aislaron** no repetibilidad de libx264 + VBV multi-hilo: original en replays 54/60 y 53/60 frames; `-threads:v 1` o quitar VBV dio 60/60; controlar solo `-filter_complex_threads 1` NO resolvió (53/60). El control QA no es requisito de producción ni prueba de speedup: preservarlo únicamente para verificaciones estrictas A/A y no confundirlo con ajuste de rendimiento de workers.
4. JÚPITER OPT-07/07C/08 **ya auditó** segmentos, dos workers, stream-copy, cachés y FFmpeg: flujo 720p→1080p con imposibilidad de stream-copy por tamaño. Sobre la VM previa hubo interferencia con jm, no A/B de escalado CPU. **Hallazgo nuevo prioritario a confirmar**: en Linux `_render_segment` intenta `h264_videotoolbox` de Apple y, tras error, usa `libx264`; `ffmpeg -encoders` del VM solo muestra `libx264` y no `h264_videotoolbox`. El coste es **desconocido**, puede ser solo arranque fallido rápido; inspeccionar trazas existentes antes de benchmark o cambio de motor.
5. Herramientas de benchmark A/B **ya disponibles**: `ZuckerVideos/tools/benchmarks/render_ab.py` (Mac-specific) y `segment_costs.py` (instrumentación histórica); no reconstruir framework. Cache fría vs caliente y versión/fuente/plan congelados son controles imprescindibles.

### Decisión actualizada
**Congelar EX-14F como candidato de optimización, no realizar nuevo benchmark de trabajadores ahora.** La literatura externa es contexto de posibles políticas, pero nuestra evidencia histórica sobre 1/2/4 workers ya existe. Retomar workers solo tras seleccionar una pregunta distinta y un fixture Stage real reproducible con métricas que faltaban.
Priorizar inspección sin render del fallback `h264_videotoolbox` en Linux: existe candidato preciso y contrastable en código, sin asumir ganancia; consultar logs de ejecución y `ffmpeg_commands` en manifiestos, sin publicar rutas privadas. Un A/B posterior solo con coordinación y autorización de Fernando; nunca tocar `main` ni ramas ajenas.
El preflight EX-14F-01 dio 8 CPU visibles, FFmpeg 6.1.1 con `libx264` y sin `h264_videotoolbox` en listado, OpenCV no disponible en el Python **del sistema** (no informa sobre venv de motor).
