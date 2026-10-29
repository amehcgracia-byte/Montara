# SATURNO-00 — Revisión científico-técnica: información mínima para exportación fiel de Montara
**Fecha:** 2026-10-29 · **Tipo:** revisión focalizada de literatura, documentación normativa y auditoría estática del motor · **Estado:** investigación; NO se han ejecutado pruebas E2E ni modificado el motor. **Rama:** `fernando/continuacion-montara`.

## Resumen ejecutivo
**Pregunta de investigación:** para una edición multicámara de Montara, ¿qué información mínima debe estar presente en la máquina que genera el vídeo final, con qué garantías de integridad y fidelidad, y bajo qué condiciones compensa transferirla en lugar de ejecutar localmente?

**Hipótesis prioritaria (a comprobar):** la mayor oportunidad suele ser no transportar intervalos audiovisuales que no intervienen en el montaje, y transportar los intervalos necesarios **más su cierre de dependencias de decodificación**; reutilizar caché certificada en destino cuando realmente exista; mantener render local cuando el coste de empaquetar y enviar supere el ahorro remoto. *No hay ratios de reducción medidos para Montara*: es una hipótesis, no una promesa.

No existe reconstrucción arbitraria de medios ausentes a partir de un digest de longitud fija: un SHA-256 identifica/verifica contenido si hay una copia candidata, pero no lo codifica de manera reversible. Si el receptor ya posee bloques idénticos o material relacionado y una receta, pueden evitarse transferencias redundantes. A efectos prácticos, la deduplicación entre cámaras distintas y archivos H.264/H.265 comprimidos **no debe presuponerse**.

### Tres objetivos distintos de identidad
1. **Binaria:** SHA-256 del MP4 de salida idéntico, incluyendo metadata, configuración/mux y cualquier no determinismo. Exigencia más fuerte y a menudo innecesaria.
2. **Audiovisual decodificada:** mismo recuento, orden y contenido de fotogramas y muestras de audio (o cuantificación definida), sin exigir MP4 byte-idéntico. Requiere alinear timestamps, color, pixel formats, audio delay y tolerancias.
3. **Perceptual:** métrica con referencia alineada (VMAF/SSIM/PSNR según corresponda) y revisión humana; no equivale a igualdad de muestras ni a fidelidad absoluta. **No sustituir una exigencia por otra de forma silenciosa.**

## 1. Dependencias temporales, GOP, I/P/B, cortes y compressed-domain editing

### Evidencia científica y documental
- **Egawa (2000), _Editing MPEG2 video in compressed domain_**, NJIT. Estudia dos problemas: buffer del decodificador y extracción de segmentos que sean independientes de imágenes fuera del corte, preservando orden de decodificación/presentación: https://digitalcommons.njit.edu/theses/797/ . Aplicación conceptual: el intervalo visible solicitado no define necesariamente todos los paquetes necesarios para decodificarlo; codec específico de MPEG-2, NO prueba sobre H.264/H.265 concretos.
- **Kurceren y Chebil (ICASSP 2006), _Compressed Domain Video Editing_**: transformaciones y transiciones en dominio comprimido para familias de codecs predictivos; ahorros frente a operaciones decodificar-filtrar-recodificar, pero con limitaciones por dependencias y operación: https://dihana.cps.unizar.es/proceedings/ICASSP/2006/pdfs/0500441.pdf .
- **Thies, Hall y Amarasinghe (ACM Multimedia 2009), _Manipulating Lossless Video in the Compressed Domain_**: procesamiento de Apple Animation/LZ77 sin descomprimir todo; mediana 15× en su conjunto de 12 vídeos, **no extrapolable** a flujo H.264/HEVC lossy ni a 360 Lanczos: https://dspace.mit.edu/entities/publication/59e3c387-0766-4f8e-baaa-a6553e1d7339 .
- **FFmpeg, manual `-ss` y stream copy**: el seek suele aterrizar en el punto de búsqueda más cercano; al transcodificar puede decodificar y desechar pre-roll, mientras el copy preserva datos previos. `-c copy` omite la decodificación y no puede aplicar filtros: https://www.ffmpeg.org/ffmpeg.html y https://www.ffmpeg.org/ffmpeg-all.html .
- **FFmpeg segment muxer**: cortes precisos requieren keyframes alineados con límites esperados; hay restricciones de cadence y timestamp: https://ffmpeg.org/ffmpeg-formats.html .

### Implicación Montara
Definir por toma una unión de intervalos de salida referidos a fuente, con pre-roll de GOP o cierre real de dependencias, y margen temporal para movimiento, fades, transición, corrección y audio. El rango de *bytes* se calcula **después** de examinar contenedor, índices, cabeceras y referencias; no se infiere por proporción de duración. Los B-frames y orden PTS/DTS deben probarse. La proyección 360 es otra operación espacial, no reducible a cortar intervalos.

