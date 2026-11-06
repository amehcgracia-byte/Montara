# URANO U13D2C — puente supervisor ↔ contenedor privado

**Fecha:** 2026-11-06. **Estado:** PR DRAFT; pruebas **PASS** en [GitHub Actions run 42224036778](https://github.com/amehcgracia-byte/Montara/actions/runs/42224036778): jobs `contracts` y `container-bridge` con Docker real ambos SUCCESS. No desplegado.

## Contexto y objetivo

Tras U13D (supervisor de procesos), U13D2A (prueba de concurrencia sin cola global) y U13D2B (dos carpetas invisibles entre contenedores), faltaba conectar el protocolo del worker a un contenedor de verdad. Esta es la primera integración del **supervisor de sesiones** con el ciclo de vida de un contenedor, todavía con un worker sintético.

**Regla conservada:** los bloqueos son *por runtime/propietario*; jamás se crea una cola global FIFO por defecto. La medición de capacidad representativa futura es **Companion + servidor** por modo de trabajo, no el 100 % del render dentro de Docker.

## Entrega

- `urano/container_worker_bridge.py`: `ContainerWorkerBridge` recibe solo datos resueltos por infraestructura de confianza: owner, runtime registrado U13B, workspace privado, imagen Docker por digest sha256, nombre restringido y argv de worker predefinido. Construye Docker con la política U13D2B, añadiendo stdin interactivo y cidfile privado. No se monta Docker socket ni se abre puerto o API HTTP.
- `start()`: exige runtime idle, lanza Docker, recibe handshake JSON y comprueba identidad/estado de contenedor mediante inspect del CID exacto y red `none`; no equipara el PID dentro del contenedor con el del cliente Docker.
- `open_project(project_id)`: se autoriza con U13A y se reserva con U13B; solo se envía un nombre de carpeta resuelto en backend. Tras mensaje de apertura y comprobación del contenedor se confirma en U13B. Un fallo de apertura detiene el contenedor y no declara proyecto listo.
- `stop()`: `docker rm -f` por CID, verifica su ausencia con `docker inspect` y **solo entonces** invalida estado/generación en U13B. Si no puede confirmar la desaparición del contenedor, falla cerrado: no libera el runtime. Recurso Docker es externo y requiere orquestador de confianza fuera de los procesos de usuario.
- `tests/test_urano_docker_bridge.py` usa imagen Python Alpine *real* fijada por digest y crea únicamente proyectos ficticios. Tres escenarios: proyectos antiguo/reciente, protección de cuenta ajena, bloqueo propio durante trabajo.
- `.github/workflows/urano-u13d2c-bridge.yml`: contratos acumulados de URANO y gate Docker real separado.

## Lo que sigue SIN resolver

1. **No corre todavía el Engine real dentro del contenedor**: el bridge está demostrado, si la CI pasa, con worker sintético. U13C sí probó Engine real en proceso separado Linux, pero esos dos gates aún no están integrados en una ejecución común.
2. No hay orquestador de múltiples propietarios bajo permisos distintos ni contenedores sin salida de red para Stage/Push/Show; comprobar necesidades autorizadas de red/almacenamiento de cada modo. No montar originales de otro usuario, secretos, sockets o rutas de host.
3. **No hay reconciliación automática tras caída del proceso supervisor**, ni heartbeats, ni manejo de FFmpeg/subprocesos de export real, ni pruebas de supervivencia del Engine en render bajo cancelación. El `--rm` del contenedor y `docker rm -f` no sustituyen una estrategia de limpieza de trabajos externos.
4. La UI U12b sigue sin API de activación y sin editor; la autenticación U12 no está endurecida para público.
5. El propietario del proyecto no es un sandbox de seguridad por sí mismo: los UID dentro del contenedor, permisos de volumen, cgroups, vulnerabilidades del kernel y acceso al Docker daemon tienen que ser revisados en el host final.
6. No afirmar que una prueba Docker sintetizada mide cuántos usuarios y renders admite la máquina. La capacidad debe medirse después con **Companion real + servidor** y escalera 1/2/4/8/10/25 simultáneos.

## Gate siguiente

U13D2D/U13E: montar Engine real en imagen de pruebas con rutas dedicadas y ejecutar apertura + edición/export con vídeos sintéticos en un contenedor privado, con proceso supervisor, comprobación de cierre limpio, aislamiento entre dos propietarios, pruebas en navegador y recuperación. Sólo después evaluar beta privada de Chema con autenticación fuerte, HTTPS y rollback. Chema no tiene aún una URL de esta rama; la URL Pages de Cloudflare es un benchmark estático independiente.

**No tocar main, los servidores de Chema o FER, Vercel, Cloudflare ni DNS.** No fusionar pila completa sin revisión y CI.
