# JÚPITER — FOCUS EXPORT EX-06, cierre de la línea OpenCV 360 (2026-11-01)

**Estado:** candidato de optimización respaldado por microbenchmark real a 1080p; investigación JÚPITER cerrada. **No integrado, no A/B E2E, sin revisión visual humana de JPEG aún**.

## Resultados reproducidos desde salida SSH de Fer
Fuente 360 HEVC real 3840×1920, t≈840 s, seis frames a 6 fps (cinco para medias warm), salida 1920×1080, OpenCV 4.11.0, NumPy 1.26.4. Variación de yaw 0.3°/frame. Script `experiments/media_optimization/focus_export_native_remap_ex06_1080.py` commit `4b43d81`.

| Fase (media 5 frames) | Milisegundos |
|---|---:|
| Generar mapa | 71.086 |
| `cv2.remap` bicúbico float | 24.228 |
| `cv2.remap` bilineal float | 7.460 |
| `cv2.convertMaps` | 6.442 |
| `cv2.remap` bilineal fixed | 6.538 |

- Mapa + bicúbico actual: 95.31 ms/frame.
- Mapa + bilineal float: 78.55 ms/frame (**−17.59 %** de este subpipeline).
- Mapa + conversión + bilineal fixed: 84.07 ms/frame (**−11.80 %**).
- Calidad relativa bicúbico vs bilineal: PSNR 47.597 dB, MAE 0.430/255; se trata de comparación contra el baseline, no verdad terreno ni garantía perceptual.
- Float bilineal vs fixed bilineal: mismo píxel en los seis frames (igualdad exacta).
- En EX-05 a 960×540: bilineal float −24.38 % y fixed −28.87 %; la jerarquía cambia con la resolución, por lo que **no generalizar**.

## Interpretación científica
- `INTER_LINEAR` CPU es **candidato prioritario** a prueba opt-in; `convertMaps` en poses cambiantes a 1080p **no mejora** al bilineal float en esta muestra.
- El mapa supone 71.086 ms del baseline 95.314 ms (~74.6 %), y es el mayor coste observado dentro de este subpipeline; no implica que lo sea del export completo.
- El test excluye decodificación FFmpeg, transferencia por pipes, codificación, mux, caché, control de concurrencia, verificación y Metal en Mac. No se estima ahorro total del producto.
- Solo seis frames; hay variación considerable entre mediciones; ordenar por microbenchmark corto es provisional. La comparación visual existe en JPEG `/home/fer/montara-focus-export-ex06-review.jpg` pero **no ha sido inspeccionada por el asistente** y no debe describirse como validación perceptual.
- `cv2.remap(..., INTER_CUBIC)` es ruta actual de `core/spherical_motion.py`, mientras que las pruebas históricas F4 trataron filtro FFmpeg `v360`: no confundir implementaciones.

## Recomendación para Chema
1. **No sustituir globalmente** bicúbico ni modificar engine desde el laboratorio Fernando.
2. Si la telemetría de jam real confirma suficiente proporción de coste `native_remap`, evaluar `INTER_LINEAR` como **opción experimental reversible** y comprobar 1080p real visual A/B a resolución original sobre rostros, texto, cables y bordes, incluyendo fallback.
3. Una sola comparación E2E mismo segmento y máquina con parámetros y calentamiento controlados; si impacto global insuficiente, cerrar sin integrar.
4. Más adelante, investigar cálculo de mapas (dominante en microbenchmark) solo si vale la pena por cuota E2E; sin cadenas de microexperimentos.

## Decisión
**Cerrar FOCUS EXPORT / native_remap por JÚPITER; dejar integración condicionada a telemetría real de Chema y validación de calidad.** La solicitud de telemetría está en issue #34. Ningún cambio de producto realizado.
