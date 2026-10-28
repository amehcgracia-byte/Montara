# MONTARA — Deep dive focalizado A+C: identidad de medios y caché al cambiar de ejecutor
2026-10-28. Auditoría estática basada en `zucker_videos` pin `60a7b7e9a39077b36f45057811abd6a833a168ef` y Montara main vigente. No render nuevo ni modificación del motor. **Candidato de arquitectura, no parche de producción.**

## Resultado prioritario
El motor YA tiene un caché global por segmentos de recetas, con attestation SHA-256 y versiones explícitas; ya omite generación de proxy completo 360 para movimiento original y evita transcodificar originales H264 CFR SDR compatibles. **No duplicar esas funciones.**

El cuello de arquitectura para A+C es **identidad portable de fuentes distinta de ruta física del ejecutor**:
- `core/normalization.py:261-271`: `cache_key_for_signature` usa `migrated_identity(path)` o ruta absoluta, tamaño, mtime y `NORMALIZATION_VERSION=6`.
- `core/storage.py:105-126`: hay soporte explícito de identidad antigua en *migraciones verificadas* (manifest con firma tamaño/mtime), por tanto **no es verdad que toda reubicación rompa cachés**; pero no es resolución genérica browser→Linux.
- `core/stages/export.py:4150-4210`: `cached_segment_path` incluye `source['cache_key']` **y** `source['source_path']`, ajustes visuales, tiempos, movimiento, versions, etc. Cambiar la ruta de una fuente puede producir un **nuevo key de segmento** aun cuando los bytes no cambien y la reconstrucción sea idéntica. Mantiene seguridad de caché, pero sacrifica potencial reutilización entre ejecutores.
- `core/stages/export.py:4212-4260`: cache sidecars con receta y SHA-256 del fichero; buena base de integridad. Modificar claves sin preservar attestation y versionado sería regresión.
- `core/project.py` y `sync.py`: rutas absolutas y clip IDs dependen de rutas; NO reemplazar a ciegas `project.json`, identidad de cámaras, offsets, timeline o `source_path`.
- `core/normalization.py:99-125`: bypass de proxy H264 CFR <=1080p existente. `core/stages/export.py:2128-2154`: bypass proxy de esfera en export movimiento original existente.

## Hipótesis técnica (alto impacto potencial para A+C)
Crear una **capa externa de resolución de fuentes** en Montara que conserve IDs y contrato Zucker; mantener `project.json` vigente y ofrecer `source_id` lógico -> local/browser/media staging/remoto según ejecutor. `original` es fuente de verdad, manifest claro de hash validado, y `source_path` real se resuelve *antes* de invocar engine. Una caché inter-ejecutor compartida NO se promete; se estudia en etapa posterior con operación/versión/codec/contexto completos. El primer objetivo es poder retomar un mismo montaje sin rehacer edición al mover los medios entre Windows y Linux, no compartir hashes globales sin controles.

## Secuencia mínima, sin sobreingeniería
1. **Inventario concreto de consumidores:** `project.py`, `sync.py`, `edit.py`, `export.py`, `show_playback.py`, `mixer_adapter`, endpoints de Montara. Confirmar dónde se congela `clip_id` o ruta después de ingestión.
2. **Prueba de portabilidad offline reproducible:** proyecto de dos cámaras+máster sintéticos, guardar receta, duplicar fuentes en árbol A/B con rutas distintas, intentar reanudar mediante un resolver solo de Montara, medir identidad de clips, offsets, fuentes de render, caché válida/invalidada y salida de frames/audio. No construir navegador paralelo ni reescribir motor.
3. **Primera implementación (si lo anterior demuestra viabilidad):** manifiesto de staging de medios privado, mapeo explícito source ID->ruta destino, verificación contenido y acceso, rechazo de rutas fuera de roots, preserving original ID and all time transforms; no subir todos los originales por defecto.
4. **Pruebas de aprobación:** mover directorio manteniendo bytes/mtime y cambiando mtime; duplicados, homónimos distintos, fuente perdida/reconectada, 360, VFR, Windows drive, Linux path, cancelación, identidad de dos cámaras, hash y version de receta, permisos usuario. Nunca confiar en nombre/tamaño solamente.
5. Solo entonces experimental cloud/RunPod: cronometrar transferencia explícita + cola + proceso + descarga, con mismo edit plan y versión del motor.

## Oportunidades científicas — prioridades revisadas
- **N.º 1 (producto):** identidad de artefactos/cachés content+action, según principios de *content-addressable storage* (inspiración técnica, no instalar Bazel). Aquí el problema está confirmado por código; experimento de portabilidad primero.
- **N.º 2 (motor):** estrategia de bitrate de proxies no conformes: la normalización usa bitrate objetivo fijo y fallback H264 SW; probar *solo* archivos low-bitrate VFR/rotados o 360 representativos y comprobar si crece el proxy y si influye en uso real. Probar misma exactitud de seek/audio/color antes de tocar calidad. No deducir resultados de JUPITER local.
- **N.º 3 (360):** algoritmos adaptativos de tiles/viewport útiles principalmente para *streaming*, NO beneficio automáticamente extrapolable al render 360 a 1080p. Solo experimentar si un perfil nuevo muestra decodificación/reproyección como cuello principal. El motor ya omite full proxies para casos de movimiento original. No introducir tile stack por moda.
- **N.º 4 (GPU):** esperar benchmark real con copia CPU/GPU y transferencia de fuentes. No contratar ni anticipar ahorro.

## Criterio de propuesta sustancial
No es un "parche de optimización" hasta pasar E2E y medir. Cambio ambicioso prioritario: conectar un adaptador de identidad portable a la API Montara con compatibilidad Zucker. Hasta entonces, documentar el punto de ruptura y evitar contaminar los pins actuales.

## Fuentes base
Código `amehcgracia-byte/zucker_videos` pin `60a7b7e9`: `core/normalization.py:99-125,261-271`, `core/storage.py:105-126`, `core/stages/export.py:4150-4260`, `core/stages/export.py:2128-2154`. Montara `docs/INTEGRACION_FER_2026-10-28.md` reconoce que browser proxy UI/export final no están integrados. Artículos viewport 360 documentados en `docs/AUDIT_SPHERICAL_AND_PAPERS_2026-10-28.md`; evidencias físicas de rendimiento aún faltan.