### Riesgo
Una selección de paquetes insuficiente puede decodificar negro, artefactos, temporalmente distinto o fallar en GOP abierto. Una selección demasiado generosa pierde el beneficio de transmisión. Re-encode de fragmentos para corregir cortes puede introducir pérdidas, cambiar hashes/píxeles y consumir mucho CPU.

## 2. Reducción de datos: selección, deduplicación, compresión, transferencia

**Orden de hipótesis a probar, en lugar de asumir una única técnica:**

A. **No enviar lo no usado**. Extraer de la receta intervalos de fuente; fusionar solapamientos, aplicar dependencias y medir bytes de origen incluidos. Las tomas simultáneas de cámaras distintas no son automáticamente redundancia binaria.

B. **No enviar lo que el receptor ya tiene**. Tridgell y Mackerras (1996), _The rsync algorithm_, identifican partes comunes entre ficheros de máquinas distintas y envían diferencias: https://openresearch-repository.anu.edu.au/items/15a1c428-0ad3-49d6-bb54-9238250cbbf0 . Especialmente útil en revisiones o transferencias interrumpidas, no cuando el receptor parte de cero y carece de referencias.

C. **Deduplicación por contenido (CDC)**. Xia et al. (USENIX ATC 2016), _FastCDC_, mejora la velocidad de delimitación de bloques a la vez que mantiene una tasa de deduplicación próxima a enfoques Rabin: https://www.usenix.org/conference/atc16/technical-sessions/presentation/xia . Aplicación: caché de objetos/rangos en destino o versiones ligeramente modificadas. **No equivale** a comprimir vídeo comprimido ni promete ahorro si los bytes cambian totalmente. Véase implementación práctica y tradeoffs de chunkers en Borg: https://borgbackup.readthedocs.io/en/master/internals/chunker.html .

D. **HTTP Range**, RFC 9110 §14: soporta petición de rangos de bytes en representaciones; puede responder 206, pero el soporte es opcional y se deben manejar validadores/estado 200/206/416: https://www.rfc-editor.org/rfc/rfc9110.html . Byte ranges no tienen por sí mismos semántica de GOP ni garantizan un MP4 independiente reproducible. Para fuentes **locales del usuario**, un servidor remoto no puede abrir sus rangos sin un agente/servicio autorizado o subida voluntaria.

E. **Recodificar representación** para red o proxy. Puede reducir bytes respecto a original en ciertos casos, pero consume CPU, puede aumentar tamaño si origen muy comprimido y puede alterar calidad del render. Nunca presentar proxy con pérdida como sustituto idéntico de fuente final.

### Techo informacional
Un hash de 256 bits no puede codificar reversiblemente todos los archivos posibles de muchos GB (principio de conteo). Los límites de información/entropía, introducidos por Shannon (1948), acotan compresión sin pérdida y requieren distinguir supuestos sobre la fuente: https://marco-dalai.unibs.it/teach/IT/shannon_1948.pdf . Con una copia en destino, una semilla compartida o un generador determinista, el mensaje podría ser corto **porque la información necesaria ya está en otro lado**.

## 3. Identidad, integridad y reconstrucción

- **Manifest de contenido**: cada fuente referencia ID estable, tamaño, fingerprint verificable, metadatos de codec, intervalos cerrados de decodificación, SHA-256 por fragmento y conjunto, mapeo PTS/DTS al intervalo original, versión de receta, FFmpeg/codec/color, activos, restricciones de licencia y temporales.
- **Verificación por pieza**: al recibir, verificar hashes de fragmentos y del conjunto; rechazar datos modificados y no aceptar una coincidencia de nombre/ruta como prueba. El checksum de muestra rápida sirve para *hint*, NO para probar identidad criptográfica del original.
- **Árboles de Merkle**: construcción de hash sobre hojas para validar partes y estructura (ejemplo formal RFC 6962, certificado de transparencia): https://www.rfc-editor.org/rfc/rfc6962.html . No implican reconstrucción de bytes ausentes, solo integridad/proofs.
- **Receta determinista ≠ salida byte-idéntica** entre máquinas: codec/build/preset, metadatos MP4, timestamps, hardware y procesamiento pueden introducir diferencias. Guardar parámetros/entorno y comparar objetivos independientes.
- **Privacidad**: hashes de grabaciones privadas pueden revelar igualdad de contenidos o permitir correlación; evitar publicarlos indiscriminadamente. No publicar rutas, nombres personales, audio privado, o manifest capaces de enumerar medios sensibles. Entitlements y cifrado con alcance de cliente, retención y revocación todavía requieren diseño.

## 4. Arquitectura local-remota: qué necesita píxeles y qué puede operar con recetas

