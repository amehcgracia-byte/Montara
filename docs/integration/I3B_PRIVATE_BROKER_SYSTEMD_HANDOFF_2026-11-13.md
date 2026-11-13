# I3b — Broker privado y entrada systemd del Engine Owner (integración en main)
**Fecha 2026-11-13 · Autor Fernando · Estado: componente optativo, sin despliegue.**

> **Nota para Chema y su IA:** `main` seguirá funcionando visual y funcionalmente como antes. Esta entrega incorpora el ejecutor aislado que conoce los controles I3a, pero NO lo conecta todavía al editor ni a los flujos públicos de Stage/Push/Show. Un nuevo broker solo se puede iniciar por configuración explícita del operador con sockets y privilegios restringidos; ningún usuario puede elegir el worker/Engine/UID/servicio a través del navegador. Hasta que llegue I4, NO activar esta ruta en la instalación principal.

## A. Novedades
- `urano/private_broker_service.py`: servicio broker root opt-in, entrada local Unix con verificación de credenciales del proceso, selección de recursos del operador, ledger por Owner con recuperación, lanzamiento de unidades `systemd` con `DynamicUser` y perfiles aislados; validación independiente de sesión/proyecto, rutas de broker H4 disjuntas del piloto antiguo, operaciones de Owner y estado.
- `urano/native_owner_systemd_entry.py`: entrada controlada y verificación de configuración/propiedad de directorios y unidad antes de iniciar el worker de Chema; sin ejecución como código de aplicación global.
- `urano/private_jm_wsgi_socket.py`, `private_engine_route_contract.py`, `private_editor_connect_admission.py`, `private_editor_fd_handoff.py`, `private_stage_snapshot_bridge.py`, `private_stage_unix_transport.py`, `editor_mode.py`: transporte local privado/FD y contratos mínimos que evitan aceptar rutas del cliente como autoridad.
- 15 pruebas existentes del código H4 sobre namespace broker, selección de scripts, control de rutas/UID y entrada systemd.

## B. Duplicidades
Reutiliza el ledger, admisión SQLite, perfil de aislamiento y política de recursos ya fusionados en I3a. Se incorpora el broker que entiende esos contratos, **no** otro catálogo ni otra identidad Google y **no** se sustituye el editor principal de Chema. Se mantienen caminos heredados para rollback y el nuevo modo es explícito.

## C. Reutilización
Fuente: beta H4 aislada con trabajador de Chema y MP4 real ya validado en Windows el 13-11. La puesta en servicio concreta H4 en GCP es independiente del código integrado en `main`, que **no** recibe aquí secretos, unidades systemd nuevas, ports ni tokens.

## D. Riesgos y bloqueos
- Solo las unidades de `systemd` verificadas con generación y cgroup pueden liberarse. Nunca exponer endpoint público para detener PID/Engine arbitrario.
- La entrada worker nativa **depende aún** de la composición runtime/WSGI real de Chema, workspace gateway y puente del editor (I4). La importación de este archivo por sí sola no es un Stage funcional ni da acceso a vídeos.
- El código heredado de I3a establece `TimeoutStopSec=3s`; NO garantiza guardar trabajos si se apaga en mitad de mutaciones sin render activo. El shutdown cooperativo y el autoapagado con actividad web/SSH constituyen gate operativo posterior I6. No activar hasta probarlos.
- Security: deployment debe revisar permisos, propiedad root, sockets exclusivos, SELinux/AppArmor si aplica, UID separado, permisos SQLite de lectura solo por broker, límites de tamaño de proxy y rollback en caso de cgroup desconocido.
- El usuario debe conservar proyectos y medios tras reinicio. Las pruebas aisladas de componentes no sustituyen pruebas reales de 2 usuarios de sistema, origen HTTPS, transporte y VM poweroff.
- No se toca `engine/`, `mixer/`, ni companion, ni `app.py`, ni ruta de producción. No actualizar la VM sin nuevo gate operativo.

## E. Pruebas realizadas y continuación
En VM, copia de archivos exactos de esta integración a directorio temporal con Python de release, **15/15 PASS**:
```sh
PYTHONPATH="$dir" /home/fgardel00/montara-owner-portal-release/.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```
Tests: `test_native_owner_broker_policy.py` (4), `test_native_owner_h4_broker_isolation.py` (4), `test_native_owner_systemd_entry.py` (7). **No se ejecutó un render ni se arrancó root broker en esta prueba**. El servicio H4 real, ya probado en turnos previos, permanece separado.

## Lo que falta para Montara multiusuario completo
- **I4** conectar el editor real de Chema a un workspace privado por Owner y a los sockets del broker; integrar servicios de runtime restantes, Stage/Push/Show, proxy, vídeo, audio, snapshots, editor recovery y permisos. No activar rutas mientras falten dependencias.
- **I5** Companion Windows y Mac (instalador, versiones y descarga por SO alojada en servidor).
- **I6** shutdown cooperativo de worker y retención temporal, sin impedir ahorro VM por worker inactivo.
- **I7** pruebas E2E 2 usuarios reales en navegador, controles cruzados, videos MP4, y rollback.

**IA colaboradoras:** revisar `docs/COLLABORATION.md`, `docs/lab/STATUS-JM.md`, `docs/lab/STATUS-FER.md`, issue #216, handoff I3a y auditorías H4 antes de cambiar esta capa. La interfaz no revela la diferencia de aislamiento interno.
