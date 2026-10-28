# Auditoría de fuente esférica y literatura aplicable — 2026-10-28

Rama de registro: `fernando/continuacion-montara`. Fuente de verdad: submódulo ZuckerVideos anclado en `60a7b7e9a39077b36f45057811abd6a833a168ef`; benchmarks PR #6 `15aa4d6`. **No se ejecutaron benchmarks ni se modificó el motor.**

## Hallazgo que evita duplicar un arreglo existente
`core/stages/export.py`:
- L793–807 llama `_spherical_sources_to_prepare` y contabiliza `source_prepare_sec` y `source_proxy_count`.
- L2128–2154: `_spherical_sources_to_prepare` recorre segmentos y solo prepara fuentes para las que `_spherical_uses_original_motion(info, segment, draft)` es false. La documentación en código dice que el movimiento esférico nativo lee directamente el original, y que el proxy de archivo completo para esas tomas se desperdiciaría. Los borradores sí leen el proxy.
- L2157–2255: un proxy export esférico está pensado para decodificar una sola vez el archivo panorámico y reutilizarlo. Clave sha256 de ruta, tamaño, mtime, proyección, FOV, versión y 2560×1280; salida bajo caché global; `ultrafast` CRF18 x264; se guarda temporal y se renombra. Debe vigilarse ocupación y coste de recalcular al cambiar inputs.
- L636–642: `_export_draft` tiene reglas expresas para originales vs proxy de 2560×1280.
- `core/review_previews.py` crea clips de 480×270 a 15fps, `veryfast` CRF30; caché por intervalo, fuente, mtime, movimiento y framing; prefetch unitario, no proxy total.
**Conclusión:** el antiguo episodio de 866s de preparación de proxy 360 sin uso tiene una prevención explícita en la revisión actual. No afirmar que sigue siendo un bug sin reproducir un caso actual. Una regresión focalizada es más útil que reimplementar esta política.

## Papers externos y traducción realista
1. Nguyen et al., **Adaptive Tiling Selection for Viewport Adaptive Streaming of 360-degree Video**, IEICE 2019, DOI 10.1587/transinf.2018MUL0001 — https://www.jstage.jst.go.jp/article/transinf/E102.D/1/E102.D_2018MUL0001/_article . Investiga selección de teselas dependiendo de ventana de vista. **No es equivalente a render multicámara cinematográfico**: podría inspirar proxies 360 que cubren solo ventanas de vista durante revisión, pero no usar tiles sin verificar movimientos del encuadre y discontinuidades de borde.
2. Chen et al., **Optimized viewport-adaptive 360-degree video streaming**, CAAI TINT 2021, DOI 10.1049/cit2.12011 — https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/cit2.12011 . HEVC tiles, MCTS y bitrate adaptativo para ahorrar red/almacenamiento. Aplicable principalmente a PREVIEW REMOTA con restricciones de viewport; no asumir mejora de export final.
3. Adhuran & Martini, **Efficient viewport prediction and tiling schemes for 360 degree video streaming**, ACM MMSys 2024, DOI 10.1145/3625468.3653425 — https://openresearch.surrey.ac.uk/esploro/outputs/conferenceProceeding/Efficient-viewport-prediction-and-tiling-schemes/99928856202346 . Estudia predicción/selección de tiles sobre evaluación E3PO. Su aportación podría probarse solo con encuadre dinámico y horizonte previsible, coste de empaquetado medido.
4. Farooq et al., **Adaptive 360° Video Streaming: Prediction, Tiling, and Transport Trade-Offs**, Network 2026, DOI 10.3390/network6030066 — https://www.mdpi.com/2673-8732/6/3/66 . Revisión reciente de costes de viewport prediction, tiles y edge. Útil para descartar un mecanismo de streaming demasiado complejo para nuestro objetivo editorial.
5. Silhavy et al., **Machine Learning for Per-Title Encoding**, SMPTE 2022, DOI 10.5594/JMI.2022.3154836 — https://journal.smpte.org/periodicals/SMPTE%20Motion%20Imaging%20Journal/131/3/14/ . Demuestra ventajas de parámetros adaptados al contenido; la inferencia para Montara es explorar un probe/clip representativo y una política de encode condicionada por bitrate/resolución/complejidad/uso, sin integrar ML antes de demostrar que un umbral simple falla.
6. Documentación FFmpeg https://ffmpeg.org/ffmpeg.html sobre aceleración hardware: advierte que el traslado de frames GPU→CPU puede perder ventaja y que disponibilidad de acelerador no garantiza speedup. Test end-to-end incluyendo CPU↔GPU copy, decode, remap, encode, upload y retorno, por separado de procesamiento puramente local.

## Experimentos que merecerían aprobación tras línea base
A. **Regresión de prevención de proxy sin consumidor**, offline y sin recodificar media real: fixture con 65 segmentos 360 nativos HDR/SDR según política y prueba de predicado/schedule; verificar que para tomas nativas finales no se llama a preparación; en draft sí cuando corresponda. La política ya existe; solo mejorar test si los actuales no la cubren.
B. **Preview 360 bajo demanda / viewport-selective**: alternativa a proxy de esfera completa solo para vistas preseleccionadas, solo si análisis real muestra que el consumo de proxies de export/revisión es relevante. Medir continuidad de movimientos yaw/pitch/FOV; 360 feedback, no sustituir salida final equirect.
C. **Codificación por fuente/per-title para preview**: cuando el material origen ya es de bajo bitrate, medir proxy actual frente preset/CRF distintos y bypass condicionado. Variables: tamaño, bytes/min, latency until first preview, RAM, calidad perceptual, browser seek, audio sync. No extrapolar de fuente sintética.
D. **GPU-first no es dogma:** comparar decode+reproject+encode y tiempo global, transferencia local/remota. Tener ruta local/CPU estable y no mezclar cambios de calidad con cambios de hardware.

## Arquitectura híbrida: contratos aún no diseñados
- Modelo universal del proyecto: ID estable de fuente, intervalos, coordenadas 360, audio, efectos y una receta declarativa versionada, verificable y neutral al dispositivo. Primero inspeccionar `core/project.py` y contratos exactos del motor antes de inventar esquema.
- El planificador decide CPU local / GPU local / GPU remota solo si el procesador puede acceder a archivos; el browser directory handle es local al navegador, no al servidor.
- Medir coste E2E = preparar subidas (si existen) + envío + cola + procesamiento + descarga + comprobación. Medir artefactos intermedios y RAM bajo las condiciones de Oracle Always Free antes de estimar concurrencia.
- Control de calidad: preview puede usar proxy y bitrate distinto; export final debe respetar originales, gamut/transfer, sincronía, reproyección y timing.

Este documento es una auditoría estática combinada con referencias bibliográficas; no se atribuye ninguna cifra de ahorro de los papers a Montara ni se ejecutan pruebas nuevas.
