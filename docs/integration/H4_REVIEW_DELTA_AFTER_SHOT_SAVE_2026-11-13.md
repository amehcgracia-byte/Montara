# H4 / Chema original — review de miniaturas tras guardar una toma

Fecha: 2026-11-13 · Rama `fernando/chema-native-owner` · **Diagnóstico de lectura; SIN parche ni despliegue de Engine**.

## Síntoma informado en prueba humana

Tras acceder a Footage y editar una toma, al guardar el editor vuelve a esperar la galería de miniaturas completa. Esto impone una segunda espera, aunque el usuario solo haya cambiado un fotograma. El render posterior informa que Companion no está conectado porque el MSIX `0.6.11.1` distribuía solo la bandeja y no el servicio local; no confundir ambas incidencias.

## Evidencia concreta del código anclado de Chema

1. `web/cut-editor.js`, `refreshMusicReview(index)` hace `refreshFrames(true,index)`, seguido de `pollFrames()` si hay pendientes.
2. `web/montara.js`, `updateFrames(first,index)` llama `/wizard/review?render=1&shot=<index>`, pero representa **todos** los `items`, computa pendientes globales y puede programar polls globales.
3. Engine pinned `engine/server/api.py`, GET `/api/v1/wizard/review`: usa `review_items(project, render_missing=False)`; en modo `render=1`, construye `pending` con **todos** los elementos missing. El parámetro `shot` solo se transmite a `review_previews.PREFETCH.start(..., priority=shot, indices=missing)`: prioridad, **NO** scope de render. Así una edición local puede reprogramar generación de toda la galería cuando otras miniaturas estén invalidadas.
4. `engine/core/shot_review.py`, `_thumbnail_asset` usa key `sha256(source,source_mtime,timestamp,pose)` y nombre `shot-<index>-<hash>.jpg`. En principio los elementos realmente inalterados deberían conservar URL/hash, pero transiciones/continuidad `continuous_views(... preserve_authored=stage)` o alguna mutación adicional de plan pueden modificar varios elementos. **No se ha confirmado aún qué porcentaje se invalida** con el proyecto concreto.
5. H4 `urano/native_owner_browser_bridge.js`, `decorateReview` hace `await Promise.all(result.items.map(... reviewBlob(...)))`: la petición entera queda esperando las descargas privadas de **todas** las miniaturas contenidas en la respuesta. `reviewBlobs` sí cachea por URL, pero una URL nueva obliga a recuperar de nuevo el JPEG antes de devolver el JSON.

## Contrato de la corrección deseada

- Edición de índice `i`: determinar del plan cuál(es) firmas de foto han cambiado realmente frente a snapshot anterior, sin asumir que únicamente `i` cambia si la continuidad visual afecta a tomas vecinas.
- Mantener todos los JPEG reutilizables, etiquetas, frames y previsualizaciones sin reiniciarlos al guardar.
- Para `shot=i`, priorizar `i` **y restringir el scheduling** de trabajo extra al conjunto de índices invalidados, en vez de recrear `indices=missing` global. El fondo inicial de preparación de galería puede seguir preparándose durante la edición, pero sin bloqueo del guardado.
- En H4, desacoplar la respuesta de revisión de la descarga secuencial/bloqueante de 123 imágenes. Cargar las nuevas miniaturas de manera progresiva, conservando autenticación Owner y evitando mostrar imágenes obsoletas como si fueran actuales.
- Preservar la fuente original de Chema y el Engine pinned en producción hasta que las pruebas (al menos 123 segmentos, 1/2/3 ediciones y una edición que cambia continuidad) demuestren el comportamiento. No fusionar `main` antes de validar.
- Evidencia de aceptación: `GET review(render=1&shot=i)` no agenda `n-1` miniaturas ya válidas; cero redescargas para URLs invariantes; solo nuevas URLs cuando cambie realmente su contenido; revisión visible sin bloquear toda la galería; vídeo final fiel al plan actualizado.

## Prioridad

1. Restablecer Companion real en Windows y conseguir un MP4.
2. Corregir invalidación/scheduling de miniaturas en una rama reproducible, pruebas de regresión y revisión con Chema.
3. Integración ordenada a `main`, no tocar los submódulos pinned ni desplegar motor no validado.

## Actualizador Windows

El botón `Buscar actualizaciones` del MSIX **instalado** `0.6.11.1` es informativo; no publica ni descarga `0.6.12.0`. La compilación Windows PASS del siguiente MSIX no significa actualización automática. Cada firma efímera de desarrollo impide una política estable de actualización; será necesario certificado persistente bajo custodia y lanzamiento verificado de un paquete compatible con Windows. Evitar reinstalaciones improvisadas o bypass de Defender.
