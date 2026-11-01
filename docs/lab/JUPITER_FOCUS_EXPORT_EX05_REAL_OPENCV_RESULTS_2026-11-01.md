# JÚPITER — FOCUS EXPORT EX-05 · OpenCV native_remap, vídeo 360 real (2026-11-01)

**Estado:** candidato prometedor de microbenchmark; no integrado y no validado en export completo.

## Condiciones
- Original HEVC 360 3840×1920, muestra de 2s desde t=840; 12 fotogramas a 6fps, 11 medidos tras excluir el primero.
- OpenCV 4.11.0, NumPy 1.26.4, salida 960×540.
- Pose dinámica (yaw aumenta 0.3°/frame); mismo mapa y fotograma para las tres opciones.
- Pipeline evaluado: cálculo de mapa + remapeo **sin** FFmpeg decode/encode, mux ni audio.

## Resultado (media 11 fotogramas)
| Operación | Tiempo |
|---|---:|
| Generar mapa float | 35.3938 ms |
| Remap bicúbico baseline | 29.1927 ms |
| Remap bilineal float | 13.4485 ms |
| Convertir mapa a fixed point | 1.7623 ms |
| Remap bilineal fixed | 8.7867 ms |

- Baseline mapa+cúbico: **64.587 ms/frame**.
- Mapa+lineal: **48.842 ms/frame, −24.38%** en solo esta fracción.
- Mapa+convertMaps+lineal fixed: **45.943 ms/frame, −28.87%** en solo esta fracción.
- Lineal frente a cúbico: MAE 0.4101 sobre [0,255], PSNR 47.8758 dB (similitud, no garantía perceptual). Remap lineal float vs fixed: MAE 0.0 en estas muestras.

## Interpretación y cautelas
1. Candidato actual: `convertMaps + INTER_LINEAR` gana en esta muestra, pero ambos difieren del bicúbico original. Su mejora diferencial respecto a bilineal float es ~5.9% del subpipeline (no del export total).
2. **Generar mapa** cuesta 35.39 ms/frame, más que el remap bicúbico. Nueva oportunidad a considerar si las poses cambian cada frame; el código ya usa rejilla 1/3 y caché solo para poses idénticas. No prometer cambio sin revisar fidelidad y sin duplicar optimizaciones existentes.
3. Medición corta, tiempos con fuerte variabilidad y 960×540; no sirve de rendimiento 1080p ni aceleración E2E. El motor puede usar Metal en Mac. Conversión `convertMaps` cada frame incluida en la medición.
4. **No proponer sustitución por defecto todavía**. Solicitar telemetría de jam de Chema (#34) para saber peso de native_remap. Solo si justificado: una prueba controlada a 1080p, de 2–5s, con visual A/B y reloj de decodificación/codificación.

## Código
`experiments/media_optimization/focus_export_native_remap_ab_ex05.py`, commit `71aae13`. Ningún cambio en `engine/`.
