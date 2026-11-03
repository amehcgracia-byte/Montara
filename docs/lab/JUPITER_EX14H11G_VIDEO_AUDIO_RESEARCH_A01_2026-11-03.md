# JÚPITER EX-14H-11F/G + A-01 — Stage 360 A/B y apertura de investigación de audio

**Fecha:** 2026-11-03 · **Estado:** resultados observados y revisión bibliográfica inicial; *sin integración a producción*. Investigador laboratorio FER. Motor local `0f9ec03` (pin `affe97a4` con EX-07/EX-13 opt-in y adaptador Stage), rama `fernando/ex14h09-current-optin`.

## 1. Validación EX-14H-11F — ExportStage real
- ExportStage.run() real, modo Reel horizontal 1080p30, **una toma de 2s (60 frames)** con original HEVC 360 3840×1920 y movimiento yaw; máster de audio real de un proyecto FER; cada ejecución tenía proyecto/caché aislados. Flags opt-in por proyecto; sin cambios productivos.
- La instrumentación `_ex14h11_native_calls` confirmó **una llamada al reproyector por export**, `source_original=true`, `frame_count=60`, flags A=False/False, B=True/True; sin avisos, rendered_from=original, cached=False.
- ABBA tiempos export total: **A1 6.540s, B1 5.692s, B2 5.733s, A2 6.351s**. Medias A 6.446s vs B 5.713s = **−11.37% wall** observado (2 muestras por configuración).
- Tiempo del segmento: A1 5.145s, B1 4.301s, B2 4.334s, A2 4.919s. No confundir ahorro del segmento con el total ni extrapolar a grandes jam/multicámara.
- Todos los outputs 60 fotogramas / audio decodificable y 385024 bytes de PCM audio decodificado, **audio SHA256 idéntico entre todas las salidas**: `e6215d07a7acf3fb6292e4a0c32c05d93769d9bf61bff60ef274b9d101ab16e3`.
- Todos los SHA256 RGB decodificados distintos, **incluso A vs A y B vs B**. NO PASS de fidelidad bit-exact Stage, NO conclusión de regresión causada por EX07/13.

## 2. EX-14H-11G — Diagnóstico intra-condición vs inter-condición
Nueva batería Stage ABBA, cuatro exportaciones con perfiles equivalentes. Comparación de **cada byte RGB decodificado** en las secuencias de 60 cuadros y de los segmentos de caché pre-ensamblado. Audio nuevamente idéntico. Las cuatro salidas y los cuatro segmentos generaron hashes distintos; la variación aparece **antes del mux final**.

| Pareja | MAE RGB [0..255] | Canales distintos | Canales delta>8 | Mayor delta |
|---|---:|---:|---:|---:|
| A1/A2 | 0.242323 | 15.32277% | 0.00190% | 18 |
| B1/B2 | 0.253661 | 15.92343% | 0.00227% | 22 |
| A1/B1 | 0.257623 | 16.12695% | 0.00237% | 24 |
| A2/B2 | 0.257183 | 16.20039% | 0.00207% | 18 |

**Interpretación prudente:** MAE A/B similar a la variabilidad de dos renders con idénticos flags, consistente con variabilidad de codificación/processing. **No demuestra** por sí solo que la geometría A/B sea idéntica, ni que la variabilidad proceda exclusivamente de x264; es indispensable una comparación de fotogramas **pre-codificador** y, en su caso, una valoración visual sobre varias escenas y puntos sensibles (costuras, bordes, movimiento). EX-14H-10, pipeline aislado con codificador controlado, sí acreditó coincidencia exacta de 60 cuadros decodificados entre A/B para un plano artificial diferente.

## 3. Revisión externa científica específica — referencias consultadas
### Calidad y sincronización audiovisual
- **WACV 2025**, Voas y col., *Temporally Streaming Audio-Visual Synchronization for Real-World Videos*. StreamSync, sincronización temporal en contenidos largos; https://openaccess.thecvf.com/content/WACV2025/html/Voas_Temporally_Streaming_Audio-Visual_Synchronization_for_Real-World_Videos_WACV_2025_paper.html. Aplicabilidad: ideas para evaluar offsets y drift de sesiones reales; **no** acelerar el mux de Stage de manera directa ni implantar un modelo sin medición de necesidad.
- **CVPR 2025**, Zhou y col., *HarmonySet: A Comprehensive Dataset for Understanding Video-Music Semantic Alignment and Temporal Synchronization*. https://openaccess.thecvf.com/content/CVPR2025/html/Zhou_HarmonySet_A_Comprehensive_Dataset_for_Understanding_Video-Music_Semantic_Alignment_and_CVPR_2025_paper.html. Aplicabilidad: cortes musicales y alineación rítmica; no se ha demostrado una mejora directa al pipeline actual.
- **Disney Research 2024**, *DiVAS: Video and Audio Synchronization with Dynamic Frame Rates*. https://studios.disneyresearch.com/app/uploads/2024/05/DiVAS-Video-and-Audio-Synchronization-with-Dynamic-Frame-Rates-Paper.pdf. Aplicabilidad: validación A/V con distintas cadencias y condiciones, no procesamiento más rápido.
- **IEEE TIP 2025**, *Subjective and Objective Audio-Visual Quality Assessment for Omnidirectional Videos*, https://pubmed.ncbi.nlm.nih.gov/41052156/. Aplicabilidad: auditar experiencia A/V en 360, sin cuantificar nuestra optimización.
- **IEEE SPL 2025**, *Viewport-Patch Extraction Enhanced 360° Video Quality Assessment*, https://ieeexplore.ieee.org/abstract/document/11304536. Aplicabilidad: QA geométrica y temporal por viewport, evitando depender exclusivamente de RGB MAE global. Publicación en línea diciembre 2025.

