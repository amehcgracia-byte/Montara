# JÚPITER — FOCUS EXPORT EX-01: telemetría existente (2026-11-01)

## Conclusión
No añadir instrumentación antes de inspeccionar los artefactos de una exportación Stage **ya ejecutada**. ZuckerVideos registra tiempos de fase y por segmento con caché/origen; analizar esos datos sin render es el siguiente paso. No confundir Stage multicámara con modo 360 passthrough.

## Evidencia en código (rama zucker_videos:claude/show-after-44)
`core/stages/export.py`:
- `phase_times` incluye `intro_sec`, `source_prepare_sec`, `source_proxy_count`, `concat_sec`, `cadence_sec`, `mux_sec` y otras fases según rama ejecutada.
- Segmentos paralelos: `ThreadPoolExecutor(max_workers=segment_workers)`; lista priorizada por duración (larga primero); verificación se puede solapar y limita cola con `BoundedSemaphore(2)`. Por tanto **sumar `ffmpeg_sec` de segmentos no equivale a wall-time de render**.
- Cada segmento registra `cached`, `rendered_from`, `ffmpeg_sec`, `verify_sec`, `total_sec` en registro de export y `render_stats`.
- `project.data["_export_performance"]` guarda `segment_count`, `segment_workers`, `stream_copy_count`, `wall_sec`, `total_wall_sec`, `phases`, `segments`. Determinar si hay persistencia en artefacto/proyecto concreto antes de prometer recuperación.
- Camino export 360 directo: `_render_360_plan` intenta `_copy_trim_video` con copia de flujo, concat HEVC validado y fallback recodificación; distinto de Stage que puede reproyectar 360 y exportar planos.
- `SPHERICAL_EXPORT_MOTION_MODE="native_remap"` para movimientos; static v360 conservado para planos estáticos. El benchmark F4 sobre v360 no prueba automáticamente aceleración native_remap.

## Trabajo antiguo que NO repetir
`main:docs/lab/RUNS.md`: 4 vCPU/654s salida/export 4101.5s vs 8 vCPU/628s salida/export 1388.1s: cambios simultáneos, no comparables causalmente.
`main:docs/lab/INVENTORY-FER.md`: F7 ffprobe pequeña prioridad, F4 v360 y F8 proxy esférico ya investigados; no reiniciar.
`docs/lab/JUPITER_FOCUS_EXPORT_BASELINE_AUDIT_2026-11-01.md`: auditoría EX-00.

## Siguiente paso mínimo EX-02 (sin render)
Inspeccionar desde terminal bajo usuario `fer` los manifiestos/JSON disponibles en proyectos de pruebas anteriores, sin abrir `/home/jm` ni borrar nada. Detectar campo `_export_performance` y estadísticas `segments`; clasificar segmentos por metadatos existentes (360/plano, origen, cache, duración, motion) y documentar cobertura real. Si esos datos solo están en procesos históricos de Chema y no en FER, solicitar export de `_export_performance` anonimizado a su equipo, en lugar de repetir un render largo.

## Restricciones
No modificar engine, no nuevos renders, sin datos privados en repos públicos. No atribuir mejoras sin A/B mismo input, equipo y parámetros.
