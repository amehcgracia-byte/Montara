# JÚPITER-18 — Small test 360 4K→1080p sin tocar Zucker (2026-10-28)

## Decisión y alcance
Ensayo *externo* al motor 360, con FFmpeg Linux 7.1.5. **No modifica Montara, ZuckerVideos ni ZuckerMixer, no activa ninguna opción por defecto**. Sirve para decidir si merece un experimento específico en draft; NO valida integrar bilineal en exportación final.

## Fixture realmente ejecutado
Fuente *sintética* equirectangular de 4096×2048, testsrc2 a 24 fps, 2 s, H.264 CRF24 preset ultrafast; archivo fuente ~11 MiB. **NO es captura 360 real de cámara**, por lo que no contiene la textura, detalle natural, luz, movimiento óptico o codecs de fuente de un proyecto real. La vista sintética rotó yaw=35°, pitch=12°, FOV horizontal=100°, FOV vertical=62°, salida 1920×1080. El encoder de salida H.264 libx264 preset veryfast CRF23 2 threads, sin audio.

Solo se modifica `interp=` del filtro:
`v360=input=equirect:output=flat:yaw=35:pitch=12:h_fov=100:v_fov=62:w=1920:h=1080:interp=lanczos|linear,format=yuv420p`

Cuatro exportaciones independientes en orden Lanczos, linear, linear, Lanczos (incluyen lectura/decodificación, filtro, libx264, escritura).

| interpolación | ejecución | wall s | salida bytes | código salida |
|---|---:|---:|---:|---:|
| lanczos | 1 | 1.841 | 95,796 | 0 |
| linear | 1 | 0.703 | 87,426 | 0 |
| linear | 2 | 0.725 | 87,426 | 0 |
| lanczos | 2 | 1.524 | 95,796 | 0 |

Promedios: Lanczos 1.6825 s; bilinear 0.714 s, reducción de wall time ~57.6% **de este clip de 2 segundos, no de Montara**. Dos muestras por variante: pequeño tamaño, sin intervalos de confianza ni prueba de saturación/temperatura.

Comparación de los dos archivos codificados primera ejecución, usando FFmpeg `psnr` y `ssim`, reference Lanczos, target linear:
- PSNR avg 51.820700 dB, min 49.526376 max 53.150088
- SSIM All 0.999055 (Y 0.999334 U 0.998337 V 0.998658).
Ambas medidas son distancia con **Lanczos**, no verdad de terreno ni calidad perceptual. Compresión encoder y diferencias en tamaño contribuyen. No inferir indistinguibilidad visual a partir de SSIM alto.

## Precauciones
- **No movimiento por frame:** `sendcmd [expr]` de Zucker `_v360_motion_commands` no interviene en este ensayo.
- No original 5K/6K, caras, texto fino, cables, color HDR, raw_insv, reproyección doble, audio, multiplexación, caché, timeline, QA Stage; no es Montara E2E.
- Aumentar nitidez vs halo/aliasing es una decisión de calidad, y el primo del usuario ha trabajado mucho en asegurar la fiabilidad de 360.
- En `zucker_videos@60a7b7e9`, `core/stages/export.py` `_export_source_filter` tiene `interp=lanczos` y el modo draft existe; **no modificar motor 360** sin revisión explícita de su autor.

## Veredicto
**Experimento confirmado**: bilinear reproyecta/exporta más rápido en un fixture sintético 4K→1080p. **No recomendar cambio universal ni integración en final**. Como potencial futuro, estudiar opción *solo draft* de menor coste y receta de caché separada, una vez que el autor lo acepte y exista validación visual con 360 real. Si no desea tocar 360, **cerrar esta línea ahora** y pasar a optimizaciones con mayor valor transversal (ingest, orquestación local↔servidor, puntos de copia) sin invadir algoritmos de encuadre.

## Reproducibilidad
```bash
ffmpeg -hide_banner -loglevel error -threads 2 -f lavfi -i 'testsrc2=size=4096x2048:rate=24:duration=2' -an -c:v libx264 -preset ultrafast -crf 24 -threads 2 -pix_fmt yuv420p -y equirect_4k.mp4
for interp in lanczos linear; do
  ffmpeg -hide_banner -loglevel error -threads 2 -i equirect_4k.mp4 -vf "v360=input=equirect:output=flat:yaw=35:pitch=12:h_fov=100:v_fov=62:w=1920:h=1080:interp=${interp},format=yuv420p" -an -c:v libx264 -preset veryfast -crf 23 -threads 2 -pix_fmt yuv420p -y "${interp}.mp4"
done
ffmpeg -i lanczos.mp4 -i linear.mp4 -lavfi psnr -f null -
ffmpeg -i lanczos.mp4 -i linear.mp4 -lavfi ssim -f null -
```
Wall time measured externally with `time.perf_counter()`; actual run used 4 render repetitions in alternating order. CPU cgroup quota 4 CPU.