**Taxonomía operativa provisional, a verificar con trazas del motor:**
| Operación | Datos imprescindibles | Dónde conviene a priori |
|---|---|---|
| Visualizar/cortar | proxy descodificable + asociación temporal a original + receta | navegador/local; remoto opcional |
| Planificar montaje, elegir cámaras, guardar decisiones | metadata temporal, decisiones y previews autorizados | local/cloud |
| Sincronía por audio, análisis musical | waveform/features o audio en el ejecutor | local, o cloud si hay consentimiento para transferir datos derivados |
| Render 1080p/4K con ajustes y color | píxeles reales del intervalo usado + pre-roll/dependencias + receta + overlay/fonts + motor | preferible local si fuentes locales; cloud solo con transferencia autorizada |
| Movimiento v360 | original o representación suficientemente fiel para cada fotograma necesario, geometría, trayectorias, filtros | local por defecto en diseño actual |
| Composición, concatenación, mux final | segmentos finales compatibles + audio master + metadatos/cadencia | donde residan segmentos y audio master |
| Reutilizar segment cache | bytes de segmento verificados + receta/versiones exactas | cerca de datos y cómputo |

**SMPTE (2020), Ening y Schragmann, _Editing in the Cloud_**, documenta modelos cloud/streaming proxy/híbridos, no demuestra rendimiento de Montara: https://journal.smpte.org/periodicals/SMPTE%20Motion%20Imaging%20Journal/129/2/16/ .

**Invariante de arquitectura:** ningún servidor puede exportar píxeles originales ausentes a partir de sus hashes. Proxies pueden permitir edición, pero resultado final fiel necesita medios fuente o segmentos finales previamente renderizados. **Local-first** es hipótesis de producto, no integración ya terminada. La propuesta de remoto selectivo exige decidir qué procesamiento se delega sin filtrar medios privados.

## 5. Contraste con ZuckerVideos / Montara

**Auditoría estática** sobre `amehcgracia-byte/zucker_videos` commit `60a7b7e9a39077b36f45057811abd6a833a168ef` y Montara rama `fernando/continuacion-montara` (no prueba end-to-end):
| Pieza existente | Prueba de código | Aplicabilidad |
|---|---|---|
| Plan de segmentos con fuentes/instantes | `core/stages/export.py` `_render_segment_job` ~2550 y `cached_segment_path` ~4155: `clip_start_sec`, `duration_sec`, `master_start_sec`, `source_path` | Base para inventario de intervalos necesarios; no demuestra export sin archivos completos |
| Caché de segmento por receta | `cached_segment_path` usa versiones, framing, spherical shot/motion, overlays, color y bitrate; `_segment_cache_stamp_matches` ~4245 verifica SHA completo | Ya hay reuso semántico local; no reimplementar otro cache global |
| Publicación y enlace | `_link_or_copy_segment` ~2991 hardlink si mismo FS y copia si no; `_publish_rendered_segment` usa rename atómico | Optimiza disco local, no equivale a dedup remoto |
| Recorte sin recodificación cuando procede | `_copy_trim_video` ~1493, usado en `_render_360_plan` ~1108 | Ya hay stream-copy para casos concretos; analizar tolerancias y exactitud antes de proponer fragmentación |
| Salida concat/audio directo | `_try_direct_concat_master_audio` ~3148 y fallback `_cadence_checked_joined_video` ~3131 | Evita pasos redundantes si pasa verificaciones; no reescribir |
| Prototipo local | `local_media/proxies.py`: caché por fuente + ffmpeg `libx264` CRF28, guarda JSON privado y público, `resolve_recipe` | Proxies locales experimentales; NO está integrado como render final y tamaño no siempre menor |
| Subida backend | `resumable_upload.py` en Montara | Ruta actual mueve originales a servidor; no es autorización automática de carpeta local |

**Lo que NO se ha demostrado en repo**: exportador de paquetes mínimos independientes para 360/cortes arbitrarios; equivalencia exacta de output tras empaquetar intervalos, traslados remotos por hash de archivo, estrategia de subir solo GOPs/bytes necesarios; complemento local productivo y seguro. Para descartarlo definitivamente habría que buscar también en todos los módulos del motor y tests; revisión actual no es auditoría exhaustiva del repo.

## Diseño experimental priorizado (no ejecutado)

