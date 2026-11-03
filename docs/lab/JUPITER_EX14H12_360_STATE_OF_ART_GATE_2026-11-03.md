# JÚPITER — EX-14H-12: revisión comparativa de tecnologías 360 antes de priorizar audio
Fecha: 2026-11-03 · Estado: investigación externa y decisión de puertas científicas, **sin implementación ni benchmark nuevo**

## Por qué no cerrar EX-14H
EX-14H-10: pipeline 360 aislado con salida RGB exacta, **−18.35% wall** EX07+EX13. EX-14H-11F: ExportStage real Reel horizontal 2 segundos, 60 frames, con flags por proyecto y `source_original=true`, tiempo medio 6.446→5.713s, **−11.37% wall** (n=2 por modalidad). EX-14H-11G: hashes RGB diferentes incluso entre A/A; MAE 0.242323 (A/A), 0.253661 (B/B), 0.257623 (A1/B1), 0.257183 (A2/B2). Audio PCM idéntico. Conclusión: no hay evidencia de degradación visual apreciable en este caso, pero NO equivalencia exacta preencoder, ni generalización a actuaciones largas. La ruta optimizada está aislada y opt-in; producción inalterada.

## Nuevas referencias y métodos contrastados
1. FFmpeg **v360_vulkan**, anuncio de propuesta abril 2026, filtro/documentación en árbol FFmpeg de octubre 2026. Fuentes: https://www.mail-archive.com/ffmpeg-devel%40ffmpeg.org/msg188481.html ; https://www.ffmpeg.org/doxygen/trunk/vf__v360__vulkan_8c_source.html ; https://www.mail-archive.com/ffmpeg-cvslog%40ffmpeg.org/msg77240.html. Tiene controles dinámicos de rotación y subset de formatos; todavía NO verificado disponible en FFmpeg de la VM, ni equivalencia con interpolación/sweep/pose sampler de Zucker. Especialmente importante por errores históricos de sendcmd v360 clásico.
2. ACM VRCAI'25, publicado 05-02-2026, *Efficient Projection of Panoramic Video onto Cube-Based Layouts for Immersive CAVE Visualization*, DOI 10.1145/3779232.3779286; https://doi.org/10.1145/3779232.3779286. GPU CUDA + FFmpeg y reducción de transferencias/cambio de contextos; 8.17ms→1.79ms→0.57ms por frame en RTX A5000 **en su geometría y su prueba** (no Stage). La estrategia de cero copias/interop GPU merece investigación en worker GPU; no prometer aquellos tiempos.
3. NVIDIA PyNvVideoCodec 2.2, documentación https://developer.nvidia.com/pynvvideocodec y https://docs.nvidia.com/video-technologies/pynvvideocodec/. Decodificación/encode HW, índices temporales, buffers en memoria, threaded decode; requiere NVIDIA y arquitectura diferente. Candidato RunPod, no para GCP e2 CPU.
4. OpenCV documentación de `cv2.convertMaps` https://docs.opencv.org/5.0/main_modules/imgproc_transform.html; fixed-point maps y remap acelerado según backend. **EX-05 YA probó** convertMaps+remap, no repetir sin nuevo cuello demostrado.
5. FFmpeg `v360` CPU y filtrado estático también han sido medidos en F4; distinto de `native_remap`. La calidad de interpolación bilineal vs cubic EX06 ya fue explorada, decisión pendiente de calidad, no mezclar con EX07/13.

## Matriz de decisiones
- **Prioridad 1, misma máquina**: verificar equivalencia **antes de encoder** (float maps, decoded RGB input, pose/frame, pixels BGR tras remap), 60 frames de un clip real con holds y movimiento, bordes/seam. El SHA de H.264 final puede variar aun para A/A.
- **Prioridad 2, mismo pipeline CPU**: medir fases decode_wait/map/remap/write_wait/encode, pico RAM y saturación por hilos; contraste con EX-05 para evitar duplicación.
- **Prioridad 3, alternativas**: examen estático de disponibilidad real `ffmpeg -filters` de v360_vulkan y dispositivos Vulkan, sin instalar nada en sistema; verificar semántica de opción dinámica y encuadre antes de A/B.
- **Prioridad 4, cuando GPU disponible**: comparación fair y coste €/min vídeo de CPU original, CPU EX07/13, v360 Vulkan viable, CUDA worker decode→projection→encode; benchmarks con misma fuente y encuadre, calidad y coste de transferencias.
- **Prioridad 5, arquitectura producto**: tasa real de planos 360 y movimiento en conciertos, solapamiento en 2/5/10 jobs, viabilidad Companion local vs worker remoto, influencia de subida SATURNO y energía/costo. No optimizar cuellos que no pesan en workflow real.

## Audio — A-01 archivado como segunda vía, sin abrir optimización todavía
Inventario actual: master de referencia **PCM s16le, 48 kHz, mono, 20s, 1,920,078 bytes**. Esto pertenece a un fixture de laboratorio, **NO una grabación de concierto representativa**, por lo que no se puede usar para generalizar CPU/audio. Fases de un manifiesto anterior `assembly=direct_concat_audio`, `cadence_sec=2.391`, `mux_sec=0.363`, intro 0.039, outro 0.028, source_prepare 0.0. No achacar cadence al audio. `_mux_continuous_master_audio` ya usa vídeo stream-copy y aplica fades/trim/delay/pad con audio AAC re-encode por necesidad semántica. Futuro A-01: inventario de cargas reales y validación de packet copying con trim/priming y sync; nunca prometer `-c:a copy` universal.

## Stop conditions
- A/B preencoder muestra diferencias importantes de geometría, costura o calidad perceptual.
- Nuevo método necesita un dispositivo inaccesible o añade costo operativo > ahorro real.
- El cuello medido no explica wall de Stage bajo cargas representativas.
- Nunca activar mejoras de forma global antes de aprobación de Chema.
