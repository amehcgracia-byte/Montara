# URANO U13E2C — rectificación y aceptación de exportación Stage real · 2026-11-08

**Novedad comprobada sobre el informe parcial anterior:** la exportación iniciada desde el laboratorio FER **sí alcanzó estado `done`**. El intento de detener nuestra ejecución para no competir con el render de JM no había impedido que el export finalizase. La evidencia posterior es concluyente para el estado de finalización, pero **no equivale todavía a aceptación del Companion/navegador ni decodificación exhaustiva**.

## Evidencia verificable en VM aislada

- Checkout experimental de PR #112 `16a87a78`, Engine pin `841f4ed`; no es `main` actual (`beb11d8ea` / Engine `98bce06`).
- Directorio exclusivo: `/home/fgardel00/urano-u13e2c-acceptance-20261108/`.
- Proyecto real de laboratorio: `outputs/pipeline-sony.zuckervid`. Fuentes: dos fragmentos visualmente diferentes pero derivados del mismo clip **Sony** real `C0188.MP4` (20 s), con máster WAV sacado del mismo origen. **No** son dos cámaras físicas independientes ni prueba de sincronía con iPhone/360.
- Todos los estados persistidos al reabrir con `core.project.load_project`: `ingest=done, sync=done, cut=done, edit=done, export=done`. Existe `artifacts/sync_map.json` (dos cámaras), `edit_plan.json` y `export_manifest.json`.
- `project.json`: export `started_at=2026-11-08T14:27:58.483685Z`, `finished_at=2026-11-08T14:29:34.881934Z`, `elapsed_seconds=96.398`, `error=null`. Log final `100% Export ready`.
- MP4 final `exports/URANO_SONY_STAGE-youtube-20261108-142758-496218324.mp4`: **52,519,068 bytes**, **40.200 s** (20 s aprox. de contenido + intro/outro de branding), **H.264 1920×1080 1206 fotogramas**, **AAC 48 kHz**; `ffprobe` retorna salida válida.
- SHA-256 del MP4: `1a9f258973c667e9cb74cd94c0514f65e212aef2d49f61bdba6e31fff48b9a39`.
- El manifiesto export registra `segment_count=5`, `segment_workers=4` y tiempos internos; **no** deducir capacidad ni velocidad por usuario de esta prueba.
- La comprobación de carga posterior confirmó que JM seguía exportando con FFmpeg (~646% CPU). **No** se lanzó decodificación completa de este MP4 ni más renders para no interferir. Requiere `ffmpeg -xerror` completo cuando la máquina quede disponible, más inspección visual.
- No se alteraron originales, servicios, checkout FER ni JM, ni se subió media privada a GitHub/Actions.

## Estado real y ruta pendiente

**PASS confirmado:** fases del Engine, sincronía de dos fragmentos Sony del mismo origen, generación y persistencia de proyecto, finalización de ExportStage y metadatos ffprobe del MP4. `load_project` permite recuperar receta y referencias, pero no se ha probado aún la recuperación interactiva desde web/Companion.

**Pendiente:** (1) decodificación completa del MP4 y QA visual/audio; (2) aceptación de export local con Companion y navegador H.264 compatible (el Chromium Playwright disponible en esta VM informó `canPlayType(...H264)=''`); (3) prueba 2 cámaras físicas con máster acreditado y 360 separado; (4) armonización con Engine actual y nueva UI; (5) aislamiento real de cuentas/proyectos/Engine. No elevar PR #112 a lista de integración sin estos pasos.

**Política de coexistencia:** cualquier nuevo render debe esperar a que JM no esté ocupando intensamente CPU; no reiniciar/detener JM. El repositorio contiene `deploy/vm/bench_lock.sh`, pero el lock compartido no está instalado en esta VM. Mantener trabajo con lock local y control previo de CPU.
