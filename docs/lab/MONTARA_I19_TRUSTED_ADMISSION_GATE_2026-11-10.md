# I19 — De propiedad validada a un job aislado con recuperación

**Fecha:** 2026-11-10. **Estado:** contrato de orquestación comprobado en laboratorio; **NO** activado en C8/Owner ni conectado aún al Engine real. **No fusionar a main.**

## Objetivo de producto

El usuario ya ha comprobado que el login Google real y sus proyectos persisten tras salir y volver a entrar. I13 creó la ruta *opt-in* de apertura autenticada, I17 demostró Engine/FFmpeg reales en cgroups temporales con cancelación, e I18 creó un registro duradero de jobs/fencing. **I19 une autorización y reserva persistente alrededor de un interfaz mínimo para el broker**, de forma reversible y sin dependencia de GCP/CPU/Docker.

## Código

`urano/trusted_job_admission.py` contiene `TrustedJobAdmission`, un controlador **solo de confianza**, y la interfaz `IsolatedJobBroker` (dos operaciones: `launch_and_verify(lease)` y `stop_and_verify_empty(lease)`). No hay rutas HTTP ni subprocess/sockets/proveedores en ese módulo. Se requiere una implementación real del broker, previamente verificada en el sistema operativo, antes de usarlo con propietarios reales.

1. **Arranque:** `startup_reconcile()` fencea y enumera jobs sin cerrar en el ledger I18; debe ejecutarse antes de `admit`, no una vez por petición. Su resultado no libera nada; el broker inspecciona y limpia cada huérfano individualmente.
2. **Entrada:** `admit(owner,project)` llama a `ProjectCatalog.get` antes de reservar o acceder al broker. Luego `JobRecoveryLedger.start_trusted` serializa una única reserva activa por owner. Si no hay exclusividad, `BusyOwner` sin tocar procesos. Solo una prueba positiva de `broker.launch_and_verify` permite `mark_running`.
3. **Error:** cualquier fallo de arranque solicita parada y exige verificación del cgroup vacío; solo entonces marca `stopped`. Si no se puede comprobar, persiste `stopping` y **se bloquean aperturas futuras**.
4. **Cierre:** `stop(job)` comprueba owner, UUID, `job_id`, generación y estado actuales; pasa a `stopping` y verifica parada. Un token obsoleto no puede liberar un trabajo posterior.
5. **Reinicio:** `cleanup_orphan()` solo admite el job que continúa `orphaned` con idénticos metadatos; exige prueba externa de limpieza antes de liberarlo. Dos usuarios diferentes pueden trabajar de forma independiente.

**Pruebas:** `tests/test_urano_trusted_job_admission.py` usa un broker de prueba que registra llamadas, pero **no prueba aislamiento kernel, cgroups ni apertura física Engine**. En VM, I19 + I18 + I13: **17 tests focales PASS**. Se añade CI específica, sin instalaciones ni privilegios.

## Límites y puerta siguiente

- El protocolo `IsolatedJobBroker` debe implementarse realmente reutilizando el controlador I17, con validación de proceso y unit/cgroup, y sin aceptar unidades o rutas elegidas desde HTTP. No se debe usar su fake en producción.
- I13 `OwnerEngineGateway` todavía requiere que se conecten `EngineProjectRegistry`, `RuntimeActivationGuard` y broker con estado consistentemente reconciliado. Esta orquestación **no es una transacción distribuida** entre guard, ledger y systemd; los fallos intermedios deben cerrar o persistir incertidumbre (fail closed). Evaluar un único estado transaccional en vez de acumular componentes.
- Ningún worker/engine/socket se lanza al importar I19. El servicio público `montara-owner` **no** monta el endpoint de abrir proyecto; se mantiene 404. Sin cambios en `main` ni Chema 8101–8103.
- Faltan separación UID host por tenant o aislamiento OCI equivalente, seccomp/AppArmor, protocolo físico Companion y prueba Stage/MP4 local.

**Siguiente objetivo:** unir este control plane con un único broker real I17 bajo una cuenta demo/entorno reservado. Una vez hecho y validado aislamiento de dos owners, activar «Abrir proyecto» **solo en una beta cerrada y detrás de flag**, y comenzar las pruebas de Companion. No prolongar artificialmente el proyecto en fases de laboratorio que no acerquen al recorrido funcional.
