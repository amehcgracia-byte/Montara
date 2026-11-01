# JÚPITER — FOCUS A/C iPhone 4K original, primera exportación real satisfactoria (2026-11-01)

**Resultado:** `PASS_IPHONE_ORIGINAL_UNCACHED_EXPORT_NEEDS_VISUAL_REVIEW`. Prueba puntual mediante **ExportStage real del submódulo ZuckerVideos**, sin ejecutar EditStage de nuevo ni alterar originales. Motor de FER: `c89e779`; FFmpeg Ubuntu 6.1.1.

## Evidencia del ensayo
- Script `experiments/media_optimization/focus_ac_iphone_real_original_export.py`, commit de corrección de identidad `9f6029f`; proyecto temporal `/home/fer/montara-focus-iphone-original-03`.
- Proyecto y plan editados con proxies reales de iPhone y Sony en ensayo previo; cambio aislado de segmento Sony a **iPhone original `IMG_0044.MOV`** y proxy `1-iphone-proxy.mp4`; clip t=10.0 a 14.0 s.
- Resolver: `source_path=/home/fer/lab-clips/originales/IMG_0044.MOV`, `proxy_path=/home/fer/montara-focus-ac-real-01/1-iphone-proxy.mp4`.
- Manifiesto por segmento: `rendered_from=original`, `cached=false`, `ffmpeg_sec=10.46`, `total_sec=11.132`, `verify_sec=0.662`; `force_rerender_segments=true`. El log indica intento de bypass de caché y rechazo de caché no verificable para receta 29.
- Output MP4 H.264 **1920×1080, 30fps**, **15,672,816 bytes**, tiempo total del harness **23.265 s**. Los 4 segundos son duración del **segmento**; el archivo final de Stage incluye intro/outro según configuración, por lo que NO inferir 4s de duración final.
- El ensayo **no certifica export 4K**, calidad visual, orientación correcta, sincronía de un concierto real ni integración de Companion/local render en Mac. Debemos inspeccionar un fotograma dentro del segmento exportado (evitando intro) y revisar la orientación vs fuente rotada.
- El ensayo no explica los 219 s anteriores de EditStage; allí el editor analizó iPhone+Sony pero eligió Sony y usó master sintético. La demora precisa requiere perfilado del editor, pendiente en otra fase.

## Criterio de cierre
Mecánica de **exportación Stage 1080p desde original iPhone 4K** acreditada. Mantener `NEEDS_VISUAL_REVIEW` hasta ver orientación y encuadre. Tras recoger evidencia, borrar solo artefactos temporales del directorio de ensayo y conservar JSON/informe en GitHub. 
