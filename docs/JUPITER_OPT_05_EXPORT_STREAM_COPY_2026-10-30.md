# JÚPITER-OPT-05 — Diagnóstico de stream copy en Stage E2E (2026-10-30)

## Resultado
**Cerrado, sin parche de motor.** En el E2E sintético Stage (40,2 s finales, 1920×1080 YouTube, seis segmentos) no hubo reutilización de caché ni stream copy, y los seis segmentos se exportaron desde originales.

Fuentes verificadas en la VM mediante ffprobe por el operador:
- camera-a.mp4: H.264, 1280×720, yuv420p, 30/1 fps.
- camera-b.mp4: H.264, 1280×720, yuv420p, 30/1 fps.
- Segmentos interiores: #2 inicia en 3,566667 s (3,6 s), #3 en 7,166667 s (6,633333 s), #4 en 13,8 s (2,533333 s), #5 en 16,333333 s (1,533334 s).

## Causa comprobada en código
Versión de ZuckerVideos del experimento `c89e7791ff6200e29c4281b79e84307277f9527f`, `core/stages/export.py::_stream_copy_eligible`: exige, entre otros requisitos, mismo tamaño que el destino `_target_size(platform)`, FPS de salida compatible, color, H.264 CFR y ausencia de fundidos. La salida YouTube era **1920×1080**, pero los originales sintéticos son **1280×720**: este único desacuerdo de resolución basta para descartar stream copy en los segmentos centrales. El primero y el último además están excluidos por los fundidos.

No se comprobó la alineación GOP de esos cortes ni todos los restantes predicados: no es necesario para explicar el rechazo dado que la resolución ya lo determina. Tampoco se deduce de ello la eficiencia real con archivos Sony o iPhone, ni que eliminar el escalado sea correcto para calidad o producto.

## Rendimiento observado
Manifiesto export `performance`: `total_wall_sec=186.427`, `wall_sec=109.354`, `segment_workers=2`; segmentos individuales FFmpeg 36.097, 33.826, 64.501, 26.828, 11.233, 23.349 s. Intro 30.824 s, outro 26.829 s, con caché propia `Cache/logo_clips` (2 archivos, 0,73 MiB observados). Los tiempos individuales pueden solaparse; E2E compartió CPU con carga de jm. No extrapolar multiplicadores a producción.

## Decisión y siguiente acción
No ampliar permisividad de stream-copy basándose en esta fixture, ni crear cachés redundantes. La oportunidad de mayor impacto pasa por perfiles reales y evitar procesamiento innecesario a nivel de GOP/decodificación sin alterar render, sincronización ni color. El encargo HEVC 4K HDR VFR de Chema se registró en `docs/JUPITER_IPHONE_HEVC_CPU_PLAN_2026-10-30.md`; cuando existan clips reales, revisar bibliografía y documentación técnica vigente antes de pruebas pesadas. Mantener rama `fernando/continuacion-montara`; sin cambios a engine, mixer, main ni HOME de jm.
