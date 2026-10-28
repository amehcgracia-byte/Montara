# JÚPITER-26: comprobación de cadencia, 7 llamadas FFprobe versus una (2026-10-28)

## Ruta auditada
Engine PIN `amehcgracia-byte/zucker_videos@60a7b7e9`, `core/stages/export.py`, `_verify_video_cadence` ~4781: 7 ventanas de 2 segundos, cada una mediante `_frame_pts_times` y proceso `ffprobe`. La función se usa en la validación de ensamblado directo y salida final. **No confundir ahorro de esta función con ahorro de exportación completa.**

## Hipótesis
Usar `ffprobe -read_intervals '0%+2,2.8%+2,...'` en lugar de 7 invocaciones por separado podría reducir arranque de procesos y devolver exactamente las mismas marcas temporales.

## Prueba ejecutada
Linux, fixture sintético H.264 640×360/30 fps/30 s, ~6.03 MB. Ventanas iniciadas en [0,2.8,7,14,21,25.2,28] con duración 2 s. FFprobe, mismas opciones de stream, entradas y campos.

Primera serie observada 3 repeticiones: siete llamadas mediana **0.541 s** y una agrupada mediana **0.185 s**. 420 líneas en ambos y comparación íntegra exacta. Segunda serie reproducida con script enlazado: siete llamadas **[0.5623,0.6745,0.5750]**, mediana **0.575 s**; llamada agrupada **[0.1785,0.1872,0.1670]**, mediana **0.1785 s**. En las tres repeticiones **todos los 420 timestamps coincidieron exactamente en orden**.

## Límites y riesgos
Esta es una **prueba de la operación aislada**, no E2E. Fuente CFR sencilla; NO cubre VFR, offsets de origen, B-frames con PTS inusuales, tiempos negativos, clips 360 largos, fallo parcial de una ventana, casos de lista duplicada/solapada, ni combinación de varios segmentos. Incluso si el lote resulta equivalente, `_verify_video_cadence` filtra diferencias entre muestras; debe conservar la misma separación y lógica de detección, no simplemente comparar toda la salida concatenada sin adaptar los límites. No se ha modificado el motor.

## Decisión
**Candidato de optimización identificado y microbenchmarks favorables. NO integrar en Zucker sin regresiones de PTS/VFR y prueba de comparación fase-total con el proyecto real.** En la rama experimental queda un script autónomo reproducible; el autor decide si merece un PR. Proteger los checks existentes.
