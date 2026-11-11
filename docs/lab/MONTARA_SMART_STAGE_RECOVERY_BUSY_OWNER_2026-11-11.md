# SMART — Diagnóstico de recuperación Stage y rechazo del broker (11-11-2026)

## Informe de usuario

Al abrir desde «Mis proyectos» un Stage anterior, Chema muestra «Opening your edit…» y después «Lost the connection to Montara (/api/v1/wizard/status)». La portada y OAuth sí funcionan.

## Diagnóstico verificado sin acceso a originales ni edición de datos

- Servicio Owner, túnel y broker: activos. El fallo no prueba una caída de GCP/Cloudflare.
- El `web/montara.js` original reintenta **toda excepción de fetch GET** hasta tres veces y la reescribe como «Lost the connection», aunque la excepción haya ocurrido antes de enviar la petición por un rechazo en `owner_browser_bridge.js`.
- La entrada Owner existente en `?resume=footage` fuerza `ensure()` al consultar por primera vez `wizard/status`. Si el broker deniega la admisión, el adaptador anterior lanzaba un error y Chema lo malinterpretaba como desconexión.
- Inventario read-only de `/var/lib/montara-i26-broker/jobs.sqlite3`: dos workers `running`, uno `orphaned`, de tres propietarios distintos; no se ha parado ni recuperado ninguno.
- La única sesión no caducada observada en `sessions.sqlite3` estaba asociada a **tres proyectos del catálogo**, pero **un worker activo del proyecto más reciente**. Los otros proyectos no tienen worker activo. La implementación `ensure_owner` permite únicamente un worker activo/verificado por owner y solo su mismo proyecto. Para otro proyecto responde `BusyOwner` → HTTP 409 en `owner_broker_preview.py`. Por tanto, **hay un bloqueo de cambio entre proyectos plausible y compatible con el caso**, pero sin capturar el HTTP concreto de ese intento no se afirma demostrado.
- `main` Chema sigue intacto; `fernando/integracion` conserva merge desde main `5d65ec3`.

## Corrección limitada ya desplegada

- `urano/owner_browser_bridge.js`: cuando falla `/ensure`, conserva el código HTTP y mensaje seguro (409: otro proyecto activo; 401/403: sesión cambiada; 503: Engine privado no disponible). En la consulta original `GET wizard/status` de recuperación devuelve una **respuesta HTTP JSON con `error.message`** en vez de rechazar `fetch`. De ese modo Chema enseña la causa sin inventar desconexión ni repetir tres veces.
- No cambia el Engine, el broker, la identidad, el catálogo, las rutas de medios ni los archivos originales. No se cierra ningún worker; el cambio de proyecto requiere política posterior segura.
- Nueva prueba `tests/test_owner_stage_recovery_errors.cjs` con 409 y 503; regresiones `tests/test_owner_stage_resume.cjs`, `test_owner_browser_bridge.cjs`, `test_owner_review_bridge.cjs`: **4 PASS**.
- Despliegue SMART en GCP con backup `~/.config/montara-owner-beta/rollback-recovery-diagnostic-20261111/owner_browser_bridge.js`: health 200; entry guest 401; OAuth start 302; túnel y broker activos.

## Siguiente acción, sin repetir laboratorios

Comprobar visualmente el mensaje al reabrir un proyecto anterior. Si confirma 409, introducir un **cambio entre proyectos** que nunca interrumpa renders activos y que use cierre autorizado/verificado del worker anterior únicamente en condición ociosa; no imponer un cierre automático sin prueba de inactividad. Después Stage+Companion+MP4 local, antes de PRs selectivos hacia main. Evitar pedir al usuario nuevos originales o reinstalar Companion.
