# JÚPITER — EX-14H-12B/C: perfil de CPU y fidelidad preencoder real Stage 360

**Fecha:** 2026-11-03. **Motor de laboratorio:** checkout `/home/fer/zucker-videos-ex14h09` commit `0f9ec03` con pin originario `affe97a4`, EX-07/13 opt-in por proyecto, instrumentación temporal; producción sin cambios. **Alcance:** ExportStage.run, Reel horizontal 1080p30, original 360 HEVC 3840x1920, 2 segundos, 60 cuadros con movimiento, master audio de fixture. No equivale a una sesión multicámara integral.

## EX-14H-12B — CPU pipeline

Ejecución A (flags false/false): Stage total 6.412 s, segmento 5.016 s, `reproject_maps` 60 llamadas/2.1926 s (36.543 ms/cuadro), `cv2.remap` 60 llamadas/1.0308 s (17.180 ms/cuadro), residual segmento 1.7926 s; CPU usuario + hijos 30.718 s, sistema + hijos 4.601 s; RSS pico Python 193280 KiB, hijo máximo 603960 KiB.

Ejecución B (flags true/true): Stage total 5.771 s, segmento 4.330 s, `reproject_maps` 60 llamadas/1.3934 s (23.224 ms/cuadro), `cv2.remap` 60 llamadas/1.1438 s (19.063 ms/cuadro), residual segmento 1.7928 s; CPU usuario + hijos 28.508 s, sistema + hijos 3.835 s; RSS pico Python 197184 KiB, hijo máximo 625472 KiB.

Interpretación: reducción observada **36.45%** de tiempo en creación de mapas y **9.997%** de Stage completo en este par individual; `cv2.remap` subió 0.1130 s, no atribuible causalmente a flags con una muestra por configuración; residual de segmento ~1.793 s no es exclusivamente encode ni decode porque incluye esperas de tubería y otros costes. CPU acumulado de múltiples procesos/hilos no se puede dividir por wall para inferir saturación exacta sin detalle de concurrencia. El ABBA sin instrumentación previo EX14H11F midió reducción 11.37% wall, con dos ejecuciones por brazo.

## EX-14H-12C — Fidelidad antes de codificar H264

ABBA 4 exportaciones reales aisladas A1-B1-B2-A2. Instrumentación de `cv2.remap`: SHA256 por frame del BGR original decodificado recibido y del BGR resultado de remap inmediatamente antes de enviarlo al pipeline de codificación. Los cuatro recorridos tenían **60/60 cuadros de entrada idénticos** y **60/60 cuadros de salida idénticos**, A/A, B/B y A/B; hashes concatenados de entrada y salida idénticos en los cuatro recorridos. Audio PCM decodificado SHA256 idéntico en las cuatro exportaciones. Los hashes RGB de los MP4 finales decodificados sí diferían, como en EX14H11G. Esto sitúa las diferencias posteriores a `cv2.remap`, pero **no demuestra aún que el codificador y no un filtro posterior o el mux sea el responsable**.

Hashes de sucesión de SHA256 por cuadro, todos los recorridos:
- input BGR: `4df5f96708d59725ac63d5a81d5c245f6cbc8a14d496ce57e6ad3bfed7e62aa2`
- preencoder BGR: `6a4d256bc1bd93acce47bf49176ea78712d17366012b5cf0b8fbdd91b9b3d6c1`
- PCM final: `e6215d07a7acf3fb6292e4a0c32c05d93769d9bf61bff60ef274b9d101ab16e3`

Tiempos EX14H12C contaminados deliberadamente por hashing de ~373 MB por flujo: NO medir ganancia con esos tiempos. Todos los medios/cachés temporales limpiados por harness. No se alteró el motor productivo.

## Decisión y gates

**PASS de fidelidad bit-exact preencoder para este clip**: EX07/13 acelera generación de mapas sin modificar BGR reproyectado en ninguna de las cuatro ejecuciones. **No PASS de integración universal**: faltan variabilidad de escena/presets, Windows/macOS, largo, concurrencia, verificación de salida codificada dentro de tolerancia, y acuerdo Chema antes de mover pin o activar flags.

**Siguiente experimento recomendado EX14H12D:** aislar la etapa H264 mediante un único stream de fotogramas preencoder capturados una vez (archivo temporal BGR sin pérdida), codificar exactamente el mismo stream en repeticiones con `libx264` fixed flags/preset y distintos niveles de threads, distinguir calidad/no determinismo del encoder/filtros, comparar tiempos de decode/encode con `FFmpeg -benchmark` sin falsear tiempos de pipe. Se puede construir, pero no está todavía ejecutado. Evitar recodificar continuamente hasta establecer ROI.

**Audio A01:** postponed; máster fixture PCM s16le, 48 kHz, mono 20s. Su SHA PCM se mantuvo idéntico en todas las variantes; la línea de optimización audio es independiente y posterior a 360.
