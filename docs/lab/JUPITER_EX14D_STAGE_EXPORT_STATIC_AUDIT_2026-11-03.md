# JÚPITER EX-14D — Auditoría estática de exportación STAGE
Fecha 2026-11-03 · Estado: **investigado / sin benchmark nuevo** · Ningún cambio a motor ni producto.

## Fuentes y versión
- `amehcgracia-byte/zucker_videos`, `main:core/stages/export.py` blob `a3d24388dfe317ca4e8c2cad318972cb85b51ef4`, 5671 líneas.
- Montara `main` observado `b718470c7d6ffb3a029a02a56785a1c489bc6890` y `deploy/vm/run_history.py` blob `a0f391bac24b0470632416a219dc419b91b690f0`.
- Issue #34 última comunicación revisada: EX-06/07/13 prototipo de motor todavía local, sin permiso Write para publicar, no duplicar ni tocar esos cambios.

## Flujo probado por lectura
1. `_render_plan` prepara fuentes 360, decide número de workers con `_segment_worker_count` (auto: mitad de CPU lógica, cap 8 y adaptación RAM; configuración explícita >2 cap 8).
2. `ThreadPoolExecutor` procesa segmentos ordenando los **más largos primero**, conservando índices para composición final.
3. `_render_segment_job` resuelve receta y cache stamp, reutiliza si válido; en frío intenta stream-copy si elegible, si no invoca `_render_segment` sobre originales/proxies según la ruta.
4. Verificación de segmento fresco antes de caché, con posible solape en executor separado y semáforo acotado. Cada segmento guarda `ffmpeg_sec`, `verify_sec`, `total_sec`, `cached`, `rendered_from`. Suma de tiempos de workers NO equivale a wall por paralelismo.
5. Compone segmentos con transición si hace falta, render intro/outro; intenta `_try_direct_concat_master_audio` para evitar ruta tradicional. Si no, concat con `-c copy`, verificación de cadencia y multiplexado de audio (más overlays si Reel).
6. `_export_performance` registra `segment_count`, `segment_workers`, `wall_sec`, `total_wall_sec`, `phases`, `segments`; `ExportStage.run` lo publica en el manifiesto. `SPHERICAL_EXPORT_MOTION_MODE = native_remap`: las pruebas v360 FFmpeg no son automáticamente aplicables al flujo dinámico dominante.

## Hipótesis priorizadas (no conclusiones)
- **H1 CPU/RAM saturación por FFmpeg concurrente**: auto workers hasta ocho puede competir con hilos internos de FFmpeg; evaluar topología y porcentaje 360 por worker.
- **H2 reproyección 360 nativa**: medir total de segundos/planos native_remap versus planos flat, y tiempo por clase. EX-06/07/13 están a la espera de publicación de rama del motor y decisión Chema; no lanzar más microbenchmarks antes de conocer peso real.
- **H3 paso final costoso**: direct concat puede fallar y activar cadence/mux; medir `phases` por export y causa del fallback.
- **H4 caché**: distinguir warm vs cold con `cached` y `rendered_from`, invalidación por receta, sin compararlos como velocidad intrínseca.

## Dato histórico insuficiente
Tres registros pasados `runs.jsonl` tenían `shots: null`; dos renders reales con hardware/mezcla diferentes dieron export 4101.5 s (4vCPU) y 1388.1 s (8vCPU). No atribuir causalidad al número de núcleos, al algoritmo de remap ni al formato sin estadística por cámara.

## Próximo paso sugerido, cero render
Revisar el agregado `performance` de un export real **ya ejecutado** si está disponible para laboratorio Fer, extrayendo solo nombres de claves, `phases`, `segment_workers`, `cached` y `rendered_from`; no publicar rutas ni clips. Si no hay artefactos propios, pedir al otro laboratorio agregado anonimizado de su jam real de 628 s (ya solicitado issue #34). No solicitar una exportación larga nueva.
Explorar a continuación si la instrumentación actual puede clasificar `spherical_shot` por segmento y medir coste por categoría: la lista `segments` incluye tiempos e índice, pero la clasificación explícita no es visible en el `render_stats` inspeccionado.

**Alcance:** lectura documental, sin ejecución en VM, sin tocar main ni submódulos; contrastar configuración del motor fijado en Montara antes de cualquier ensayo real.
