# JÚPITER F4 — Cierre de ronda real de interpolación 360 (2026-11-01)

**Estado:** candidato de optimización validado en benchmark aislado; **NO integrado**, NO validación E2E del motor. Prioridad siguiente: FOCUS A/C vídeo desde originales reales. 

## Condiciones
Cámara HEVC 360 real `VID_20260824_204524_00_004.mp4`, corte 5 s en t=840, yaw=180°, pitch=-30°, h_fov100 v_fov62, salida 1920×1080 libx264 CRF23 preset veryfast threads2; cuatro interpolaciones en orden L-linear-cubic-spline16-spline16-cubic-linear-L. Trabajo compartido en GCP, dos repeticiones, sin protocolo de aislamiento de carga completo.

| Método | Tiempos (s) | Media (s) | SSIM All contra Lanczos | PSNR average dB contra Lanczos |
|---|---|---:|---:|---:|
| Lanczos | 16.17; 13.63 | 14.90 | referencia | referencia |
| Bilineal (`linear`) | 9.10; 9.24 | **9.17** | **0.990657** | **45.640404** |
| Bicúbica (`cubic`) | 13.72; 16.28 | 15.00 | 0.991179 | 46.139343 |
| Spline16 | 13.00; 14.60 | 13.80 | 0.991138 | 46.108322 |

Bilineal ahorró **38.46 % del tiempo de wall** en esta muestra. Frente a Lanczos las otras alternativas mejoran ligeramente SSIM y PSNR pero con ganancia de tiempo marginal o negativa. Los resultados de métricas se obtuvieron de FFmpeg `[0:v][1:v]ssim;[0:v][1:v]psnr` sobre los MP4 renderizados (la salida de SSIM se remite a PSNR mediante reutilización del flujo; metodología válida para comparación pero comprobar alineación de frames en adopción final). 

Se inspeccionó el mosaico de cuatro métodos escalado: sin artefactos geométricos evidentes y diferencias menores perceptivamente a esa escala; no equivale a prueba visual a 1080p. La primera prueba real sobre un encuadre muy oscuro (t=10, yaw35, pitch12) midió 15.72 % de ahorro y SSIM 0.996337, y motivó seleccionar escenario t=840. 

## Decisión
**STOP investigación incremental por ahora**: bilineal candidato para modo preview/export rápido opt-in, Lanczos como referencia de calidad final. No modificar `engine/` ni `main` hasta que Chema acepte prueba A/B con camino real de render, movimientos de encuadre, y regresión visual. Ahorro de interpolación no debe extrapolarse al sistema completo.

## Recomendación a Chema
Pedir estudio de incorporación selectiva como preset "rápido 360" cuando priorice rendimiento; evidencia de dos encuadres reales y sintética previa. No confundir con un cambio productivo ya desplegado.

## Próximo frente en JÚPITER
FOCUS A/C: exigir una exportación **iPhone 4K original seleccionado** desde plan editado con proxy, y auditar origen, rotación, dimensiones, duración y calidad. La prueba mini previa incluyó iPhone candidato pero exportó solo Sony; no cerró iPhone real.
