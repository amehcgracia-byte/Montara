# LUNA JUPITER-03 — auditoría inicial de proxies, cachés y render (2026-10-28)

**Estado:** análisis estático de código anclado a revisiones de submódulos. No se han ejecutado benchmarks nuevos. No modificar `main`, `engine/`, `mixer/` ni infraestructura sin acuerdo.

## Revisiones auditadas
- Montara `main`, submódulo ZuckerVideos `60a7b7e9a39077b36f45057811abd6a833a168ef`.
- ZuckerMixer `c7a46a6d8388c6e0703ef54983f2d627ea189f32`.
- Auditoría complementaria de Montara `local_media/proxies.py`, `show_playback.py`.

## Hallazgos fundamentados y NO candidatos a reimplementar
1. **Proxies rápidos ya existen.** `zucker_videos/core/review_previews.py`: hover previews *a demanda*, prefetched por un único trabajador en segundo plano, 480×270 a 15 fps, x264 `veryfast` CRF30 sin audio. Clave SHA256 por fuente/mtime/segmento/encuadre/movimiento; escritura mediante temporal + `os.replace`, reutilización si el artefacto existe y no está vacío. Son clips cortos, no proxies de toda la fuente. **No sustituir por un transcode completo experimental.**
2. **El motor YA tiene evaluación A/B de export.** `zucker_videos/tools/benchmarks/render_ab.py`: compara frío/caliente, rechaza borrar cachés de usuarios y evita sobrescribir outputs; `segment_costs.py` descompone esperas de decodificación, reproyección, encode y verificaciones; `conversion_costs.py` hace pruebas controladas HEVC. Reutilizar estas herramientas y adaptar medición a plataformas en lugar de escribir otra batería desde cero.
3. **Existe protección de pipeline/caché.** `core/render_watchdog.py` observa progreso CPU/salida para evitar falsos timeouts; `tests/test_composition_base_cache.py` verifica metadatos y conservación de base de composición; `tests/test_export_cache_attestation.py` verifica atestación de caché. No asumir que un simple stat equivale a una caché válida.
4. **Mixer también trata deliberadamente el almacenamiento local.** `ZuckerMixer/project_storage.py` coloca estados junto a sesiones originales (en `ZuckerMixer/`) sin mover grabaciones ni exports, con migración comprobada por hashes antes de eliminar estado anterior. `preview_encoding.py` pasa audio PCM por pipe a FFmpeg, evitando escribir/leer un WAV temporal completo. `test_compressed_stem_cache.py` comprueba caché PCM para stems MP3/M4A. No presentar ninguna de esas ideas como novedades.
5. **Distintas clases de proxy según objetivo:** `Montara/show_playback.py` compone segmentos para la reproducción continua de Show mediante FFmpeg 1280×720, 30 fps, x264 ultrafast CRF24, AAC 128k. Se ejecuta en hilo backend, guarda archivos cacheados por fuente/tamaño/mtime/cortes, y serializa renders con `render_lock`. `Montara/local_media/proxies.py`, por separado y **sin integrar**, crea un proxy 960px/veryfast/CRF28/AAC96k de fuente completa (o 2048×1024 para esfera) y una receta con referencia al original. Sus metadatos tienen claves separadas para información pública y rutas privadas.
6. **El usuario verificó en un experimento externo**, NO en el pipeline principal: fuente H.264 835.384 s 41.48 MiB → proxy 640px x264 ultrafast CRF28 73.72 MiB en 63.509 s. El proxy fue ~77.7 % más grande. Este dato señala riesgo de presets/tasa de bits al codificar una fuente ya muy comprimida; no prueba fallo del motor existente.

## Hipótesis que merecen medición, no cambios inmediatos
A. **Presupuesto de almacenamiento por categoría.** La memoria se mide separando: originales, thumbnails/hover previews, show_playback, composición, caches de audio, exportaciones, archivos temporales. En relación con minutos procesados, cantidad de revisiones y fuente. Tomar muestras reales antes de imponer cuota/purga.
B. **`show_playback.py` x264 ultrafast CRF24** podría generar más bytes que `veryfast` u otras opciones cuando el original es muy comprimido. A/B emparejado con misma fuente y cortes: ultrafast/veryfast, CRF24/28, 720p/540p; evaluar tamaño, segundos de encode, seek, primera imagen, continuidad, fidelidad y CPU. Este módulo usa `render_lock` global, que puede serializar escenas: medir cola y simultaneidad antes de alterarla.
C. **Invalidación de caché:** `review_previews.py` usa mtime además de parámetros de framing y su caché es positiva por tamaño no vacío; `show_playback.py` usa ruta+tamaño+mtime+segmentos y existencia. Medir integridad bajo error/interrupción, reemplazo de origen de igual tamaño/mtime y revisiones del codec/preset. No borrar caches de usuario durante benchmark.
D. **No duplicar transcoding:** matriz de interdependencias para ver si previews de Show y Stage pueden compartir trabajo intermedio sin comprometer framing/efectos/timing. No inferir que deben unificarse: los outputs sirven funciones diferentes.
E. **Persistencia:** contrastar la funcionalidad actual de `ZuckerMixer/project_storage.py` y `core/project.py` con la hipótesis de recetas locales y sincronización; no inventar nuevo estándar JSON antes de conocer los contratos de proyecto y límites de seguridad.

## Orden de pruebas concreto
1. Describir y medir con un proyecto existente la ocupación actual por tipo de caché y export, usando `du`/inventario sin leer originales completos, con localización protegida y sin subir datos sensibles. Guardar tamaño (original/proxy), dimensiones, FPS, codec, bitrate y duración.
2. Reutilizar `render_ab.py` y `segment_costs.py` en entorno de referencia compatible; medir frío y caliente, CPU/RAM, I/O de disco, duración de procesamiento y validación de frames/audio.
3. A/B **solo sobre el módulo continuo Show** en laboratorio aislado: misma entrada y exactamente los mismos intervalos, `ultrafast` y `veryfast`. Preparar presets candidatos únicamente si ambas salidas reproducen/sincronizan bien y existe ventaja en función de coste ponderada.
4. Si las métricas justifican el cambio, introducirlo con tests de caché/integridad/persistencia en nuestra rama y un informe para revisión del autor. Nunca tratar una prueba FFmpeg externa como tiempo real de Montara.
5. Infraestructura: comparar opción 100% browser, trabajo local opcional, Oracle ARM gratuita, y GPU temporal, **incluyendo transferencia**. No activar infraestructura ni gastar créditos antes de conocer perfil de coste del motor existente.

## Matriz de aceptación sugerida (umbrales A DEFINIR con autor)
- Rendimiento: tiempo hasta primera previsualización, tiempo total transcodificación, tiempo de render real frente duración del vídeo, frío/caliente, tiempo de CPU y RAM pico.
- Almacenamiento: bytes por minuto de fuente, caché acumulada tras N revisiones, tamaño de proxies frente originales, frecuencia de reutilización.
- Calidad: A/V sync, drift, CFR/VFR, seeking a fotograma, framing 360, media errors, fiabilidad de reproducción navegador.
- Seguridad: originales inmutables, transacción completa, invalidación correcta, no pérdida de metadatos, preservación de fuente al cancelar o reiniciar.
- Resultado: mejora reproducible respecto al mismo commit original, sin regresiones en Stage/Push/Show/Mixer.

**Límite:** inspección parcial de código fuente de motores fijados. No equivale a certificación completa de arquitectura ni ejecución de CI. Priorizar análisis de `core/stages/export.py` y `core/stages/sync.py` en la siguiente fase.
