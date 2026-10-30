# JÚPITER — Inventario real y criterios de ensayo (2026-10-30)

## Fuente
Metadatos `ffprobe` compartidos por Fernando desde `/home/fer/lab-clips/originales`. No inspección de fotogramas ni hashes; estos metadatos son informativos, no prueba de identidad/origen ni calidad visual.

| Fichero | Duración (s) | Tamaño (bytes) | Vídeo | Audio / notas |
|---|---:|---:|---|---|
| IMG_0044.MOV | 986.825011 | 3551746708 | H.264 3840×2160, avg 2218725/74012 ≈29.978, r 30000/1001; BT.709 yuv420p; rotación -180 | AAC mono 44100; posible VFR no probado |
| VID_20260824_204524_00_004.mp4 | 911.64 | 2521799326 | HEVC 3840×1920 25 fps, yuvj420p BT.709 | AAC estéreo 48000; proyección 360 anunciada por Chema, metadatos provistos no confirman etiqueta esférica |
| C0188.MP4 | 89.76 | 570452494 | H.264 1920×1080 25 fps, BT.709 | PCM s16be estéreo 48000; datos auxiliares |
| 03 - The Floor Remembers_v1_20261004_170913.mp3 | 634.044082 | 25362946 | sin vídeo | MP3 estéreo 44100 |
| download.mp4 | 294.801 | 53148018 | AV1 1920×1080 24 fps, BT.709 | Opus estéreo 48000 |
| preview.mp4 | 294.801 | 23657978 | H.264 960×540 24 fps, BT.709 | AAC estéreo 48000 |
| reel-1/2/3/4.mp4 | 32.625 / 38.625 / 33.5 / 30.416667 | 5849250 / 6608860 / 4882853 / 9049825 | H.264 720×1280 24 fps, BT.709 | AAC estéreo |
| analysis.wav | 294.7935 | 4716774 | sin vídeo | PCM 8000 mono |
| speech-16k.wav | 294.7935 | 9433470 | sin vídeo | PCM 16000 mono |

## Hallazgos
1. El iPhone **no es HEVC HDR según este probe**, sino H.264 SDR rotado 180°. Promedio ≈29.978 vs r_frame_rate ≈29.970: **indicio**, no prueba de VFR. Confirmar mediante PTS de ventana acotada, no mediante media global.
2. Vídeo 360 real es HEVC 3840×1920, **4K equirectangular reportado por Chema, no 5.7K**. Se requiere confirmar proyección y contenido visual antes de afirmar calidad F4 para 360 real.
3. Sony H.264 1080p 25fps es contraste útil con audio PCM, pero no comparar sus segundos de CPU con iPhone 4K/360 sin normalizar tareas.
4. Los archivos `download`, `preview`, reels y WAV parecen materiales de otro flujo por duración compartida, pero **no se ha probado su procedencia**. No usarlos como pareja A/B hasta verificar asociación.
5. El MP3 (634 s) no coincide automáticamente con 90 s de Sony o 911–987 s de fuentes: no asumir sincronía o cobertura común.
6. Carga `uptime` ~33/31/23 en 8 vCPU. No lanzar render ni benchmark ahora; comprobar luego con Chema qué la ocasiona, sin matar procesos de terceros.

## Próximas comprobaciones de bajo coste
- `ffprobe` con `-read_intervals` corto sobre el iPhone para PTS y distribución de deltas, conservar exacta fracción y tamaño de ventana; no inspeccionar millones de frames.
- `ffprobe` format/stream tags y side_data de 360 para establecer soporte de proyección.
- Solicitar o identificar un verdadero ejemplo **iPhone HEVC 4K HDR VFR** si sigue siendo necesario certificar ese caso; el actual no cubre su matriz.
- Para F4 usar 2–5 segundos reales elegidos por presencia comprobable de cara/letras/cables y dejar explícito que bilinear/lanczos no debe evaluarse solo por SSIM agregado.
- Para FOCUS A/C crear plan efectivamente analizado con proxies, luego reubicar al original con mismo timing y controles rigurosos; no confundir con plan sintético generado desde originales.
- Antes de cualquier trabajo pesado, aviso al operador; `montara-bench` y comprobar carga independiente de jm.
