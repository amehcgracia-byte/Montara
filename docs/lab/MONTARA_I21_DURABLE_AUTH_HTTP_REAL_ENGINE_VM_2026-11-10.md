# I21 — Conectar I13 (HTTP), I18/I19 (ledger) y Engine REAL con cierre atestado

**Fecha:** 2026-11-10. **Estado:** contrato control-plane + **dos pruebas físicas PASS** en VM FER, con OIDC Google **sintético firmado**; no desplegado en beta pública y **no apto aún para tenants reales**.

## Visión del hito

El I20 ya probó HTTP firmado → guard del proyecto → Engine Linux real, pero su ejecutor de laboratorio no escribía el ledger durable I18/I19. Ahora el flujo I21 integra **en una sola petición** `POST /urano/v1/projects/<uuid>/open` → `OwnerEngineGateway` (I13) → `GatewayJobBridge` (nuevo) → `TrustedJobAdmission` (I19) → `JobRecoveryLedger` (I18) → transport Linux I20 → **Engine auténtico pinneado**, y su posterior cierre, sin nuevas rutas de usuario ni cloud/provider específico.

## Código y contratos

- `urano/gateway_job_bridge.py`: nuevo `GatewayJobBridge`, ejecutor **de confianza** compatible con I13, usando una referencia `ActivationTicket` suministrada por el backend y **no por el navegador**. `TrustedJobAdmission` garantiza propietario, persistencia, generación/fencing y respuesta fail-closed. `_TicketBroker` solo permite iniciar el proyecto reservado cuyo owner+project corresponden al ticket; no recibe rutas desde HTTP.
- Una reserva I13 `switching` solo pasa a `ready` tras confirmación del Engine físico y tras pasar a `running` el job I18. Se impide una segunda apertura de un propietario que ya tiene trabajo activo para que no mate el Engine anterior ni cree otro runtime. Las cuentas diferentes mantienen ranuras y jobs separados.
- Ante fallo de apertura, I19 exige parada y prueba de limpieza antes de liberar. Se descubrió en pruebas una **inconsistencia real**: el ledger se quedaba en `stopping` por limpieza no verificada, pero la guardia I13 podía pasar a `idle`. Corregida: `GatewayJobBridge.abort` consulta `JobRecoveryLedger.unverified_for_owner`. Si existe un job sin limpiar, **eleva error**, de modo que I13 retiene `switching` (bloqueado) en lugar de aceptar un nuevo proyecto como si nada ocurriera.
- `close_trusted` cierra el job mediante broker, actualiza el ledger a `stopped` **solo** con verificación de cgroup vacío, e invalida la generación de la guardia I13 a `idle`. No hay una operación pública de cierre desde el navegador en esta etapa.
- **Arranque:** `GatewayJobBridge.prepare` invoca `startup_reconcile()` de I19 antes de admitir jobs. Los huérfanos no se liberan sin comprobación por un broker de confianza. El mapeo `job_id` ↔ unidad temporal/ActivationTicket **no está persistido aún**: ante crash se bloquea por seguridad, pero falta una reconciliación autónoma en producción. **No desplegarlo con propietarios reales**.

## Evidencia física en VM

`tests/urano_i21_signed_http_fenced_real_engine_lab.py` usa las herramientas reales de I13, I18/I19 y el ejecutor limitado I20 en entorno Linux, y solo un OIDC **fake firmado** para no necesitar una cuenta privada de Google. Crea proyecto y base SQLite efímeros, dos owners de test, y verifica apertura ajena HTTP **404**.

| Ejecución | Hasta HTTP `ready` | Abrir + cerrar | Resultado |
|---|---:|---:|---|
| Física I21 A | **2,762 s** | **5,889 s** | Engine abierto, job `running`, cierre `stopped`, guardia `idle`, cgroup vacío |
| Física I21 B | **2,416 s** | **5,548 s** | Mismo resultado, sin unidades ni workspaces residuales |

**Picos/mediciones**: la prueba usa `MemoryMax=512MiB`, `TasksMax=32`, `CPUQuota=100%` del ejecutor I20; no atribuirle pico de memoria de un render. Sin vídeos, FFmpeg no ejecutado durante esta apertura, sin Companion y sin MP4. El UID real de host del laboratorio sigue siendo el mismo operador; user/mount/net/pid namespaces y cgroup aportan barreras, pero **no satisfacen por sí mismos el nivel de aislamiento multiusuario de la beta real**.

