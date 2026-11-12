# MONTARA I26 — Broker privilegiado independiente, socket Unix y Engine auténtico

Fecha: 2026-11-10. Estado: servicio REAL instalado y funcionando en la VM de pruebas; **modo laboratorio, sin enlace al Owner público**.

## Arquitectura desplegada

Ruta técnica: Desktop Commander Remote → Oracle `instance-20261001-0035` → `ssh montara` → VM GCP. No se utiliza TryGateway. Rama de trabajo `fernando/i26-private-broker-local`, objetivo integración hacia `fernando/integracion`; `main` y los servicios de Chema 8101–8103 permanecen intactos.

- Cuenta sistema separada `montara-i26-client` (UID 995), sin shell ni sudo. La cuenta web/operador es UID 1006 y no tiene permiso de conexión directa al socket.
- Daemon systemd de sistema `montara-i26-broker.service` ejecutado como root en modo restringido (`ProtectHome`, `ProtectSystem=strict`, `PrivateTmp`, `PrivateDevices`, `NoNewPrivileges`, `ReadWritePaths` limitados). El servicio no escucha puertos TCP. Su socket AF_UNIX `/run/montara-i26-broker/control.sock` es `root:montara-i26-client` modo `0660`, dentro de directorio `0750`.
- `SO_PEERCRED` comprueba la identidad real del proceso cliente; peticiones limitadas a `ping`, `demo_start` **sin parámetros** y `stop` **solo** con `job_id`/generación. No se aceptan owner arbitrario, project, unit, path, PID ni parámetros systemd enviados por el cliente.
- El ledger I18/I24 del broker está bajo `/var/lib/montara-i26-broker/jobs.sqlite3`, propietario root, modo `0600`, directorio `0700`. Identidad de unidad derivada exclusivamente del UUID aleatorio persistido; recuperación automática de huérfanos tras reinicio del broker, con verificación física de cgroup antes de liberar el owner.
- Bundle **compartido, versionado y root-owned** `/opt/montara/bundles/engine-b5e48317ef85225f901adc69af8cc17aa8146880` (~1,4GB), de solo lectura. Solo se copia una vez; no 1,3GB por trabajo. Código del broker también root-owned en `/opt/montara/broker`.
- Engine ejecutado en unidad transitoria `montara-i24-job-<hex32>.service` con `DynamicUser`, `NoNewPrivileges`, HOME oculto, red privada, disco de proyecto separado en RuntimeDirectory, límites 768MiB RAM, 64 tareas y CPUQuota 100%. El worker crea/abre un **proyecto sintético** mediante API Engine auténtica, confirma la carpeta cargada y queda vivo para cancelación posterior.

## Evidencia física

1. `ping` de cuenta técnica: `ok=true`; intento de conexión directa desde UID 1006: **PermissionError [Errno 13]**. El Owner actual tiene `NoNewPrivs: 1` y `CapEff: 0000`; operador interactivo mantiene sudo general para laboratorios, por lo que un eventual aislamiento de despliegue requiere revisión antes de producción.
2. `demo_start` real: `engine_opened=true`, UID Engine **65475**, generación 1; la unidad quedaba activa tras volver el comando. Segundo `demo_start` concurrente rechazado `BusyOwner`; un `stop` con ID inexistente rechazado `StaleJob`. `stop` válido cerró el cgroup y permitió generación nueva.
3. Inicio generación 2 (UID host **63795**) y **reinicio del daemon mientras Engine seguía activo**. Durante el reinicio, el socket desaparece temporalmente (esperado); una vez activo, el broker recuperó el job persistido, comprobó y eliminó la unidad correcta sin afectar otros servicios. Después aceptó nueva generación 3 (UID host **64030**), que fue detenida con `state=stopped`. No quedaron unidades `montara-i24-job-*`.
4. Test offline de protocolo I26 + I25: **18 tests y 22 subtests PASS** tras corregir la validación del mensaje `stop` también en la frontera del socket, no solo en el controlador.
5. El Owner/túnel y puertos de Chema permanecieron activos; no hubo cambios en Cloudflare/Pages ni en `main`.

## Instalación y operación

El script opt-in `ops/install_i26_lab_broker.sh` crea la cuenta técnica, copia el código controlado por el operador a directorios root-owned, instala y habilita `montara-i26-broker.service`. Requiere operador con sudo y bundle preempaquetado verificado; el servidor web **nunca** ejecuta ese script. Se puede consultar el servicio con `sudo systemctl status montara-i26-broker` y el socket con `sudo stat ...`; para probar: `sudo runuser -u montara-i26-client -- python3 /opt/montara/broker/private_broker_client.py ping`.

## Límite de seguridad / próxima prueba humana

**NO habilitar la ruta pública `/open` todavía.** El IPC funciona desde una cuenta técnica distinta y maneja el ciclo completo del Engine real, pero `demo_start` es un comando de **laboratorio fijo**, no una autorización real de proyecto Google. El `GatewayJobBridge` I21 aún no envía una orden de apertura auténtica del usuario a este nuevo daemon: falta el enlace seguro entre la identidad verificada de Owner, su project UUID y el broker, sin convertir la web en un cliente administrativo ni admitir owner/proyectos elegidos arbitrariamente por socket. La cuenta web/operador comparte todavía UID 1006 con una cuenta con sudo interactivo general (aunque la unidad Owner tiene NoNewPrivileges), lo que impide declarar aislamiento de producción sin revisar esta frontera.

**Siguiente acción acotada:** integrar la autorización del proyecto en el servicio de control sin extender el protocolo con rutas arbitrarias, probar el botón solo en beta privada para la cuenta Google real, y después inspeccionar Companion instalado/residuos en Windows antes de Stage→MP4. No realizar más laboratorios redundantes de `DynamicUser`.

Autoapagado pendiente de revisión posterior con Chema; no entra en este hito. PR hacia `main` #189 sigue DRAFT.
