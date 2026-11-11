# SMART — Seguimiento de incidencias humanas: Engine, ficheros y Plans
**Fecha:** 2026-11-11 · **Rama:** fernando/integracion.

## Observaciones humanas
- Engine ON funciona; al pulsar OFF se abría inesperadamente el modal Account, en lugar de explicar el error junto al switch.
- Algunos vídeos acababan con fila `ERROR` y estado visual `Ready · lossless`, sin aviso rojo global. El texto del estado no demostraba entrega al Engine.
- Pie de página `Montara SMART Beta · Plans · preview` apuntaba a `/montara/plans`, que en la beta Owner devolvía 404.
- Un audio presentado en el navegador como `5._Second.mp3` falló con `Private upload rejected (invalid_media_name)`, y sí se mostró el aviso rojo.

## Diagnóstico
- El nombre visible `5._Second.mp3` **sí** satisface la expresión de nombres de archivo de Owner, tanto en subida directa como en metadatos resumables. No se conoce el nombre completo realmente recibido en la petición rechazada; no inventar una explicación ni ampliar restricciones a ciegas.
- El error `invalid_media_name` podía ocultar una cabecera `X-Zucker-Filename` ausente en subida directa. Se distingue ahora `missing_media_filename_header` y `invalid_media_filename_encoding`, sin registrar rutas ni nombres privados.
- En Chema `web/montara.js` la fila con f.kind=`error` muestra antes el texto genérico `Ready · lossless` si f.small, por el orden de su ternario. Se trata de un fallo de presentación; no se ha afirmado que el vídeo fuera aceptado.
- El aviso Owner rojo estaba implementado para XMLHttpRequest directo, no para `fetch` en el uploader reanudable; por eso el vídeo no mostraba el mensaje arriba.
- `web/plans.html` y `plans.js` sí existen en el JM original. `plans.html` no forma parte del manifiesto genérico por ser HTML, de modo que se expone solamente por nueva ruta explícita con sesión Owner y hash fijado al arrancar, sin habilitar una ruta HTML arbitraria.

## Cambios desplegados, con rollback
1. `urano/owner_project_picker.js` y `.css`: error Engine junto al interruptor, sin abrir Account. Verde solo tras admisión confirmada; rojo solo tras cierre confirmado; estado desconocido visible.
2. `.css`: en filas ERROR se muestra `Transfer failed` en vez de `Ready · lossless`. No cambia la carga ni modifica el editor de Chema.
3. `urano/original_jm_owner_assets.py`: `Plans · preview` usa la página real de Chema bajo `/urano/v1/editor/projects/<UUID>/plans.html`; página original servida solo con sesión/owner y hash de contenido verificado. `plans.js` servido por whitelist existente; el enlace de regreso se lleva al editor privado, no a Vercel. Simulador sin pagos.
4. `urano/first_valid_upload_gate.py`: distinguir filename XHR ausente de nombres malformados; se preserva la restricción de caracteres y las medidas de seguridad.
5. `urano/owner_browser_bridge.js`: avisos persistentes también para POST de metadatos, PUT de fragmentos y POST finish del uploader resumable, incluso errores de red. La respuesta nativa no se consume y el reintento de Chema permanece intacto.
6. Regresiones nuevas en `tests/test_owner_navigation_consistency.py`, `tests/test_urano_owner_original_jm_rpc.py` y `tests/test_owner_fragmented_upload_feedback.cjs`.

## Verificaciones
- Conjunto Python: **32 PASS, 42 subpruebas PASS**, rutas de Plans autenticadas, validación de nombre y contratos privados.
- Pruebas JS de rutas y feedback: **4 PASS**. Sintaxis Node y Python PASS.
- Beta pública: health 200, guest entry 401, Google start 302, portal/túnel/broker activos.
- Copias reversibles: `~/.config/montara-owner-beta/rollback-footer-engine-filelabel-20261111/` y `~/.config/montara-owner-beta/rollback-fragmented-upload-feedback-20261111/`.
- **Pendiente:** determinar por qué la petición real de `5._Second.mp3` obtuvo invalid_media_name y por qué no finaliza aún el flujo vídeo/audio de Windows. No afirmar carga E2E ni MP4 local.
- El candidato del runtime de audio lossless en `/tmp/montara-lossless-audio-release-20261111/` sigue preparado y probado, pero **no activado** en el broker. Sin cambios en main, Engine activo, proxy de Cloudflare ni datos originales.

## Siguiente trabajo funcional
Consolidar el candidato de runtime con ventana segura del broker y prueba de transferencia a un owner de prueba. Capturar un código de fallo seguro (sin datos privados) de XHR/resumable si el error persiste. Prioridad: Companion → proxy → Stage → MP4 nativo.