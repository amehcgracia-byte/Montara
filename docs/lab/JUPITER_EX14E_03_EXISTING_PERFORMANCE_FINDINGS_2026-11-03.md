# EX-14E-03 — Telemetría existente y revisión de caché de cabeceras

Fecha: 2026-11-03. **Observado en VM FER por ejecución de scripts de solo lectura**; no se lanzó ningún render ni se cambió el motor.

## Recursos durante la lectura
`focus_ac_vm_cpu_guard.py --interval 2`: 8 vCPU, CPU muestreada 0%, load 1.04/1.66/0.95, ningún ffmpeg/ffprobe en ese instante; no implica exclusividad futura de la VM compartida.

## Manifiestos existentes, valores observados
| Proyecto | Duración segment(s) | Export total s | Wall segmentos s | Workers | Intro s | Outro s | Cadence s | Mux s | Assembly |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| montara-focus-iphone-original-03 | 4.0 | 15.485 | 11.134 | 1 | 0.006 | 0.005 | 3.606 | 0.467 | direct_concat_audio |
| montara-focus-real-mini-01 | 4.0 | 9.628 | 6.593 | 1 | 0.039 | 0.028 | 2.391 | 0.363 | direct_concat_audio |
| montara-focus-ac-true-edit-01 | 19.0 aprox, 6 planos | 43.365 | 18.079 | 4 | **12.777** | **4.602** | 2.580 | 0.597 | direct_concat_audio |

Todos los planos reportan `cached=false`, `rendered_from=original`, `source_proxy_count=0`. Dos manifiestos tienen 1 plano; tercero 6 planos, duraciones 3.566667/3.6/6.633333/2.533333/1.533334/2.133333 s. Las cámaras aparecen por ID opaco y `projection=null`; **no inferir clasificación 360**. El `wall_sec` de 6 planos es 18.079 s; sumar `ffmpeg_sec` de todos los workers no da wall por solape. Diferencias entre proyectos NO son A/B controlado ni prueba de escala.

La última edición consume 17.379 s en intro+outro, el 40.07% de export total; es un candidato a caché fría sin demostrar. Verificadas rutas de código de ZuckerVideos `claude/recover-montara-engine`:
- `_render_logo_clip` codifica por FFmpeg a través de `_logo_clip_cache_path` y recupera con `_reuse_cached_logo` (índice incluye receta, tipo intro/outro, duración, bitrate, dimensiones, fps, codec, identificador y estadística del recurso). Los valores casi nulos en otras ejecuciones son **compatibles** con hit de caché; no lo demuestran.
- `_try_direct_concat_master_audio`: concat+mux en una pasada, luego `_verify_video_cadence` y `_verify_segment_frame_duration`; si pasa, `phases["cadence_sec"]` mide **la verificación**, no una reparación de cadencia. En las tres muestras `assembly="direct_concat_audio"`: éxito fast path, `concat_sec=0`.
- No cambiar `libx264` preset ni saltarse verificación de cadencia sin A/B y validación de calidad/duración.

## Base científica / técnica externa
1. Documentación oficial FFmpeg concat demuxer: segmentos deben compartir streams, codec y base temporal; duración errónea puede desordenar timestamps. https://www.ffmpeg.org/ffmpeg-all.html
2. FFmpeg oficial: streamcopy sin decodificar/recodificar es rápido pero requiere compatibilidad y no permite filtros. https://www.ffmpeg.org/ffmpeg.html
3. Revisión académica 2024 de caché/transcodificación para vídeo (ICT Express, DOI 10.1016/j.icte.2024.05.012), como contexto de reutilización; NO es validación directa del logo encoder de Montara: https://www.sciencedirect.com/science/article/pii/S2405959524000626

## Hipótesis y prueba de solo lectura siguiente
**H-logo:** intro/outro de 17.379 s del ensayo multicámara fueron misses y hoy existe caché apropiada. Comprobar mediante `export.log` líneas `Reusing cached logo clip` y estadísticas de `logo_clips`, sin publicar rutas, hashes ni medios. Si no se puede establecer hit/miss inequívoco, añadir en una rama futura contadores observables, no suprimir garantías. El cache global podría compartirse con otros usuarios: NO borrarlo ni modificarlo.

**H-remap:** estos tres ensayos no soportan inferencias sobre 360 dinámico. Se requiere un manifiesto nuevo clasificado con segundos de 360 y timings por segmento.

No reproducir renders pesados sin coordinación VM. No cambiar `main`, `engine/`, `mixer/`.
## EX-14E-05 — Reconstrucción de eventos y cronología (03-11-2026)
- El fichero `export.log` contiene secuencias literales `\\n`; se reconstruyeron 3/3/8 eventos de los tres proyectos. Los eventos `PLAN`, `SEGMENT` y `PHASE` confirman 0 aciertos de **caché de segmento**, pero no informan del estado de **caché de logos** (logging separado en `_reuse_cached_logo`).
- `montara-focus-ac-true-edit-01`: 6 segmentos completados, 4 workers, 0 cached, wall 18.079 s; completan fuera del orden numérico. Cronología 17:39:28 a 17:39:46.
- Dos directorios `logo_clips` listados sin rutas privadas: 3 MP4 (3531.5 y 2959.1 KiB modificados 2026-10-30 17:39:28 y 17:39:50; uno 16.7 KiB modificado 2026-11-02 23:24:53), y 2 MP4 (373.0 y 374.8 KiB modificados 2026-10-30 13:29:37 y 13:31:53). El conjunto es **compatible** con generación y posterior reutilización de bookends, pero no se ha determinado identidad de caché ni hit/miss de cada render.
- `intro_sec=12.777` y `outro_sec=4.602` del ensayo multicámara frente a milisegundos en otros dos casos: **hipótesis de caché fría**, no conclusión; los registros del export no bastan.
- Información operativa de Fernando: Chema podría estar ejecutando pruebas de Companion y render. **No lanzar tareas que consuman CPU ni A/B concurrentes** hasta coordinación y preflight nuevo. Companion mezcla localmente en ciertos flujos, pero Stage vídeo puede seguir usando servidor.
- Siguiente paso propuesto: comprobar contadores de hits/misses de logo por logger específico o inspección dirigida, solo lectura; si continúa la ambigüedad, priorizar instrumentación explícita sobre microbenchmark de logo. Evitar `rglob` global caro en VM compartida.
