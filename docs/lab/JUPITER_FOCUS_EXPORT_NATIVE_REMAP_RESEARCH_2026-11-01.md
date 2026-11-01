# JÚPITER — FOCUS EXPORT: investigación native_remap (2026-11-01)

## Fuente de verdad
Código `amehcgracia-byte/zucker_videos`, rama `claude/show-after-44`, `core/spherical_motion.py` y `core/stages/export.py`. Consultadas las secciones de `reproject_maps` y `_run_reprojected_command` (2026-11-01). Fuentes externas:
- OpenCV official remap/convertMaps docs: https://docs.opencv.org/4.13.0/da/d54/group__imgproc__transform.html
- OpenCV official geometric transformations: https://docs.opencv.org/5.0/main_modules/imgproc_transform.html
- OpenCV 4→5 migration notes: https://github.com/opencv/opencv/wiki/OpenCV-4-to-5-migration

## Observado en el motor
1. Render 360 dinámico: FFmpeg decodifica originales en `bgr24` → Python lee fotogramas → se calcula pose y `reproject_maps` → `cv2.remap(..., interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_WRAP)` → FFmpeg codifica. Existe rama Metal en macOS con `try_remap`, por lo que no extrapolar CPU Linux a GPU Mac.
2. Los mapas de coordenadas se calculan en rejilla de aproximadamente 1/3 por eje (cuando `exact=False`) y luego se escalan con `cv2.INTER_CUBIC`, antes de remapear. `_projection_grid` usa LRU por tamaño. Se reutilizan mapas **solo** mientras `pose == previous_pose`; movimientos continuos generan poses/mapas distintos por frame.
3. Ya se reutilizan búferes de imagen de entrada y salida; no investigar como novedad la eliminación de copias de estos búferes.
4. Exportación usa `SPHERICAL_EXPORT_MOTION_MODE='native_remap'` en `core/stages/export.py`; F4 anterior comparó filtro FFmpeg `v360`, no este pipeline.

## Hipótesis sometibles a prueba
A. `INTER_LINEAR` vs `INTER_CUBIC` de OpenCV: probable ahorro en remapeo CPU, con posible degradación perceptual (bordes, texto, rostros); medir tiempo y PSNR/SSIM sobre la **misma entrada real y mapas iguales**, y no extrapolarlo a export sin atribución de etapas.
B. `cv2.convertMaps` crea mapas fixed-point compactos; OpenCV afirma posible mejora de velocidad de remap (hasta ~2x en determinadas condiciones), pero convertir **cada frame** puede anular la ganancia; medir `convertMaps + remap` frente a float maps + remap, y medir caso pose fija por separado.
C. Desglose decode/map/remap/encode: parece crucial para saber techo de ahorro; el `performance.segments` existente mide render global y FFmpeg, no distingue esas cuatro fases.

## Restricciones
- No alterar `engine/` o `main`; no renders completos ni benchmarks de 2h; primera medición máxima 1–2 segundos de vídeo real si Chema autoriza camino de prueba.
- No prometer cifras de ahorro para export entero desde microbench.
- La variación de resultados de `cv2.remap` entre OpenCV 4 y 5 puede cambiar reproducibilidad; registrar versión instalada antes de comparar.
- Siguiente decisión: esperar telemetría de jam real solicitada a Chema por issue #34, mientras se diseña un único A/B corto de native_remap si evidencia confirma su peso.
