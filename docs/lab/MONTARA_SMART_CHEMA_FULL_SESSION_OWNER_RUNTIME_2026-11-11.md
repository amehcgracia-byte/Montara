# SMART — Integración nativa de sesiones Stage de Chema (11-11-2026)

## Evidencia humana que inició esta fase
- El usuario confirmó que los vídeos y audios preparados por Companion **se suben correctamente** al Stage Owner.
- Al pulsar `Continue` con vídeo + varias pistas o audio preview, Chema muestra `Your session, song by song` y `Lost the connection to Montara (/montara/session)`.
- En la cabecera seguía visible el Engine ON/OFF antiguo, con un cuadro de confirmación `Close this idle Engine?`; el indicador del nombre del proyecto aún no estaba desplegado.

## Causa y verificación
- El propio código del editor `web/montara.js` elige `openFullSession(true)` cuando Stage tiene vídeo y varios audios o audio preview. No es un fallo de navegación del usuario.
- `web/full-session.js` inicia `POST /montara/session`, después consulta progreso y rutas de mezcla; el adaptador `owner_browser_bridge.js` y `owner_original_jm_rpc.py` no tenían ninguna de esas rutas en su lista cerrada. El adaptador lanzaba error JS que Chema convertía en `Lost the connection`, aunque Cloudflare y GCP estuvieran operativos.
- El editor y servidor originales de Chema permanecen inmutables; Owner amplía su bridge bajo sesión Google y proyecto Stage verificados.

## Cambios desplegados en portal Owner
- `urano/owner_session_contract.py`: rutas y métodos explícitos para crear sesión, consultar progreso, consultar audio, cancelar, preparar, seleccionar canciones, renderizar, subir rangos originales, confirmar mezcla local y servir resultados. Queries estrictamente acotadas, sin catch-all de `/montara`.
- `urano/owner_session_bindings.py`: asociación durable de `session_id` (12 hex) con `owner_id` y `project_id` en SQLite. El dueño solo puede acceder a sesiones creadas desde el Stage correspondiente. No guarda media original, rutas ni tokens.
- `urano/owner_original_jm_rpc.py`: autentica la solicitud, vincula las nuevas sesiones tras el POST 202, niega identificadores de otras sesiones y retransmite los comandos al mismo worker privado de Chema. Audio y ZIP viajan por stream con límite de 2 GiB y CSRF; `HEAD` mismo origen sin Origin acepta CSRF. Respuestas de error compatibles con el cliente de Chema.
- `urano/owner_browser_bridge.js`: mapea las rutas originales de sesión a URLs Owner, inyecta CSRF y generación del Engine y convierte la escucha nativa de `<audio>` y las descargas directas en URLs Blob locales protegidas; no expone `/montara/session` global. Para el reproductor, el preview completo en memoria se limita a 128 MiB. Una sesión superior al límite necesita una estrategia de streaming local futuro.
- Compatibilidad inmediata: en el CSS activo se oculta el antiguo interruptor de Engine que podía detener el worker. La luz indicadora sigue, pero **el título del proyecto no está desplegado**; la versión read-only con título depende de actualización del broker root y no debe reiniciarse con un worker activo.

## Pruebas ejecutadas
- **57 Python PASS, 99 subpruebas PASS y 5 Node PASS, 2 skipped**, con tests de proyecto propietario vs otro proyecto, usuario distinto, CSRF, rutas inválidas, HEAD sin Origin, creación y lectura de sesión por HTTP Unix real, audio y enlace ZIP local por el navegador simulado.
- Los archivos se pusieron en un staging separado y se compilaron en GCP. Solo se reemplazaron los 4 módulos del portal y se reinició **únicamente `montara-owner-beta.service`**.
- Rollback disponible en `~/.config/montara-owner-beta/rollback-chema-session-20261111/`; copia del CSS anterior en `rollback-engine-switch-hidden-20261111/`.
- Despliegue público: `/healthz` 200, entrada anónima 401, Google OAuth start 302, sesión privada sin cookie 401. Portal, túnel y broker activos, PID broker root **672 sin cambios**. Ledger actual: 1 worker `running`, 12 anteriores `stopped`.
- Se verificó que la tabla `urano_owner_jm_sessions` está creada en la SQLite Owner; **no se han usado ni modificado archivos originales ni proyectos del usuario**.

## Limitaciones y siguiente aceptación
- La nueva ruta de sesión **no tiene aún E2E autenticado desde el Chrome del usuario**. La transferencia de audio/vídeo ya fue confirmada antes de la integración, pero el render musical y MP4 todavía no están validados. No presentar esta fase como exportación PASS.
- En el editor original quedan fuera del piloto Owner APIs de mezcla manual (`/montara/mix`), mastering independiente (`/montara/master`), narración de Show y otras rutas; no afirmar que esas modalidades funcionan en la beta.
- Control humano más económico: abrir una pestaña nueva del proyecto Stage, recargar para obtener JS actualizado, recuperar archivos si el navegador lo ofrece y pulsar `Continue` una sola vez. Si falla, anotar el texto exacto sin repetir cargas innecesarias.
- Conserva `main`, Engine, Mixer y worker root activos. El autoapagado sigue con 120 min de inactividad y verificación cada 20 min, sin cambios.