| Prioridad | ID | Ensayo | Variables y falsación | Criterios |
|---|---|---|---|---|
| P0 | S01 | **Inventario pasivo de medios leídos por un render** sin alterar motor; plan congelado y media autorizada | volumen de clips usados vs no usados, duración cubierta por fuente, reads de disco si posible; falsar intuición de poca cobertura | listado completo sin omitir fuentes/activos; output baseline intacto |
| P0 | S02 | **Recorte dependiente de codec/GOP** de 3–5 fuentes sintéticas: all-I, GOP largo con B, HEVC, VFR, equirect 360 (más audio) | tamaño de paquetes, pre-roll, FPS/PTS/DTS, frames comparados; falsación si artefactos/omisiones | frame-exact o perceptual explícito, A/V sincronizado, ausencia de fallos |
| P0 | S03 | **Render desde solo el paquete mínimo** en QA aislada: negar acceso al resto de originales | ratio bytes, tiempo de extracción y render, calidad, hash de frames, capacidad de repetir; falsar si motor exige ficheros completos o rutas no resueltas | E2E export válido con mismo plan y calidad objetivo; cero rutas de fuente externas |
| P1 | S04 | **Transferencia selectiva vs total vs local** con ancho de banda simulado y medido | bytes útiles, tiempos empaquetado, upload, job, download, factura, RAM/disk | desigualdad E2E favorable robusta a variaciones |
| P1 | S05 | **Reutilización remota** con mismo archivo y versiones parcialmente cambiadas | bloques compartidos, huellas, transferencia delta vs hash cost | ahorro con verificación fuerte y sin filtración de información |
| P2 | S06 | **CPU/GPU** solo después de establecer inputs equivalentes | CPU vs GPU en mismos frames, quality matched, costes | mejora real de total, no solo del encoder |

**Matriz de estrés imprescindible:** 2/30/120 min, múltiples cámaras simultáneas, material con GOP 1/120/240, B-frames, codec H264/HEVC, 360 con motion, VFR y audio/latencias, contenedor MP4/MOV, cambios de color y overlays. Empezar sintético pequeño, luego un fixture de concierto autorizado. No extrapolar ratios a 80 GB sin observación.

### Métrica crítica
`total_remote = selection + package + transfer + queue + startup + remote_render + verify + download`; `total_local = local_render + local_verify`. Registrar también bytes del paquete / bytes originales totales, pico de disco, energía no necesaria inicialmente, calidad y fallos. El costo de cada actividad debe recogerse por separado.

## Qué hace falta antes de programar SATURNO-01
1. José Manuel debe poder revisar protocolo y este informe. No hay obligación de aceptar una arquitectura.
2. Elegir **un fixture congelado** del repo (p.ej. `tests/fixtures/much-to-me`) y un plan con SHA, sin alterar derechos de media.
3. Comprobar que el plan serializado del motor permite inventariar fuentes, y diseñar script de **solo lectura** para S01. No inyectar patches en engine.
4. Definir política de calidad: ¿idéntico MP4 o idénticos fotogramas + audio? No decidirlo implícitamente.
5. Publicar resultados con una tabla: hecho ejecutado / evidencia del código / inferencia / pendiente.

## Fuentes primarias y límites
- Shannon, C. E. (1948), *A Mathematical Theory of Communication*: https://marco-dalai.unibs.it/teach/IT/shannon_1948.pdf
- Tridgell & Mackerras (1996), *The rsync algorithm*: https://openresearch-repository.anu.edu.au/items/15a1c428-0ad3-49d6-bb54-9238250cbbf0
- Egawa (2000), *Editing MPEG2 video in compressed domain*: https://digitalcommons.njit.edu/theses/797/
- Kurceren & Chebil (2006), *Compressed Domain Video Editing*: https://dihana.cps.unizar.es/proceedings/ICASSP/2006/pdfs/0500441.pdf
- Thies et al. (2009), *Manipulating Lossless Video in the Compressed Domain*: https://dspace.mit.edu/entities/publication/59e3c387-0766-4f8e-baaa-a6553e1d7339
- Xia et al. (2016), *FastCDC*: https://www.usenix.org/conference/atc16/technical-sessions/presentation/xia
- Ening & Schragmann (2020), *Editing in the Cloud*: https://journal.smpte.org/periodicals/SMPTE%20Motion%20Imaging%20Journal/129/2/16/
- RFC 9110 HTTP Semantics §14 range requests: https://www.rfc-editor.org/rfc/rfc9110.html
- RFC 6962 Certificate Transparency §2.1 Merkle trees: https://www.rfc-editor.org/rfc/rfc6962.html
- FFmpeg documentation: https://www.ffmpeg.org/ffmpeg.html , https://www.ffmpeg.org/ffmpeg-all.html , https://ffmpeg.org/ffmpeg-formats.html
- Borg chunker documentation: https://borgbackup.readthedocs.io/en/master/internals/chunker.html

**Cautela bibliográfica:** revisión dirigida, **no revisión sistemática exhaustiva/PRISMA**. No se han ejecutado ni replicado experimentos de los papers; los resultados publicados solo justifican hipótesis, no predicen rendimiento de Montara. La metodología y la versión exacta de cada paper requieren lectura integral para diseñar implementación.
