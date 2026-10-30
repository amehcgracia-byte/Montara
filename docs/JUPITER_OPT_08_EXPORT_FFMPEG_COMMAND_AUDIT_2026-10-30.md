# JÚPITER-OPT-08 — Escafandra al comando FFmpeg de exportación (2026-10-30)

## Alcance
Auditoría estática del código real de `amehcgracia-byte/zucker_videos` en pin `c89e7791ff6200e29c4281b79e84307277f9527f`, `core/stages/export.py`. No modificación de engine/mixer/main, no FFmpeg ejecutado, ni pruebas adicionales en VM.

## Hallazgos verificables
1. `_render_segment` (aprox. línea 2295) usa `_segment_source_info` y selecciona el **original** salvo ruta específica para reproyección 360/proxy de seguridad. El código construye filtro de fuente con `_export_source_filter`, filtro de composición con `_segment_filtergraph` y origen mediante `_segment_video_command_base`.
2. `_segment_video_command_base` (aprox. 2972) usa `-ss clip_start -t duration -i input`, por tanto recorta al comienzo del pipeline; incluye progreso. Destino fija fps CFR, frame_count, pixel format y timescale. No retirar estas garantías por rendimiento.
3. `_base_video_filter` (aprox. 3266) para YouTube estándar escala a **1920×1080** (con pad y yuv420p). Los originales Stage E2E fueron **1280×720**, por tanto FFmpeg necesariamente reescala/recodifica estos segmentos; stream copy queda impedido (OPT-05).
4. **Hipótesis concreta para investigar:** el código intenta primero `h264_videotoolbox` en `_render_segment` y, cuando lanza `FFmpegError`, reintenta con `libx264`. VideoToolbox es el encoder de Apple, mientras nuestro banco de prueba es Linux. Si todos los segmentos pasan por fallo del encoder HW antes de realizar la codificación software, puede haber un coste de arranque evitable y un mensaje de error innecesario. **No cuantificado**: el manifiesto mostrado no contiene los comandos/retornos, y el comportamiento exacto puede variar con compilación FFmpeg. Antes de cambiar selección por plataforma, observar comandos de `ffmpeg_commands` o trazas existentes. Verificar si `_video_encode_args` ya controla ese caso; no asumir siempre doble trabajo o que fallan los 6.
5. `_render_segment_job` (aprox. 2550) usa caché por receta, verifica duración y movimiento, publica con atestación SHA256 y hard links; ya evita repetición de pruebas caras para caché válida. Retirarlas sin sustituto debilitaría seguridad.
6. `_render_segment` serializa `-filter_threads/-filter_complex_threads 1` **solo si hay overlays Reel**, debido a inestabilidad conocida; no imponer al resto ni ampliar paralelismo sin analizar seguridad.
7. 360 nativo emplea `run_reprojected_command`, ruta distinta de codificación ordinaria. No trasladar automáticamente optimizaciones de escala/encoder al 360.

## Lectura de tiempos
`performance` del E2E: total 186.427 s, ffmpeg por segmentos 36.097 / 33.826 / 64.501 / 26.828 / 11.233 / 23.349 s, con dos workers y CPU compartida. No inferir de ellos tiempo gastado específicamente en el fallback hardware ni coste de escalado/encoder.

## Próxima acción sin renders
- Inspeccionar `_video_encode_args` y, si existe, el registro de comandos del `export_manifest.json` ya creado, **sin mostrar rutas privadas ni volcar logs grandes**.
- Preparar un chequeo offline que documente si Linux ofrece encoder `h264_videotoolbox` y si es elegido por el exportador (mediante inspección y prueba de enumeración de encoders, no render), con Chema revisando cualquier cambio propuesto a ZuckerVideos.
- Si se confirma intento inútil en Linux, proponer microparche **solo tras distinguir corrección funcional vs mejora medible**. Las mayores ganancias probables siguen en FFmpeg de segmentos, pero aún sin atribución causal.

## Restricciones
Carga VM observada >30 con 8 vCPU: no renders / benchmarks ahora. Herramientas ligeras de lectura son seguras. Mantener `fernando/continuacion-montara` y coordinar integración vía Chema.
