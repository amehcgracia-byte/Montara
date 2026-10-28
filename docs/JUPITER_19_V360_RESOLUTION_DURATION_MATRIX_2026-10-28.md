# JÚPITER-19 — Matriz 4K, 6K y 8K × 2, 5 y 10 segundos (2026-10-28)

**Resultado:** 18/18 exportaciones completadas en Linux FFmpeg 7.1.5, fuera de Montara/Zucker. Una ejecución por cada celda — **NO** repetición estadística. Mantener motor 360 de José Manuel intacto.

## Método y límites
Entrada sintética H.264 `testsrc2` equirectangular a 24 fps: 4K=4096×2048, 6K=5760×2880, 8K=7680×3840. Salida idéntica en todos los casos: 1920×1080, libx264 CRF 23, preset veryfast, 2 threads, sin audio, yaw35 pitch12 FOV100×62, `format=yuv420p`, variación única del filtro `v360 interp=lanczos` frente a `interp=linear`; `-stream_loop -1` y `-t N`. Medida wall con Python perf_counter, incluye decodificación→reproyección→codificación→escritura de MP4.

**CAVEAT CRÍTICO:** fuentes sintéticas **4K y 6K de 2 segundos en bucle** para las duraciones de 5 y 10; fuente **8K de solo 1 segundo en bucle** para las tres duraciones: crear la fuente 8K de 2 segundos no terminó antes del tiempo límite. Las exportaciones a 8K sí terminaron; ninguna representa un vídeo de cámara real continuo. El contenido repetitivo puede cambiar compresión y cachés respecto a secuencias largas. No interpolación móvil por `sendcmd`, no 360 real ni audio, ni estabilidad de encuadre.

## Datos observados
| Origen | Duración | Lanczos s | Bilineal s | Ahorro tiempo |
|---|---:|---:|---:|---:|
| 4K | 2 | 1.584 | 0.937 | 40.8% |
| 4K | 5 | 2.937 | 1.496 | 49.1% |
| 4K | 10 | 4.991 | 2.594 | 48.0% |
| 6K | 2 | 1.659 | 0.933 | 43.8% |
| 6K | 5 | 3.287 | 1.725 | 47.5% |
| 6K | 10 | 5.320 | 3.133 | 41.1% |
| 8K | 2 | 2.344 | 1.150 | 50.9% |
| 8K | 5 | 3.607 | 2.535 | 29.7% |
| 8K | 10 | 6.309 | 4.481 | 29.0% |

El ahorro temporal observado oscila del **29% al 51%** en estos nueve pares. No se puede convertir este porcentaje en mejora total de Montara: exportador real integra otros trabajos.

## Calidad comparada, muestras de 5 segundos
FFmpeg SSIM All de salida bilineal versus salida Lanczos, tras codificar ambos H.264: **4K 0.998949, 6K 0.999205, 8K 0.999199**. Métrica contra Lanczos, NO contra imagen verdad-terreno; no demuestra ausencia de pérdida de detalle, halos, textura fina, colores ni problemas de movimiento.

## Comandos reproducibles
```bash
# Ejemplo 4K; cambiar SIZE por 5760x2880 o 7680x3840 para 6K/8K.
ffmpeg -v error -y -threads 2 -f lavfi -i 'testsrc2=size=4096x2048:rate=24:duration=2' -an -c:v libx264 -preset ultrafast -crf 27 -threads 2 input.mp4
for D in 2 5 10; do
  for I in lanczos linear; do
    ffmpeg -v error -nostdin -y -threads 2 -stream_loop -1 -i input.mp4 -t "$D" \
      -vf "v360=input=equirect:output=flat:yaw=35:pitch=12:h_fov=100:v_fov=62:w=1920:h=1080:interp=$I,format=yuv420p" \
      -an -c:v libx264 -preset veryfast -crf 23 -threads 2 "out_${D}_${I}.mp4"
  done
done
ffmpeg -v info -i out_5_lanczos.mp4 -i out_5_linear.mp4 -lavfi ssim -f null -
```

Para reproducir **exactamente** la variante 8K ejecutada, generar 1 segundo, no 2. La matriz es **un ensayo exploratorio**, no un benchmark E2E, y el orden de ejecución Lanczos→bilinear por par puede introducir efectos de caché/temperatura.

## Decisión y siguiente paso
- **No tocar 360**; conservar Lanczos y los contratos de movimiento, geometría, fotogramas y cachés del motor de José Manuel.
- La reducción de coste sintético es considerable, por tanto guardar alternativa bilineal como opción de **draft/preview** condicionada a consentimiento del autor, calidad visual y test motion sobre material real.
- La prueba pedida (matriz 4K/6K/8K × 2/5/10) está completada con la salvedad importante del contenido repetido, especialmente en 8K.
- **Cerrar este frente por ahora** y continuar otras optimizaciones sin cambios a 360.
