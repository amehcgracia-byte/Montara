# MONTARA — Mapa Stage / Push / Show, conservación y consumo VM (2026-11-11)

## Alcance y fuente
Análisis de solo lectura de `fix/jm-native-video-save-project-recovery-20261110` en GitHub y medición `du` en VM `montara-test`. No se atribuye autoría individual: parte de la tecnología de Companion, proxies y segmentos procede de contribuciones previas de Fernando. No se ha cambiado main, servicios, proyectos, privacidad ni limpieza. La próxima integración se hará desde el gran main de Chema cuando se publique y después de comparar dependencias.

## Decisiones de experiencia aportadas por Fernando
- Mantener la portada auténtica de Chema (logo sobre negro, elección Música/Vídeo) tras landing y Google. Entrar en Stage/Push/Show sin una pantalla técnica intermedia.
- Tratar inicialmente los proyectos Stage, Push y Show como ámbitos diferentes; cada uno tiene selector contextual de propios proyectos, continuar, crear, cargar y renombrar dentro de su editor, sin dashboard obligatorio.
- Optimizar el número de pasos. Preguntar antes de modificar el flujo de Chema; el diseño no es una aprobación definitiva.
- No convertir automáticamente los 14 días de `footage-memory.js` en la caducidad de proyectos. No activar limpieza de medios sin evaluación de requisitos, política de conservación y aprobación.
- Conservar optimizaciones anticipadas, solapamiento de tareas, proxies, identificación y render con originales locales.

## Mapa de operaciones real: Stage (plataforma interna `youtube`)
1. UI: `web/index.html` selección Music/Video y `data-platform=youtube`; `web/montara.js` activa Footage. `footageMemory.handlesFromDrop/pick` obtiene handles en Chrome/Edge, `addFiles` recuerda metadatos y dispara `upload` por archivo sin esperar a que se terminen todos.
2. Companion: `web/companion.js` detecta localhost 47820, `POST /locate` con nombre/tamaño/fingerprint de extremos, `POST /proxies` devuelve trabajo; sondeo `GET /proxies/{id}`, lectura `GET /proxies/{id}/file`; el navegador sube medios reducidos mediante `/montara/uploads`. El original permanece local salvo fallback de consentimiento expreso. Proxies tienen claves e invalidación por `VIDEO_PROXY_RECIPE=3`.
3. Registro: `registerProject` `POST /wizard/projects/new`, `POST /wizard/draft` y asigna `state.projectId`; si está Companion, puede seleccionar carpeta LOCAL mediante `POST /projects`. **Son identidades de proyecto distintas** de Owner UUID y de Push pack ID.
4. Decisiones de ramas: Stage con varias pistas de audio/preview largo usa `openFullSession(true)`; audio solo puede usar mixer o full session. No imponer un único pipeline.
5. Preparación: `prepareStageSources` hace `/settings/fillers`, `/wizard/prepare`, consulta `/artifacts/sync`, evalúa fuentes por evidencia de audio y excluye cámaras silenciosas/no verificadas del render, sin borrarlas de la biblioteca. `/wizard/draft` y `/wizard/start` inician trabajo real. `startPolling` observa evolución.
6. Edición: planos, cámaras 360, cortes, timeline, `/wizard/review/render` y `/wizard/compose`; exportación nativa usa `/edit/native-recipe?project_id=` con `engine` obligatorio igual a `companion.local_video.engine`, comprobación hasta dos originales paralelos y `POST /video-renders` Companion, `GET /video-renders/{id}`, guardado a carpeta local. No descargar/cargar originales enteros sistemáticamente.
7. Preservar: procesamiento al subir, cache hit, recuperación de handles, sync por audio, trabajo pendiente/cancelación, paso de audio largo a sesión y pruebas de versión Engine/Companion.

## Mapa de operaciones real: Push (plataforma interna `reel`)
- El editor incluye dos itinerarios: el normal `reel` usando wizard/cámaras/edición, y la modalidad **Four reels** activada en `web/push-pack.js` (no tratarlos como un único código).
- Four reels: la interfaz elige **un** vídeo subido o URL; `POST /montara/push/packs` devuelve pack ID UUID32, guarda `PushPacks/<id>/pack.json`, inicia hilo de preparación. Reutiliza fuente local permitida, descarga URL con yt-dlp cuando procede, crea `preview.mp4`, analiza imagen/audio/ritmo, propone cuatro regiones, puede transcribir letra con Whisper en background.
- `GET /montara/push/packs/<id>` y `/latest` permiten sondeo/último pack; edición PATCH de cortes, layout y captions por reel; alineación de palabras `POST /reels/<id>/align` lanza hilo; `POST /export` encola y renderiza reels seleccionados con lock, separados por reel; `GET /reels/<id>/file` entrega MP4.
- Recuperación: sessionStorage recuerda pack en navegador y `/latest` busca pack listo; ahora es catálogo global de un data_root. Riesgo claro de fuga entre propietarios si se expone sin aislamiento. **No asumir que un pack es proyecto Stage.**
- Push requiere control owner/project también en `/montara/push/packs`, que no pertenece a `/api/v1` del wizard; la integración debe revisar todos sus endpoints, no solo wizard.
- Conservación: `pack.json` pequeño frente a `download.*`, `preview.mp4`, `analysis.wav`, transcripción y `reel-*.mp4`; separar persistente de regenerable.

