# I18 — Registro duradero de ejecución: recuperación tras reinicio y fencing

**Fecha:** 10/11/2026. **Ámbito:** código de control, sin lanzar contenedores, procesos, systemd, ni instalar servicios. **Estado:** contrato probado, **no conectado al Owner público, ni al broker de I17, ni a `main`**.

## Por qué necesitamos esta etapa

I17 consiguió abrir el Engine real y detener el grupo completo junto a FFmpeg desde un controlador independiente, incluso cuando el Engine es PID 1 en su espacio Linux. El laboratorio real se validó dos veces y no dejó procesos, directorios ni unidades residuales. Sin embargo, un reinicio de la VM o una caída del controlador puede dejar una transición ambigua. No es seguro admitir trabajos nuevos porque una sesión HTTPS haya finalizado ni porque transcurran cinco minutos.

## Diseño añadido

`urano/job_recovery_ledger.py` incluye `JobRecoveryLedger`, un registro SQLite **solo invocable por componentes del backend de confianza**. Identificadores de ejecución aleatorios, contador **monótono por propietario**, restricción de exactamente un trabajo no verificado por propietario y transiciones atómicas `BEGIN IMMEDIATE`.

- `start_trusted`: reserva un trabajo si no existe otro `starting`, `running`, `stopping` u `orphaned` del propietario. No crea un proceso ni toma rutas del navegador.
- `mark_running`: exige coincidencia de propietario, proyecto, `job_id`, generación y estado previo, tras atestación del runtime por un broker futuro.
- `request_stop`: pasa a `stopping` y mantiene la reserva. El estado persistido no acredita que systemd haya detenido aún nada.
- `recover_after_restart`: al iniciar un controlador, marca como `orphaned` los trabajos no finalizados y los enumera para inspección/reconciliación. Un trabajo huérfano **bloquea** otro del mismo propietario.
- `confirm_stopped(..., verified_cgroup_empty=True)`: la confirmación solo puede venir del broker de confianza **después** de verificar identidad exacta de unidad/cgroup y ausencia de procesos. La comprobación del kernel NO está implementada en el ledger y el booleano no es prueba criptográfica; el backend que lo invoque debe disponer de las autorizaciones necesarias.

No se admite liberación automática por TTL. Un controlador con generación antigua no puede reactivar ni finalizar otra ejecución. Los proyectos y owner IDs se almacenan como referencias opacas; sin acoplar el almacenamiento a Cloudflare, GCP, Docker, systemd, GPU o arquitectura CPU. Los originales del vídeo continúan locales con Companion.

## Evidencia

Nuevo `tests/test_urano_job_recovery_ledger.py` con 6 casos: secuencia normal, crash/restart, generaciones obsoletas, intento cruzado por propietario/proyecto, concurrencia real entre dos hilos sobre SQLite y ausencia de liberación por TTL. **17 tests focales PASS** con contratos I13 y activación U13 ya existentes. Una futura CI específica validará este contrato offline sin arrancar el Engine; el E2E general histórico no sustituye la prueba real con Companion.

## Límites y próximos gates

1. El ledger **no sustituye** a `RuntimeActivationGuard` ni está integrado todavía con él. Una implementación de broker deberá mantener coherencia de ambos estados, diseñar reconciliación crash-safe y evitar dobles decisiones si falla entre sus transacciones. Puede requerir consolidar estados en una sola DB o un outbox transaccional.
2. La operación `recover_after_restart` se debe ejecutar **antes de aceptar nuevos trabajos**. El ledger como componente aislado no controla la secuencia de arranque del broker, ni garantiza que quien lo invoca sea de confianza; de ello debe encargarse el provisionador.
3. Para liberar la reserva, un controlador externo tiene que demostrar terminación y cgroup vacío, no solo enviar `systemctl stop` o confiar en PID sin comprobar contra la generación.
4. Falta mapeo durable `job_id` → identificador seguro de unidad systemd/OCI y recuperación cuando se reinicia el host, prueba con fallo de controlador a mitad de una operación y un Engine/FFmpeg reales.
5. Falta comprobar límite de CPU/RAM/datos temporales y aislamiento por UID de host o runtime equivalente; pruebas adversariales, vídeo y E2E Companion → export local. No activar `POST /urano/v1/projects/<uuid>/open` en Owner C8.

**Regla de integración:** mantener `fernando/integracion` como rama de trabajo y PR #189 en borrador. No fusionar a `main` hasta completar la cadena funcional, como aprobó el propietario del proyecto.
