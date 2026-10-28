# Arquitectura híbrida — auditoría de contrato de proyectos, normalización y portabilidad (2026-10-28)

**Alcance y rigor:** examen estático del submódulo ZuckerVideos fijado por Montara main en `60a7b7e9a39077b36f45057811abd6a833a168ef`, y de los datos históricos aportados en PR #6 `15aa4d6`. No se ejecutaron renders, benchmarks ni tests; no se cambió el motor. Guardado únicamente en `fernando/continuacion-montara`.

## Hechos comprobados en código

### A. Proyecto ya versionado, transaccional y con etapas incrementales
- `core/project.py:96-107`: `schema_version: 1`, `inputs` (master/songs/videos), `stages` (ingest/sync/cut/edit/export), `settings`. **No inventar otro esquema de proyecto**.
- `core/project.py:111-145`: carpetas proyecto separadas `cache/`, `artifacts/`, `exports/`, JSON guardado atómicamente con `fsync` y `os.replace` (`:275-290`).
- `core/stages/export.py:374-389`: huella de exportación incorpora huella de `edit`, ajustes y versiones de recetas, permite invalidación sensible al cambio.
- `core/project.py:28-39` guarda **ruta absoluta** resuelta y tamaño/mtime de fuente. `core/stages/sync.py:194-201` identifica el clip usando esa ruta; `:437-500` incluye `source_path` y firma en el resultado. **Implicación**: un paquete de instrucciones que contenga una ruta Windows no se puede ejecutar directamente en una VM Linux. Propuesta de investigación: un adaptador de recursos (source_id/locator) que preserve el esquema y resuelva rutas localmente después de autorización/copia, nunca reescritura masiva de `project.json` sin test.
- Identidad de contenido ya se utiliza en varias zonas (cache keys y override content identity). No extrapolar que todas las rutas dependen exclusivamente de la ruta absoluta; inspeccionar consumidores antes de diseñar el adaptador.

### B. Transcodificación no siempre necesaria; umbral ya implementado
- `core/normalization.py:99-123`: **reutiliza el original** sin proxy si `proxy_transcode_compliant` es verdadero; registra `proxy_skipped=True`, motivo.
- `:538-556`: exige H.264 CFR SDR 8-bit, rotación cero, sin proyección, dimensiones <=1920x1080. En ese caso no necesita transcodificar, con independencia del bitrate.
- Para vídeos no compatibles, `:559-636` crea H.264 con `-b:v 2500k -maxrate 3500k -bufsize 7000k`, AAC estéreo 48k 192k, CFR; intenta VideoToolbox y luego x264 si falla (`:151-175`). Esta estrategia de **bitrate fijo** es intencionadamente simple: en un original muy comprimido o un uso solo de previsualización puede elevar los bytes sin garantía de que mejore calidad perceptual. El `jupiter` proxy ultrafast/CRF28 es otro pipeline y NO prueba un fallo en esta ruta.
- `core/normalization.py:27-46`: límites de proxy de 1280x720, política global de caché, presupuesto segmento 40 GiB y 14 días. Cualquier política adaptativa tiene que respetar las cachés y la fiabilidad de CFR, audio y metadatos.

### C. Portabilidad y coste
- `core/stages/export.py:696-718` condiciona solapamiento de verificación al menos a 16GiB físicos y 2GiB disponibles; en Linux consulta `/proc/meminfo`. **Una VM Oracle 12 GiB no tendrá ese solapamiento** con la política actual. No es por sí mismo un error: es una degradación premeditada para reducir presión de memoria.
- `core/normalization.py:559-583`: VideoToolbox sólo existe en ecosistema Apple, y el mensaje de ausencia de ffmpeg aconseja `brew`. El fallback de codificación software existe, pero debe validarse su comportamiento en Linux ARM64, Windows y contenedores.
- `core/stages/sync.py:437-500`: secuencia existente onset → spectral flux → HPSS percussive, sólo usa etapas más costosas cuando confianza falla; `verify_sync_stability` compara consistencia temporal. No introducir Chromaprint ni IA genérica sin una falsación concreta de este diseño.
- `core/stages/export.py:2128-2154`: evita generar proxy esférico global para tomas finales de movimiento nativo compatibles; en draft usa proxy deliberadamente. El caso histórico 866s sin consumidor ya tiene un arreglo visible; una regresión basta.