## Mapa de operaciones real: Show (plataforma interna `show`)
- `openShowSetup` en `web/montara.js`: selección de vídeo/ejemplos mediante drop; puede reabrir el último proyecto si `/wizard/status`, `/project` y `/show/scenes` coinciden con show.
- Tipo de montaje: fast/gamer, normal/influencer, storytelling, podcast; `prepareShowSources` y `POST /wizard/start` con `platform:show`, `show_style`, revisión y opciones; `startPolling` sigue ingest/análisis.
- Revisión: `GET /show/scenes`, `POST /montara/show/direction`, `GET /montara/show/editor`; `web/show-editor.js` modifica escenas, clips, overlays y cortes con rutas `/show/... ` y `/montara/show/cuts`, conservando edición sin rerender en cada interacción.
- Preview por escena: `POST /montara/show/playback/<scene_id>` crea render en `threading.Thread`; `GET /montara/show/playback/jobs/<key>` consulta resultado; `GET /montara/show/playback/<key>.mp4` devuelve vídeo; export final `/show/review/render`.
- Show usa `app.config['MONTARA_EDITOR_PROJECT']` a través de `show_editor_state.py`, más rutas globales y accesos a assets. Debe resolverse por Engine privado y proyecto autenticado, sin variables compartidas en una app multiusuario global.

## Sistemas de recuperación diferentes (conservar y enlazar, no duplicar)
- Owner FER: Google -> owner_id -> project_uuid; autorización antes de abrir datos/jobs.
- JM wizard: `project_id` y ruta `project.json`; `app.py` restaura `last_project_path`.
- JM `recovery.py`: `/montara/recovery/latest` escoge último trabajo no vacío de `Projects` y `Sessions`.
- Push: UUID pack, `pack.json`, sessionStorage y `/latest`.
- Companion local: carpeta elegida y `montara-project.json` más referencias guardadas, independiente de los anteriores.
- Browser `footage-memory.js`: IndexedDB `montara-footage`, handles/metadata y TTL 14 días solo de referencias browser, NO de proyecto servidor. Hoy filtra por plataforma, no owner UUID ni project UUID; precisa separación de navegador si se usan varias cuentas.
- Propuesta: Owner UUID canónico, tipo de proyecto Stage/Push/Show, referencias explícitas a IDs JM internos/pack y destino Companion; no replicar media completo en Owner. Nuevo proyecto al empezar trabajo efectivo, sin interposición de pantalla; selector en barra de cada mundo. Pendiente validación de UX por Fernando.

## Medición real: uso VM por directorio Linux (du, 11 noviembre 2026)
- `/home/jm`: ~22G; `/home/jm/montara-data`: **16G** (Projects 7.8G, Uploads 5.1G, Cache 1.5G, .cold-upload-quarantine 1.1G, PushPacks 108M, Runtime 109M, demás pequeños); `/home/jm/montara`: 2.9G y backup shot fixes 1.9G. **No limpiar**, trabajo JM vivo.
- `/home/fer`: ~13G, de los cuales `lab-clips` 6.3G, `montara-jupiter` 2.1G, `.cache` 2.1G, `montara-data` 573M. La ocupación no equivale a datos activos del editor.
- `/home/fgardel00`: ~11G, con múltiples laboratorios; `montara-personal-beta-data` 594M, incluyendo Cache 485M (WhisperModels ~464M), Runtime 109M y Projects ~416K. Owner portal y pruebas no equivalen a proyectos pesados de usuario.
- `/home/montara-main`: ~4.4G, data 2.4G (Uploads 1.2G, Projects 609M, Cache 572M, Runtime 109M); instalación compartida, **no adjudicar exclusivamente a Chema o Fernando**.
- `/opt/montara`: ~1.4G, infraestructura compartida broker/bundle. VM raíz última lectura 96G, 56G usados y 41G libres (aproximados), valores cambian.
- **Precaución:** los números `du` agrupan directorios y no contabilizan por separado hardlinks/compartición o costes por proyecto individual; el total redondeado no debe sumarse ingenuamente con df. No usar ejemplos diminutos para estimar un usuario productivo.

## Conservación y rendimiento: preguntas que deben medirse, no suponer
1. Descomponer `Projects` JM 7.8G en JSON recetas/ediciones, artifacts, render, thumbnails, proxies y originales según ubicación real, sin listar contenido privado ni borrar.
2. Comparar entrada original con proxy por duración, resolución, bitrate, HDR/360 y parámetros de calidad, con métricas bytes, tiempo, fallos y efecto visual. Un proxy puede ser mayor que original, por lo que no imponer relación de compresión universal. Receta v3 y compatibilidad Engine/Companion obligatorias.
3. Estimar espacio de múltiples proyectos en tres niveles: metadatos persistentes, caché regenerable con LRU/cotas, originales locales y resultado local; preservar proyectos referenciados en limpieza.
4. Distinguir «último trabajo» (atajo) de «Mis proyectos» por modalidad; diseñar política de expiración solo tras pruebas reales y decisión de producto.
5. Ejecutar pruebas de acceso negativo por owner para wizard, Push, Show, descargas y Companion loopback; revisar APIs en background, locks, cancelación y recuperación tras reinicio.
6. Esperar merge relevante de Chema en main y volver a comprobar rutas/SHAs. No fusionar una rama JM provisional directamente.

## Estado
**Auditoría estática y medición física completadas;** mapa de alto nivel validado por código; lista exhaustiva de endpoints, métricas reales de proxy/original y pruebas E2E aún pendientes. No prometer funcionamiento completo Google -> Stage/Push/Show -> MP4 hasta superar integración y pruebas con Windows.
