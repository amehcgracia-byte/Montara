# JÚPITER EX-14H-12D — Codificador H.264 aislado: resultados y contraste con Stage

Fecha: 2026-11-03. FFmpeg `/usr/bin/ffmpeg` 6.1.1-3ubuntu5. Original HEVC 360 real, 60 cuadros reproyectados BGR 1920×1080 30 fps, capturados una vez desde Stage en archivo temporal de 373248000 bytes. Sin cambios en engine ni FFmpeg de sistema.

## Ensayo ABBA codificación aislada

A `-threads 2`: 1.401 / 1.395 s, media 1.398 s, MP4 1918930 B, SHA256 MP4 idénticos `3be4e0982e539decd03786582cf38092ca3009b6afa21dff52bafca7a293fb0b`, RGB decodificado SHA256 idénticos `d9d78b84d83b00dfc8ce7134f8b7af77b8ffb984f2d73d9634e7798fd4553586`.

B `-threads 0` (auto): 0.845 / 0.850 s, media 0.8475 s, MP4 1885726 B, SHA256 MP4 idénticos `bd064d832729516164c7d15bc812021877c0893a016f0d042884a38544b89cb8`, RGB decodificado SHA256 idénticos `128e0c157ad5692fd091c910bdb75d43b6f19055be7e2b49dfe1e`. A/B MP4 y RGB no idénticos. Reducción observada de wall 39.38%, limitada al encoder aislado, calidad relativa no evaluada.

## Hallazgo del examen estático de Stage

En pin ZuckerVideos `affe97a4`, `core/stages/export.py::_render_segment` para 360 nativa prepara FFmpeg con raw BGR de pipe, grafo complejo `_segment_filtergraph`, SDR output args, `-fps_mode cfr`, `-video_track_timescale`, y `_video_encode_args('libx264', video_bitrate)`. En `_video_encode_args` no hay `-threads 2`, y `_render_segment` no limita hilos del encoder. El `-threads 2` del proceso decodificador HEVC está en `core/spherical_motion.py::_run_reprojected_command`, separado de la codificación.

**Conclusión:** el modo automático ya es el predeterminado del encoder de Stage; NO presentar el 39.38% aislado como mejora disponible en producción. La prueba aislada carecía de algunos filtros y control VBV de Stage, por lo que no atribuirle causalmente la variabilidad post-remap del propio Stage.

**Siguiente paso:** registrar el comando exacto del encoder de un solo render Stage (sin archivos privados ni modificación del motor) y ejecutar un control reproducible con exacto filtergraph, codec args y entrantes BGR fijos. Valorar si la variación de Stage se debe a entradas de filtros/capacidades concurrentes, y si el coste de filtrar/cadencia/validar es significativo. No hacer upgrades de FFmpeg compartido ni tocar producción.

## Barreras

- Fidelidad preencoder EX14H12C: 60/60 píxeles exactos en cuatro ABBA; el encode/postprocesado produce variación entre MP4.
- EX07/EX13 aún opt-in y sin integración; EX06 fuera por diferencia visual.
- A01 audio aparcado hasta concluir perfilado vídeo/360.
