# JÚPITER F4 — Benchmark real 360 Lanczos vs bilineal (2026-11-01)

**Estado:** PASS experimental; no modificación del engine ni de mixer. **NO decisión de producto**.

## Entorno y muestra
- VM GCP Ubuntu 24.04.5, fuente real HEVC equirectangular `VID_20260824_204524_00_004.mp4`, de `/home/fer/lab-clips/originales`.
- Una única ventana de 5 s desde t=10 s. Salida 1920×1080 a 25 fps de origen, sin audio; yaw=35, pitch=12, h_fov=100, v_fov=62.
- FFmpeg v360 equirect→flat, variación única interp=lanczos o interp=linear; H.264 libx264 CRF23 preset veryfast 2 threads.
- Orden L, B, B, L. Preflight CPU 33.8519 %. Ejecutado en el entorno compartido; Chema mantenía un proceso de mixer, no se ha verificado ausencia de trabajo concurrente a lo largo del benchmark.
- Resultados `/home/fer/montara-f4-real-360-01/report.json`, vídeos en esa carpeta; script `experiments/media_optimization/f4_real_360_bilinear_benchmark.py`.

## Resultados observados
| Orden | Interp | Wall s | Bytes |
|---|---|---:|---:|
| 1 | lanczos | 20.593 | 707112 |
| 2 | linear | 17.712 | 680759 |
| 3 | linear | 13.417 | 680759 |
| 4 | lanczos | 16.343 | 707112 |

- Medianas: Lanczos 18.468 s, bilineal 15.5645 s; ahorro relativo calculado por el script **15.72 %**.
- SSIM (bilineal contra Lanczos, primera pareja, ya codificados): Y=0.996362, U=0.996171, V=0.996404, **All=0.996337**. No es SSIM contra verdad terreno ni prueba perceptiva.
- El archivo bilineal fue 26 353 bytes más pequeño (~3.73 %). No interpretar como mejora de calidad.
- Las segundas ejecuciones resultan más rápidas; posible efecto de caché o estado del sistema. Solo dos observaciones por método.

## Interpretación y limitaciones
1. En este fragmento y parámetros, bilineal fue consistentemente más rápida que Lanczos.
2. El ahorro mediano del 15.72 % de wall **no** equivale al ahorro end-to-end del motor de Montara: incluye decodificación, reproyección, codificación y escritura, y no cubre compositor, movimientos, subprocesos o sesión real.
3. Foco fijo yaw/pitch, sin `sendcmd` de movimiento y un solo encuadre/escena. No extrapolar a toda la cámara 360, full-res, fotogramas con giros, ni al output completo.
4. Hay trabajo concurrente potencial y solo dos repeticiones; falta muestreo ampliado y revisión visual de detalles finos.
5. El benchmark previo sintético tuvo ahorros ~29–51 %; la divergencia aquí exige perfilado y no atribuirla automáticamente a HEVC, porque también varían otras condiciones.

## Siguientes puertas de verificación
- A/B con 3–5 pares en distintos offsets y orden alternado, sin carga concurrente; inspección lado a lado en fotogramas de detalle y movimiento, métricas VMAF/SSIM y tiempo por etapa si procede.
- Benchmark con el mismo movimiento/crop y ruta de exportación auténtica que utiliza el motor; **no tocar engine/** hasta validar.
- Si la calidad se acepta y hay mejora persistente, evaluar bilineal como `preview/draft` o preset opt-in. Mantener Lanczos por defecto mientras falten pruebas.

**Reproducibilidad:** commit `f2806fb` aporta script. Informe derivado de salida literal entregada por operador. No se inspeccionó aún visualmente el MP4.