## Candidatos de investigación priorizados — NO cambios de implementación

1. **Modelo de recursos independiente de ubicación (P1):** usar identificadores estables de medios y un manifiesto para re-vincular fuentes al ejecutor, con adaptador al actual `Project`. Diseñar matriz: original local accesible a browser, executor local opcional, backend remoto con subida explícita. Preservar integridad, tiempos, tipos de cámara y compatibilidad. Benchmark: mover mismo proyecto entre rutas físicas/OS y verificar mismo plan y render cuando los inputs son idénticos. No prometer remoto sin transferir medios.
2. **Proxy condicionado al contenido y finalidad (P1 investigación):** probar solo materiales no conformes, incluidas fuentes de bitrate muy bajo, contra configuración 2500k fija. A/B con tamaño original/proxy, tiempo de preparación, seek, calidad y uso de downstream; política de bypass solo si los consumidores aceptan formato y las verificaciones pasan. Nunca reducir calidad por ahorrar disco de forma inadvertida.
3. **Planificación bajo RAM real (P1):** comparar 1 worker CPU Linux ARM y configuraciones actuales en equipo de referencia; `/proc/meminfo` no reemplaza medición de límite de cgroup/VM bajo carga. Registrar máximo RSS de árbol, sobrecarga, swap, tiempo final y cola antes de decidir capacidad Oracle Free.
4. **Separación de etapa GPU/CPU (P2):** construir matriz decode→normalización→sincronía→segmentos→reproyección→encode→verificación. Export completo debe mantener mismos límites, color, audio y calidad; benchmark end-to-end incluye transferencias al remoto, no sólo frames/seg de encode.
5. **Sincronización robusta (P3 condicional):** método actual ya multirrepresentación y verifica estabilidad. Sólo papers/fingerprinting/DTW si muestras reales demuestran drift, falsas coincidencias o costes excesivos.

## Cómo aprovechar investigación existente sin sobreingeniería
- Adoptar **principios de manifests y content-addressed storage** (Bazel/DVC), no introducir Bazel/DVC en pipeline sin razón. Versionar transformaciones en caché y evitar recomputaciones innecesarias.
- Evaluar enfoque **per-title/content-adaptive encoding** primero con decisiones simples a partir de `ffprobe` y mediciones A/B; sistemas ML sólo si métodos sencillos no llegan.
- Trabajos de **360 viewport-adaptive/tiling** pueden orientar reproducción remota y proxies sobre regiones de interés; la exportación final requiere precisión global de cámara y encuadre.
- GPU: gestionar datos residentes y costes de host↔GPU; FFmpeg no garantiza rendimiento sólo por activar hwaccel.

## Matriz de aceptación del próximo experimento
Medidas obligatorias: duración y bytes originales, fps/codec/HDR/proyección, tamaño proxy, tiempo frío/caliente, RAM pico, bytes escritos, CPU, latencia hasta primer preview, discontinuidades/seeking y A/V sync. Mismas fuentes y segmentos, orden A/B equilibrado, salida original intacta, errores conservados. No interpolar valores N/D del histórico.

## Decisión preliminar
**Preservar esquema v1 de project y algoritmo existente de sincronización; no tocar main.** Investigar primero un adaptador de localización de medios y política de normalización basada en el consumo y contenido. La VM y la GPU se decidirán sólo después de perfilado: 12GiB Oracle Always Free difiere de Mac de 32GiB y no se puede inferir rendimiento.
