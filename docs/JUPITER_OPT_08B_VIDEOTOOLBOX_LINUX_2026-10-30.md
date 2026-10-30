# JÚPITER-OPT-08B — Selección de encoder VideoToolbox en Linux: confirmación estática (2026-10-30)

## Hallazgo confirmado en código, aún sin cuantificar
Motor fijado: `amehcgracia-byte/zucker_videos@c89e7791ff6200e29c4281b79e84307277f9527f`, `core/stages/export.py`.
- `_render_segment` (aprox. 2295–2525) crea `hardware = _video_encode_args("h264_videotoolbox", ...)` y `software = _video_encode_args("libx264", ...)`. Salvo `force_cpu=True`, prueba primero el comando con el encoder VideoToolbox y solo al producirse `FFmpegError` reintenta el comando software. No hay `sys.platform` ni probe de capacidades en la decisión del codificador **en esta función**.
- `_video_encode_args` (aprox. 5650–5690) produce opciones de bitrate/perfil según codec, **sin verificar disponibilidad**.
- La ruta 360 nativa utiliza `run_reprojected_command` y puede introducir diferencias; no extrapolar sin comprobación.
- Excepciones y fallback son relevantes: preservar `SegmentInactivityError`, borrado de salida parcial y fallback software/proxy. No modificar motor a ciegas.

## Interpretación
VideoToolbox es la familia de codecs hardware Apple. En un entorno FFmpeg Linux estándar no suele estar disponible como encoder funcional. El flujo puede fallar rápidamente (coste pequeño) o tardar más; **no se ha medido** el overhead. El manifiesto `performance` tiene el tiempo combinado FFmpeg por segmento pero no el contador de intentos ni su duración individual.
La referencia Stage E2E tuvo 6 segmentos no cacheados, pero **no se ha probado** que los seis hayan intentado realmente un codificador fallido. No afirmar ahorros de segundos/minutos.

## Propuesta de parche candidato para revisar con Chema, NO aplicada
1. Elegir codificador según **capacidad disponible y plataforma**: en Linux priorizar `libx264`; en macOS conservar VideoToolbox con fallback. La plataforma sola no prueba el soporte de cada compilación; un `ffmpeg -encoders` o prueba de capacidad validada puede ser más robusta. Cachear la detección en el proceso, no repetirla por segmento.
2. Preferir un cambio localizado en el motor con prueba de regresión parametrizada y sin afectar a calidad/bitrate/output policy.
3. Verificar que `force_cpu` y 360 conservan su contrato, que los errores reales del hardware siguen haciendo fallback y que la caché no entrega medios creados bajo recetas incompatibles.
4. Medición con infraestructura libre: comparar intento hardware fallido vs selección directa, número de subprocesses y tiempo de inicialización; **separar este overhead** del tiempo de escala/filtrado/encoder software. Ningún render largo para verificar un posible microahorro.
5. Cualquier cambio a `zucker_videos` requiere revisión explícita de Chema y PR pequeña; nuestra rama Montara conserva únicamente análisis.

## Siguiente maniobra de solo lectura
Revisar registro de comandos del export existente (si se conserva en manifest o logs) y comparar con `_render_segment`, o usar una pequeña prueba con dobles de función **sin invocar ffmpeg** para demostrar secuencia de intentos. No lanzar benchmark con VM en carga ~30.
