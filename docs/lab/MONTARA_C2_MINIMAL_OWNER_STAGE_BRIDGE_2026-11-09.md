# MONTARA · C2 — Identidad verificada → proyecto → Engine privado → Stage

**Fecha:** 2026-11-09. **Base:** C1 [PR #140](https://github.com/amehcgracia-byte/Montara/pull/140) (`94fe47c536763d27c1b3dd766e032ec1c6531351`), derivada del `main` existente. **Estado:** integración opt-in de laboratorio; no fusionada ni desplegada.

## Por qué esta es la siguiente pieza de la arquitectura mínima

En lugar de fusionar la pila completa U15→U22 o construir otra app:
- Se mantiene el `ProjectCatalog` y el `http_projects.py` ya presentes en `main`.
- Se mantiene el login Google/PKCE y el mapeo persistente Google `sub` → dueño privado de C1.
- Se importa **solo** la última implementación coherente del control privado U19/U20: `EngineProjectRegistry`, `RuntimeActivationGuard`, `ContainerWorkerBridge`, supervisión, protocolo fijo de Engine, rutas HTTP owner-only y descriptor de cortes seguro.
- Se conecta todo en la **misma fábrica opcional** `create_owner_api(..., runtime_controller=...)`, sin levantar otra web, sin que el usuario pueda elegir contenedor/carpeta/imagen y sin activar nada por defecto.

El usuario autenticado puede activar únicamente proyectos vinculados a su propio worker previamente provisionado por infraestructura confiable. Puede iniciar `Stage Ingest` y consultar su estado con rutas HTTP restringidas; obtiene únicamente un descriptor sin rutas locales. Sin `runtime_controller`, **ni siquiera se registran esas rutas**. La sesión no provisiona Docker ni otorga acceso genérico a Engine, disco o medios.

## Archivos incorporados

**Runtime opt-in (nuevos respecto a C1, preservados de U20):**
`urano/container_isolation.py`, `urano/engine_bindings.py`, `urano/runtime_activation.py`, `urano/private_worker_supervisor.py`, `urano/engine_worker_process.py`, `urano/container_worker_bridge.py`, `urano/owner_runtime_controller.py`, `urano/http_owner_runtime.py`, `urano/companion_handoff.py`.

**Única modificación directa al código C1:** `urano/minimal_owner_api.py` acepta un `OwnerRuntimeController` opcional, le pasa **el mismo catálogo SQLite** y **la misma sesión** que utiliza la autenticación de Google. No se modifica `app.py`, `web/montara.js`, `companion/companion.py`, Engine ni Mixer.

**Tests:** `tests/test_c2_google_to_private_engine.py` conecta login PKCE/JWT firmado ficticio → dueño real persistente → catálogo → guardia → worker emulado (aislamiento y CSRF); además se conservan los tests negativos U19/U20 y su gate real Docker con dos proyectos Stage.

## Puertas verificables

1. **CI rápida:** dos usuarios Google firmados sintéticos → dos dueños de sesión reales → dos proyectos en el mismo SQLite → cada uno activa su worker privado; proyecto extranjero denegado antes de arrancar, CSRF/Origin fallidos, cierre de A no afecta a B, logout revoca. Ruta de Engine **ausente** por defecto en C1. Validar API Ingest y descriptor sin `source_files`.
2. **CI pesada:** 2 Engine Docker reales aislados y 2 Ingest sintéticos hasta `done`, manteniendo los tests U20 previos; **en runner compartido**, sin servidor remoto ni macOS.
3. **Conservación de main:** sin cambios de runtime existente ni nueva UI; motor/worker solo activables con provisión confiable. No desplegar en VM o tocar `8101/8102/8103`.
4. **Companion siguiente:** traducir los descriptores owner-only a un render de originales locales, reutilizando U21 y los tests sin rutas, **sin cargar los vídeos originales al servidor**, primero en un recorrido completo mínimo desde web/HTTPS de ensayo.

## VM de prueba: comprobación pasiva de capacidad

El 9 de noviembre se inspeccionó **solo lectura** `montara-test-gcp-static` por Gateway: 8 vCPU, ~32 GB RAM, disco virtual 100 GB y `df -h /` **96 GB montados, 33 GB usados, 64 GB disponibles (34 % de uso)**. Los servicios existentes continúan escuchando en loopback `8101`, `8102` y `8103`. La VM `montara-test-gcp` está registrada, pero su inspección quedó en curso y **no se atribuyen los valores de la primera a la segunda**. No se hizo ningún despliegue, contenedor, instalación, restart ni limpieza en ninguna.

La autorización del usuario para utilizar la VM **no obliga a cargarla con pruebas** antes de aprobar un entorno de aislamiento: la CI desechable ya proporciona los dos Engine. Si más adelante se usa, hacerlo en **un directorio y puerto nuevos explícitamente aislados**, con límites de CPU/RAM, disco y limpieza y sin tocar servicios.

## Riesgos que todavía no hemos resuelto

- En el runtime U19 la provisión de workers se mantiene en memoria del proceso de laboratorio; no es aún un sistema multiproceso tolerante a reinicios ni una implementación de cuotas persistentes para beta pública.
- El `Stage` real de CI utiliza **fuentes sintéticas generadas en el contenedor**, no proxies reales de un Companion remoto con huella de origen extremo a extremo.
- Google real requiere callback HTTPS, configuración segura de secretos y allowlist de personas invitadas, sin usar proveedor sintético de test.
- Los descriptores de U20 son **no renderizables** hasta verificarse los originales en Companion por el traductor U21. La CI U22 demostró MP4 con dos procesos locales, pero no dos Macs físicos ni transporte WAN real.
- El frontend de `main` ya pide confirmación explícita para subir originales, pero la política de **bloqueo por defecto también en backend** debe cerrarse antes de aceptar usuarios externos.
- Cancelación, reintentos, límites de cuotas, migración de base y recuperación quedan para la aceptación real, sin abrir una nueva investigación de cada componente.

## Decisión de siguiente paso

**No** otra etapa de veinte micro-PR. Tras verificar el CI de C2, preparar una integración concreta **web/HTTPS Stage→Companion** sobre base actual con protecciones; luego ensayar un usuario real y después dos en una VM de prueba aislada con Companion en Mac. Conservar las pruebas de telemetría U17B/C solo para diagnosticar el tráfico CPU local↔servidor, no para justificar otro laboratorio.

**No fusionar ni desplegar esta PR sin revisión de Chema.**
