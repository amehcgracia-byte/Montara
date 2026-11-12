# I4 — Fundamentos del Engine por propietario: contratos privados sin Docker

**Fecha:** 2026-11-10. **Base:** `fernando/integracion@13b07e3`. **Procedencia:** U13A #91, U13B #92, U13C #93, U13D #94; el worker de I4 usa la versión ampliada del laboratorio C8 (#158), compatible con los tests históricos.

## Qué se integra

- `urano/engine_bindings.py`: relación SQL propietario + UUID del catálogo + nombre de carpeta Engine, verificada y sin rutas del navegador.
- `urano/runtime_activation.py`: reserva persistente por propietario, estados `idle/switching/ready/busy`, generación, bloqueo de acceso cruzado y de trabajo activo.
- `urano/engine_worker_process.py`: worker interno de comandos fijos por stdin/stdout, con ruta Engine real pero **no expuesto a HTTP**; incluye operaciones Stage del laboratorio posterior sin activarlas.
- `urano/private_worker_supervisor.py`: ciclo de vida de subprocess POSIX, timeout, handshake PID, muerte de grupo y revocación tras cierre.
- 4 suites antiguas completas, 4 informes originales íntegros, un workflow de contrato nuevo.

## Elección consciente de alcance

**Esto NO significa que tengamos aislamiento multiusuario ni una beta con Engine conectado.** En la versión actual `PrivateWorkerSupervisor` hereda UID y permisos del proceso padre: dos trabajadores bajo la misma cuenta de Linux pueden acceder a archivos del otro. El protocolo limita comandos, pero no sustituye permisos de SO ni protege contra un proceso comprometido. Tampoco está resuelta la recuperación de caídas del supervisor ni de subprocess de FFmpeg huérfanos. Los informes U13A–D describen estas limitaciones en detalle.

**No se incorpora `OwnerRuntimeController` ni `ContainerWorkerBridge`**: el primero requiere concretamente un Docker bridge y el segundo arranca contenedores. No corresponde habilitar web ni sustituir `isinstance` por duck typing para simular seguridad. No hay cambios en `app.py`, `companion/`, `web/`, `engine/`, `mixer/` o configuración de servicios.

## Evidencia focalizada

En worktree separado de la VM, reutilizando Python de la beta pero sin acceder a sus datos ni servicios:

`PYTHONPATH="$PWD/tests:$PWD" python -m pytest -q tests/test_urano_engine_bindings.py tests/test_urano_runtime_activation.py tests/test_urano_engine_worker_process.py tests/test_urano_private_supervisor.py tests/test_urano_project_catalog.py tests/test_urano_session_http.py tests/test_c1_minimal_owner_api.py tests/test_c4_owner_dashboard.py tests/test_c8_google_owner_ui_bridge.py tests/test_c8_trusted_local_https.py`

**54 passed y 26 subtests passed.** Incluye subprocess sintéticos; NO usa Docker ni prueba el Engine físico, UID por usuario ni edición/export.

## Puerta antes de conectar C2/C5

1. Seleccionar control de aislamiento por propietario: diferentes cuentas Unix **con separación comprobada**, LXD o contenedores, sin asumir equivalencia. Verificar restricciones efectivas de arranque, filesystem, secretos, límites y limpieza; comparar coste y riesgos.
2. Definir abstracción mínima de worker con contratos de salud/proceso, activación, ingest, cierre y certificación. El portal actual permanece `runtime_controller=None`, fail-closed.
3. Demostrar dos usuarios reales, proyectos previos, negativa de lectura cruzada, restart/crash, cancelación, límites y ausencia de trabajos FFmpeg huérfanos. No servir medios originales al navegador/servidor.
4. Revisar el estado de `main` y de Engine/Mixer antes de cualquier PR hacia Chema. La aceptación aquí no implica autorización para desplegar.

**Gobernanza:** no fusionar las ramas históricas en bloque, no borrar nada, no tocar `main` ni los servicios 8101–8115.