Pruebas de control: `tests/test_urano_gateway_job_bridge.py` comprueba apertura/rechazo extranjero, segunda apertura del mismo owner preserva el worker activo, dos propietarios separados, bloqueo doble (I13 + I18) ante limpieza no atestada, y huérfanos de reinicio. Suite I21 + I18 + I13 + I19 + U13: **30 tests locales PASS** tras regresiones. CI dedicada **solo ejecuta tests offline**, no invoca systemd ni instala componentes.

## Resultado de inspección de identidad Linux en la VM (sin modificar el host)

En la VM Ubuntu 24.04, el usuario de laboratorio es UID/GID 1006. `unshare --user --map-root-user` muestra un mapa **UID 0 interno → UID 1006 del host (rango 1)**. Existen entradas `subuid/subgid` para ese usuario (rangos de 65.536), pero **no están instaladas `newuidmap` ni `newgidmap`**, necesarias para delegar rangos arbitrarios mediante el modelo rootless tradicional. Un intento inofensivo de ejecutar un servicio temporal `systemd --user` con `DynamicUser=yes` finalizó con `status=217` y sin ejecutar el proceso. No se instaló nada ni se cambió configuración de cuentas/cgroups.

**Conclusión de seguridad:** las pruebas I15–I21 son una demostración real de aislamiento de rutas/red/PIDs y límites por cgroup, pero **no demuestran identidades host segregadas para dos tenants**. Las alternativas que merece comprobar un operador autorizado son: (a) broker mínimo con UIDs reales diferenciados y control de cgroups, (b) un runtime OCI rootless con mapeos subordinados *verificados* y política de recursos; ambas requieren una validación de privilegios, permisos y teardown antes de activar el Owner. La pertenencia del usuario de la VM al grupo `lxd` no es por sí sola una aprobación de usar LXD: ese grupo puede conceder privilegios muy amplios y no se habilitará ningún servicio por esta vía.

## Bloqueadores concretos antes de Bandera 1 visible al usuario

1. **Broker de producción con aislamiento por tenant**: separar UID host del Owner/tenant o escoger runtime OCI equivalente, límites/cgroup/seguridad de kernel, scopes estrictos y un control-plane que no posea acceso directo indiscriminado al home ajeno. Evaluar el menor coste operacional sin atarnos a GCP ni Docker.
2. **Recuperación de unidades**: guardar atómicamente la identidad física del job en el ledger y recuperarla tras reinicio. El booleano `verified_cgroup_empty` solo acredita el resultado de un transport confiable, nunca una prueba del ledger por sí solo.
3. **Coherencia tras fallos de transacción**: `RuntimeActivationGuard` y `JobRecoveryLedger` son dos SQLite independientes. Su lógica actual falla cerrada en errores de limpieza, pero falta recuperación automática de estados inconsistentes por crash entre los ACK.
4. **Feature flag en Owner C8**: el servicio 8115, páginas y Worker Cloudflare no han sido alterados. Habilitar el endpoint I13 solo cuando el broker real cumpla requisitos anteriores, y probar **con la cuenta Google auténtica del usuario**, sin acceso cruzado.
5. Después, **Companion Windows → proxies → Stage → receta → MP4 local**. No confundir «Engine abierto» con «editor y render completos».

## CI preexistente

I20 #198 tenía CI específica PASS y las U12/auth PASS. E2E Linux general fallaba en `session` por `test_c6_https_google_preflight.py` que exige `companion.trusted_signed_receipt_origin` ausente **también** en I19 anterior, con Companion y test heredado idénticos. Se documentó, sin modificar el módulo de Chema ni declarar E2E global aprobado. I21 no pretende corregir un fallo preexistente ajeno a la conexión Engine.

**Integración:** I21 queda en PR separada hacia `fernando/integracion` y la PR #189 hacia `main` sigue en borrador. Ningún cambio a `main` sin el recorrido funcional completo y aprobación escalonada con Chema.
