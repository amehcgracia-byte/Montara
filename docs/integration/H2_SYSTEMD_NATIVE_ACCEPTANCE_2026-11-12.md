# Hito 2 · Aceptación técnica systemd nativo (12 noviembre 2026)

**Estado: aprobado en aislamiento real. No desplegado en la beta de usuarios.**
**Rama:** `fernando/chema-native-owner` (nacida de `main`; `web/` original intacto).

## Qué se ha comprobado físicamente

Se instaló temporalmente **solo** el código revisado del nuevo worker nativo en una ruta independiente de `/opt/montara`, propiedad de root, y se arrancó un **servicio transient real** bajo `systemd-run --system --collect`, **sin modificar el broker ni el worker actuales**. Su identidad, unidad systemd, Directorio de Estado y RuntimeDirectory eran nuevos y distintos de los usuarios reales.

Protecciones comprobadas en el servicio real:
- `DynamicUser=yes`, `NoNewPrivileges=yes`, `PrivateNetwork=yes`, `ProtectSystem=strict`.
- `MemoryMax`, `CPUQuota`, `TasksMax`, bind mounts de solo lectura a los paquetes inmutables Engine y Chema; directorios `0700`.
- El `StateDirectory` real creado por systemd es un **enlace propiedad de root** desde `/var/lib/montara-owner-<hash>` a `private/montara-owner-<hash>`. La primera versión del validador nativo lo rechazaba. Se corrigió para admitir **exclusivamente** esa forma canónica y se añadieron pruebas de rechazo de enlaces no autorizados.
- `ready.json` se emitió con la identidad de workspace correcta, cuando ya existían los **dos sockets privados**: `jm-editor-http.sock` y `stage-read.sock`, ambos modo `0600`.
- Consultas **reales** a través de socket Unix (Python HTTP cliente) con permisos de root dentro del entorno de ensayo: `GET /api/v1/wizard/status` → **200**; `POST /api/v1/wizard/projects/new` → **200**; `GET /montara/recovery/latest` → **404 esperado** porque todavía no había proyecto guardado.
- Consulta real al socket de estado con `SO_PEERCRED` y `{op:stage_snapshot, project_id:workspace_uuid, generation:1}`: `ok:true`, `camera_count:0`, `ingest:not_started`.
- Se comprobó que el servicio estaba **active**, tenía cgroup `/system.slice/montara-i24-job-...` y mantenía protecciones reales de systemd.

**Pruebas previas reutilizadas:** en el paquete original de Chema sobre GCP, con un MP4 y un WAV diminutos de FFmpeg, `New → Draft → Latest → New → Latest` ya fue **200 → 200 → 200 → 200 → 200** a través de un Flask nativo y un socket Unix privado. Esa prueba anterior NO se hizo dentro de esta unidad systemd; no confundir ambas evidencias.

## Evidencia automatizada

Tras la corrección del enlace privado de systemd:
- **67 pruebas Python nativas y 84 subpruebas PASS**.
- En el bloque anterior, **44 pruebas históricas I24/I25/sockets/ledger y 42 subpruebas PASS** con el catálogo adaptado.
- La línea de comandos que el broker actual construirá para la nueva variante fue inspeccionada con el **`DemoBroker.demo_start` real**, pero `systemd-run` sustituido por una función de prueba; no tocó el ledger real.

La primera ejecución del cliente de la unidad transient se interrumpió por un fallo del **cliente de prueba** (intentaba usar `HTTPConnection` como context manager). El worker sí había anunciado ready y se limpió correctamente. Se volvió a probar, corrigiendo el cliente, con **resultado íntegro PASS**.

## Aislamiento y limpieza

La unidad transient se detuvo por nombre exacto y se verificó su parada; se retiraron exclusivamente su StateDirectory recién creado, el enlace canónico, RuntimeDirectory y el código de ensayo. Comprobaciones posteriores: **no existe ruta de staging**, **no existe RuntimeDirectory transient**, y queda **un único worker activo**: el original de la beta. `montara-i26-broker.service`, `montara-owner-beta.service`, `montara-owner-tunnel.service` permanecen activos; `/healthz` del Worker público responde **200**.

**No se ha cambiado `main`, ni Cloudflare, ni los workers de usuarios, ni los proyectos guardados, ni la configuración systemd de producción.**

## Estado de hitos y frontera exacta

**Hito 2: base técnica y arranque nativo de systemd verificados.** Para la aceptación funcional faltan:
1. **Hito 3:** conectar el nuevo worker a la admisión **Owner de Google/CSRF** y al broker real, en un despliegue aislado. La invocación real del nuevo script *por el broker actual* no se ha ejecutado todavía; no confundir con la prueba transient.
2. Retirar la navegación y catálogo multiproyecto añadidos sin perder la persistencia ni reabrir los proyectos anteriores. Reutilizar Chema `Music/Video → Stage/Push/Show` y su New/Latest nativo.
3. Completar las rutas de Stage/Music/Mixer/Companion/exportación y comprobar mediante Chrome, luego dos usuarios reales. No declarar MP4 final hasta tenerlo.

No crear un broker duradero adicional ni reiniciar el que sirve a la beta antes de validar la separación de estados y un rollback.

**Pendiente deliberadamente pospuesto por decisión del usuario:** después de los hitos prioritarios, localizar en GitHub el **acuerdo de colaboración entre IAs de Fernando y Chema** (documentación de acuerdos/decisiones, comunicación de issues y peticiones, protocolo de coordinación). No interrumpir la integración actual por esta búsqueda.
