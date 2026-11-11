# MONTARA — Auditoría de integración I57–I59 (2026-11-11)

**Rama:** `fernando/integracion`. **Estado:** pruebas reales PASS en GCP aisladas; no se ha fusionado ni desplegado en Owner/túnel; la prueba humana Windows todavía NO está lista.

## Incidencia de infraestructura resuelta

Fernando encendió la VM GCP que estaba apagada. La conexión `ssh montara` volvió a funcionar vía Desktop Commander Remote en Oracle. En GCP `montara-owner-beta.service` y `montara-owner-tunnel.service` estaban **active**; checkout local limpio, ~41 GB libres. No se reinició ningún servicio ni se modificaron las rutas permanentes.

**Limpieza Oracle realizada:** se borraron exclusivamente los recursos temporales **creados por nosotros** para I55–I56:
- `/tmp/montara-i55-oracle.GATevW` (~151 MB).
- `/tmp/montara-i55-testvenv` (~21 MB).

Eliminación confirmada; sin tocar `ssh`, repositorios de PoPi, proyectos, configuraciones ni daemon Desktop Commander.

## Combinación JM–Engine–Mixer de Chema reconstruida

En un espacio privado de trabajo `/tmp/montara-i57-jm-engine.RMrBXm` en GCP (no es producción) se reconstruyó la combinación **exacta** de la rama original JM:
- **Editor JM:** `14cce126137a0ef30a987351ff35b750f54473bd`.
- **Engine:** `b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b`.
- **Mixer:** `f15ff91c1b80fc5f157099dcd9451d958d553ae6`.

El editor se extrajo por `git archive`, Engine/Mixer por clones Git filtrados de sus commits, con symlinks **solo dentro del laboratorio**. Python y dependencias de la instalación de Engine anterior se aprovecharon exclusivamente como entorno de librerías; **el código Engine ejecutado fue el nuevo `b867b3c`**. Nunca se sobrescribió `/opt/montara/bundles/engine-b5e4831...`, `main`, `engine/` o `mixer/` del repo.

**PASS I57:** la aplicación Flask completa de Chema arranca con esta matriz (360 rutas registradas), abre el UUID de proyecto privado y responde HTTP 200 a `GET /api/v1/project`. El flujo real con FFmpeg `/wizard/upload` → `/wizard/projects/new` → `/wizard/draft` devuelve **200/200/200**, conserva UUID y registra el proxy.

## Conexión de «Continuar» con seguridad por Owner

Se amplió `urano/owner_original_jm_rpc.py` únicamente con las operaciones Stage revisadas:
- `POST /wizard/prepare`, `POST /wizard/start`, `POST /settings/fillers`.
- `GET /artifacts/sync`.
- `GET /wizard/status?project_id=...`, descartando la ruta física que llega del navegador (el worker privado posee su proyecto actual), sin permitir filtros arbitrarios ni selección de otro proyecto.

El `urano/owner_browser_bridge.js` original reescribe estas llamadas al endpoint por UUID, sin cambiar el JS de Chema. `urano/owner_first_stage_wizard.py` filtra los nuevos POST: `project_id` debe corresponder al Owner activo, `videos` y `master/songs` deben ser subidos y registrados previamente por su propio proyecto; `settings/fillers` no admite rutas externas ni suplantación. Las pruebas de regresión:
- `tests/test_urano_owner_first_stage_wizard.py`: **8/8 PASS** (incluye ficheros ajenos, sustitución de proyecto, filler y start/prepare).
- `tests/test_urano_owner_original_jm_rpc.py`: **8/8 PASS** con Flask real + socket Unix y status sin permitir paths al backend.
- JS original en Node: adapter de Fetch/XHR PASS.

**PASS I58 con Engine ACTUAL:** FFmpeg generó un vídeo sintético y máster WAV de 10 s: upload, draft, filler settings y `POST wizard/prepare` (**202**) funcionaron. Status pasó `running / prepare` → `running / sync` → `waiting_choice / sync`, y `GET artifacts/sync` devolvió **HTTP 200**.

Una segunda prueba con **12 s de ruido rosa no periódico** idéntico en cámara y máster devolvió correlación de sincronización interna **18,8868**, sin marcar low_confidence; `POST wizard/start` devolvió **HTTP 202**, `status=running`. **La ejecución de render NO fue seguida hasta su terminación**. En ese ensayo la limpieza de `TemporaryDirectory` se produjo mientras la tarea seguía creando ficheros, causando excepción de limpieza; no es un fallo demostrado de Engine. No afirmar que export/corte/MP4 final haya pasado.

## I59: worker completo con los tres componentes nuevos

**PASS:** se levantó `urano/full_jm_worker.serve_original_jm_worker()` dentro de un **proceso Python independiente** con:
- UUID Owner guardado en state root aislado, Unix HTTP socket y Stage-status socket en runtime root separado.
- `GET /` HTTP 200, `GET /montara.js` HTTP 200, JS original 184.474 bytes, `GET /api/v1/project` HTTP 200.
- UID/PID del proceso privado confirmados mediante `SO_PEERCRED`.
- El worker se detuvo limpiamente al finalizar la prueba, sin alterar servicios activos.

**PASS del candidato con proxies largos:** se hizo una **copia temporal** del editor JM original, se aplicó el overlay de `urano/jm_private_proxy_overlay.py` y se escribió/verificó el manifiesto de `urano/jm_bundle_manifest.py`. Hash esperado del overlay `264285f26a3106b7be55cb2d46b2769f7c3f9cbad7d484c5ddd7301c6c36073d`. Se comprobó que el uploader original de Chema no cambió.

El worker COMPLETO real arrancó con `private_preview_limit_mib=2048`; por el **socket Unix real** respondió a `GET /montara/uploads` con `max_file_bytes=2048 MiB`, `max_original_file_bytes=256 MiB`, HTTP 200. Se cerró el proceso tras prueba. **Esto verifica configuración y montaje del worker, NO una transferencia de 2 GiB ni un render de gran duración.**

## Lo que queda antes del turno de Fernando

1. **Reproducir y automatizar el laboratorio de última versión** como un test no destructivo con apagado/espera del Engine (no limpiar su directorio mientras renderiza). El espacio temporal candidato está en `/tmp/montara-i57-jm-engine.RMrBXm` si GCP sigue encendida; **no considerarlo fuente permanente**.
2. Habilitar exclusivamente las siguientes operaciones Stage para la UI real: `/wizard/review`, previews, edición/cortes, composición, streaming Range y el **render final local mediante Companion**. No exponer un proxy HTTP genérico al Engine ni devolver rutas de otros Owners.
3. Resolver el CSRF por pestaña antes de multi-tab/multiusuario real; hay rotación de token compartida entre pestañas.
4. Construir, verificar y desplegar bajo un **entorno de prueba privado separado** el bundle inmutable JM (root-owned), Engine nuevo y Mixer emparejado; probar `systemd DynamicUser`, `StateDirectory`, límites de disco/limpieza, auth Google Owner y broker real. No sustituir el live Owner portal sin autorización.
5. **Test humano:** navegador Google → Stage real → Companion Windows → proxy → edición de Chema → MP4 renderizado local, validando ubicación visible de proyecto y originales intactos. Push/Show después.

**Conclusión:** muy buena evidencia del núcleo nuevo completo, la etapa 5 sigue ABIERTA; `HTTP 202` de `wizard/start` no es un MP4 final.
