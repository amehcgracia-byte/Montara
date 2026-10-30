# JÚPITER-OPT-08C — Diagnóstico confirmado de encoder Linux (2026-10-30)

## Evidencia directa del operador
VM Linux, FFmpeg 6.1.1-3ubuntu5. `ffmpeg -encoders` devuelve `libx264` y opciones de NVENC/QSV/VAAPI, pero **no** `h264_videotoolbox`. Listar NVENC/QSV/VAAPI no prueba disponibilidad de sus dispositivos.

Mediante `inspect.unwrap(export._render_segment)`, el operador confirmó que la función real está en `engine/core/stages/export.py`, línea 2294; `render_watchdog.py` era un envoltorio con `functools.wraps`.

Líneas relativas del código real:
- 173: `hardware = _video_encode_args("h264_videotoolbox", video_bitrate)`
- 174: `software = _video_encode_args("libx264", video_bitrate)`
- 175–179: con `force_cpu`, render software directo.
- 182: sin `force_cpu`, intenta el hardware.
- 195: ante fallo, intenta software.

Aunque `sys.platform` aparece en esta función, se usa para seleccionar backend de reproyección 360 (`metal` en macOS, `cpu` en otros), **no para omitir VideoToolbox en Linux**.

## Diagnóstico y límite
Se demuestra estáticamente la ruta de intento inicial con `h264_videotoolbox` para segmentos ordinarios sin `force_cpu`. Dado que ese encoder no está listado en la VM Linux, el intento no puede prosperar allí. **No se ha contabilizado en el E2E cuántos subprocesses fallaron, ni medido cuánto cuesta cada intento.** No inferir ahorro de minutos ni declarar defecto de render final; actualmente existe fallback.

## Propuesta mínima para revisión de Chema (NO aplicada)
- Capacidad/entorno: priorizar `libx264` cuando VideoToolbox esté ausente; conservar VideoToolbox y fallback en macOS.
- Preservar las opciones actuales de codificación, manejo de fallos/timeout, verificación de duración/movimiento y hashes de caché.
- Prueba unitaria con mocks: Linux sin VideoToolbox llama software **una vez**; macOS soportado intenta hardware; fallo hardware cae a software; `force_cpu` siempre software.
- Medir overhead separado de FFmpeg encoder-failure antes de estimar rendimiento; no necesita render Stage.
- Coordinación: no editar engine/mixer/main ni submódulos anclados sin aprobación del mantenedor.

## Próximo paso
Preparar una prueba de coste mínimo en el laboratorio cuando no haya carga importante, o redactar PR sugerida en ZuckerVideos con revisión de Chema. El descubrimiento es principalmente un **fast-path de selección**, todavía sin ROI cuantificado.
