# I3a — Aislamiento Owner y ciclo de vida de workers (contratos, no daemon)
**Fecha:** 2026-11-13 · **Estado:** candidatos probados para integración en main.

> **Aviso para Chema y su IA:** esta PR no activa un broker root ni conecta el Engine al catálogo Google de I2. No hace que Stage/Push/Show de main sean multiusuario. Integra los controles con los que un broker posterior tendrá que autenticar identidad y proyecto, reservar un worker por usuario y demostrar su parada. Conservar desactivada la ruta Owner incompleta.

## A. Novedades
- `urano/private_owner_admission.py`: verificación independiente de sesión+CSRF+UUID de proyecto sobre SQLite **de solo lectura**, sin confiar en datos `owner_id` del navegador.
- `urano/private_stage_owner_admission.py`: misma verificación para lectura Stage, generación y propietario, con catálogo sin mutaciones.
- `urano/job_recovery_ledger.py`: ledger persistente con estado `starting→running→stopping→stopped`, fencing por generación, un trabajo no verificado por Owner y recuperación `orphaned` tras reinicios. Prohíbe liberar un slot por timeout o simplemente porque el navegador haya desaparecido.
- `urano/restricted_systemd_broker.py`: nombres y cgroups controlados, recursos y propiedades de aislamiento del proceso; comprobación de cgroup vacío antes de liberar.
- `urano/restricted_broker_ipc.py`: autenticación por SO_PEERCRED de sockets Unix con UID distinto del web y protocolo cerrado de parada.
- `urano/worker_state_policy.py`: espacio persistente derivado del Owner sin acoplar a Google/GCP.
- `urano/native_owner_broker_policy.py`: sólo el operador elige un worker script autorizado; no el navegador.
- Nuevas pruebas `tests/test_owner_worker_controls_i3.py`: 7 casos reales SQLite y simulación OS.

## B. Duplicidades
No crear un segundo catálogo ni una segunda sesión, y no alterar el Engine global de Chema. Reutiliza `ProjectCatalog` y `SessionStore` presentes en main tras I1/I2.

## C. Reutilización
Son políticas de la beta H4 `fernando/chema-native-owner`, extraídas de forma aislada en una rama nueva desde main. No se importan de golpe los servicios/overlay de H4, sus sockets, su web ni su infraestructura.

## D. Riesgos y límites importantes
- Las clases **no levantan ningún proceso por sí mismas** ni ofrecen garantías sin un broker root desplegado y correctamente autorizado. **I3b** debe incorporar el ejecutor y hacer pruebas reales de aislamiento OS, permisos, cgroups, dos sesiones simultáneas, recuperación y fallos.
- `restricted_systemd_broker.py` hereda `TimeoutStopSec=3s` de H4. Es un límite corto que **puede conducir a SIGKILL durante shutdown**; corregir mediante cierre cooperativo y pruebas antes de considerarlo operativo/producción. No proponer que tres segundos garantizan seguridad de escritura.
- El `JobRecoveryLedger` solo se debe manipular desde el broker autorizado. Pasarle `verified_cgroup_empty=True` desde un endpoint público sería una vulnerabilidad; la prueba de cgroup debe ser independiente y real.
- No detener trabajos mediante `pkill` o solo porque lleven tiempo inactivos, no ampliar la protección de autoapagado para impedir indefinidamente el ahorro de GCP.
- No se incluye integración OAuth/Editor, publicación de VM/Cloudflare, migración de DB real ni apertura de puertos. Mantener aislamiento por propietario y no exponer nombres de unidades a usuarios.
- No se tocan `engine/`, `mixer/`, Companion ni servicios existentes.

## E. Pruebas y siguiente acción
19/19 PASS en VM **sin systemd real**, usando un directorio temporal, SQLite real para dos propietarios, sesiones revocables y pruebas de cgroup simulado; módulos concretos de I3 más contrato existente de main:
```sh
PYTHONPATH="$dir" /home/fgardel00/montara-owner-portal-release/.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```
Afirmaciones comprobadas: se permite proyecto propio; se deniega proyecto ajeno, CSRF incorrecto, sesión caducada, campos arbitrarios (unidad/UID/owner), generación inválida, cgroup incorrecto; crash conserva el bloqueo hasta parada verificada; Bob no se bloquea por Alice.

**Pendientes exigidos antes de declarar I3 completo**: servicio broker real aislado, transporte socket privado/FD, worker nativo de Chema con UUID por propietario, pruebas reales systemd en VM/rollback y apagado sin procesos inactivos eternos. Después I4 conecta el editor. No cambiar las reglas de `docs/COLLABORATION.md` ni marcar `validado-producción` por un test de contrato.

**Aviso de integración progresiva**: la UI seguirá viéndose igual, pero con multiusuario las rutas, workspaces, procesos y medios no pueden volver a servirse por un Engine global. Toda modificación futura de API, proxy o editor debe revisar esta auditoría y las de H4.
