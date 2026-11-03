# JÚPITER — EX-14H-14A · Fidelidad de tres escenarios 360 en Stage real

**Fecha:** 2026-11-03. **Estado:** 3/3 escenarios PASS en equivalencia preencoder A/B, 6/6 exportaciones válidas. **Laboratorio:** VM GCP Linux 8 vCPU, checkout aislado del editor `0f9ec03`; flags opt-in EX07/EX13, sin cambios productivos.

## Método

Un vídeo HEVC equirectangular original 3840×1920, 2 s (60 cuadros, 30 fps), Reel horizontal 1920×1080, audio máster de fixture. Cada uno de tres encuadres se exportó en Stage dos veces: A (fast_wrap=false, smart_unwrap=false) y B (ambas true). Instrumentación interceptó `reproject_maps` y `cv2.remap` para SHA256 de los mapas, entrada BGR y fotograma BGR reproyectado previo a H.264. Cada proyecto y caché aislados; salida verificada con 60 cuadros y audio PCM. Carpetas temporales eliminadas.

## Resultados

| Escenario | Parámetros representativos | Mapas A/B por export | Frames HEVC entrada idénticos | Frames preencoder idénticos | Mapas bit-exact | Audio PCM |
|---|---|---:|---:|---:|---|---|
| fixed_hold | yaw 0°, pitch 0°, fov 95°, rate 0 | 1 / 1 | 60/60 | 60/60 | Sí | Exacto |
| moving_pan | yaw 180°, pitch -30°, fov 100°, rate 9°/s | 60 / 60 | 60/60 | 60/60 | Sí | Exacto |
| seam_pole | yaw 179.4°, pitch +68°, fov 145°, pan_right | 60 / 60 | 60/60 | 60/60 | Sí | Exacto |

**Total:** 180 comparaciones de fotogramas A/B, 121 pares de mapas equivalentes. En los tres escenarios, decoded input, mapas y píxeles preencoder fueron idénticos en A/B; audio PCM idéntico en todas las seis exportaciones, SHA256 `e6215d07a7acf3fb6292e4a0c32c05d93769d9bf61bff60ef274b9d101ab16e3`.

Map SHA de cada escenario A/B: fijo `4488d28957ca567da46b4eadb12f174202691757ac064e0707c32c20d752489d`; movimiento `c55ccce1c680d98c0df909505d00b450ca24786fba593f21061074a59059c230`; seam/pole `ac2f4fb1191b892a41bfdf19bcf503d2c500a4218eae0530ea3a69481ae389a4`.

## Tiempos instrumentados, SOLO ORIENTATIVOS

| Escenario | A Stage s | B Stage s | A segmento s | B segmento s |
|---|---:|---:|---:|---:|
| fixed_hold | 5.442 | 5.335 | 4.130 | 4.046 |
| moving_pan | 7.822 | 7.097 | 6.428 | 5.684 |
| seam_pole | 7.778 | 7.028 | 6.405 | 5.645 |

**NO cuantificar mejora a partir de esta tabla**: hashing de varios buffers añade carga y solo una repetición por configuración. EX14H11F ABBA no instrumentado es la referencia actual de rendimiento: 11.37% de reducción de wall Stage en una toma dinámica de 2 s; EX14H12B indica mapas −36.5% en una comparación aislada.

## Alcance y límites

- Equivalencia numérica BGR previa al codificador, **no** igualdad MP4 ni imagen final codificada, ya que Stage cambia ligeramente también entre dos A; EX14H12C estableció que la diferencia ocurre tras remap.
- El plano seam/pole comprueba fidelidad respecto al algoritmo original, **no certifica calidad perceptiva**, continuidad visible en costura ni calidad de encuadre.
- No constituye cobertura exhaustiva de geometrías, proyecciones, duración, codecs, hardware, macOS Metal, Windows, GPU o concurrencia.
- La cámara fija tuvo 1 solo mapa por exportación, lo que explica que optimizar la generación de mapas beneficie principalmente a escenas con poses cambiantes.
- Las tres configuraciones usan el mismo tramo de origen HEVC 840–842 s y solo duran 60 frames: variación de contenido real sigue pendiente.

## Próximo gate recomendado EX-14H-14B

Comprobar múltiples ventanas de la fuente original y segmentos de mayor duración (p. ej., 10–20 s) manteniendo audio/mux válidos y marco reproducible, sin cargar indiscriminadamente el disco de 19 GiB libres. Separar fase de **fidelidad** instrumentada de fase de **rendimiento** sin instrumentación; si se comparan distintos tramos, controlar y anotar GOP/seek/decoder para no atribuir errores a la reproyección. Probar escenarios nuevos de proyección y wrap, y luego remitir revisión selectiva a Chema por PR del editor. Priorizar integridad de datos y no modificar producción.
