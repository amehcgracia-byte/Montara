# SATURNO — Auditoría de identidad de fotogramas, 2026-10-29

**Tipo:** prueba empírica sintética; **NO** demuestra equivalencia de render Zucker, correlación PTS de fuentes VFR ni minimización de paquetes.

## Protocolo
Linux, FFmpeg disponible en laboratorio; `testsrc2` de 160×90 a 30 fps durante 8 segundos; H.264 libx264, corte 3.2–5.2 segundos mediante `-ss 3.2 -i source.mp4 -t 2 -c:v copy`. Comparación independiente mediante hashes `framemd5` de fotogramas yuv420p **sin** incluir las columnas de timestamp en el hash. Se busca una subsecuencia de hashes contigua y única del original; si falta/sobra un fotograma o hay colisión de secuencias idénticas se bloquea. Test unitarios locales: **6/6**.

## Resultado reproducido
| Fuente | Fotogramas decodificados del fragmento | Resultado |
|---|---:|---|
| H264 GOP=1, sin B-frames | 60 | 60 frames son subsecuencia contigua única; primer frame fuente 96. **PASS de identidad visual de secuencia** |
| H264 GOP=90, 2 B-frames | 62 | Los 62 hashes están en el original, pero hay un salto entre fuente 156 y 158 al final: **FAIL_EXACT_CONTIGUOUS_SEQUENCE** |

**No interpretar el caso fallido como fallo demostrado del decodificador:** buscar por keyframes, edit lists, PTS/DTS y el remux influyen. El éxito GOP=1 no prueba un render Zucker ni equivalencia audiovisual completa.

## Hallazgos metodológicos
- Un hash de píxel correcto no acredita posición temporal. **No deducir PTS a partir del índice** cuando la fuente puede ser VFR.
- La prueba usa el original como referencia **solo durante el empaquetado QA**, nunca prueba obtención de fotogramas ausentes sin fuente.
- El mapa por hashes falla cerrado ante frames repetidos/ambiguos o secuencias no contiguas.
- Pendientes: valores enteros PTS y sus time bases, mapeo VFR, dependencias de paquetes y prueba E2E con Zucker en QA.

## Fuentes técnicas
- FFprobe show_frames: https://ffmpeg.org/ffprobe.html
- Documentación PyAV sobre time_base, PTS y DTS: https://pyav.basswood.io/docs/stable/api/time.html
- Documentación FFmpeg sobre seek y copia: https://ffmpeg.org/ffmpeg.html

**Artefactos locales descargables de la conversación:** `/mnt/data/saturno_timeline/frame_map.py`, `test_frame_map.py`, `REPORT.md`, `measured.json`, `intra.json`. Esta publicación documental **no incluye aún esos scripts**. Ningún cambio en main, ZuckerVideos o ZuckerMixer.