### Audio comprimido y cortes sin transcodificación
- **Apple**, *AAC encoding background*, https://developer.apple.com/documentation/quicktime-file-format/background_aac_encoding : unidades AAC-LC habitualmente 1024 muestras (a 48 kHz ≈21,33 ms), priming/encoder delay y remainder. No son GOP de vídeo; extraer/remultiplexar paquetes AAC con límites arbitrarios necesita manejar timestamps/priming y riesgo de samples perdidos/desplazados.
- **Journal of Forensic Sciences 2025**, Wales, *Quantitative study of zero-amplitude sample padding in iOS AAC encoding*, https://doi.org/10.1111/1556-4029.70157 . Observa padding variable: un SHA PCM desigual puede reflejar retrasos/padding en vez de contenido audible distinto. Importa para diseñar tolerancias de sincronía, no prueba ahorro de CPU.
- **AES eLibrary 2024**, *Quantitative Analysis of Zero-Amplitude Sample Padding in AAC Audio: Exploring Transcoding Effects and Implications for Audio Stream Hashing*, https://aes.org/publications/elibrary-page/?id=22626. Efectos de transcodificación en padding y hashes.
- **FFmpeg** documentación `-c copy` / remux / timestamps https://ffmpeg.org/ffmpeg.html; **libswresample** `aresample=async`, `first_pts`, https://ffmpeg.org/ffmpeg-resampler.html. No activar compensación de drift sin medir si hay desfase fijo, progresivo o irregular.

## 4. Auditoría de código exportador: qué audio ya hace Montara
Lectura en ZuckerVideos `core/stages/export.py` pin `affe97a4`:
- `_try_direct_concat_master_audio` existe: intenta una concatenación y mux de master en una pasada, verificando cadencia antes del fallback.
- `_mux_continuous_master_audio` utiliza `-c:v copy` y **`-c:a aac -b:a 192k`**; aplica `atrim`, `asetpts`, `apad`, `adelay` y `afade` cuando procede. Por tanto **ya evita re-encode de vídeo en este mux**, pero **sí recodifica audio**, previsiblemente por necesidad de cortes, fades y continuidad. No prometer `-c:a copy` general: omitiría esos filtros o cambiaría su semántica.
- Este A/B de 2s produjo **PCM idéntico** entre flags EX07/13, pero no es un benchmark independiente del audio, ni demuestra sincronía durante conciertos largos, ni que el audio sea cuello de botella. La diferencia entre tiempo de segmento y Stage total tampoco debe atribuirse toda al audio (verificación/ensamblado/etc).

## 5. Nueva línea de investigación A-01 AUDIO (pendiente, priorizada)
**A1, inventario read-only**: los archivos/audio master de FER sin leer material personal de JM; formato PCM vs AAC/MP3, canales, frecuencia, tasa, duración y tamaño, ruta actual de audio `ingest/sync/mix/export`, y mapa `performance.phases` para separar render vs mux vs verificación. Determinar coste audio real antes de optimizar.
**A2, hipótesis medibles**: (i) reutilización segura de salida master audio ya procesada entre Reel/YouTube/Push si el mismo contenido y filtros; (ii) mux sin transcode solo para segmentos de audio ya canónicos, sin `atrim/afade/adelay/apad` efectivos y con priming/timestamps compatibles; (iii) audio packet-selective transfer estilo SATURNO para uploads o transferencias externas si el tiempo total de bytes lo justifica; (iv) proceso/duplicación de decodificación de audio en sync/mix (sin cambiar algoritmo sin perfilado).
**A3, QA primero**: diferencia de muestras, duración, primer sample/PPTS, offset inicial vs drift progresivo, click en bordes de corte, loudness y picos; pruebas WAV/FLAC/AAC/MP3, master largo, y clips offset. Registrar condiciones exactas que habilitan audio copy o cachés; no sacrificar sincronía ni fades por velocidad.
**GATE:** invertir esfuerzo solo si audio/mux/transferencia supone coste significativo respecto a decode/export de vídeo y del flujo completo, y si no está ya solucionado. Reportar latencia total, consumo RAM/disco y calidad perceptual además de tiempo de función.

**Siguiente trabajo JÚPITER**: experimentar A/B vídeo pre-encoder de forma aislada y, en paralelo documental, A-01 inventario audio, sin mutación en motor productivo ni nuevas notificaciones a Chema hasta hito sustantivo.
