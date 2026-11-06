# URANO U13D2B — Puerta de aislamiento de contenedores

**Fecha:** 2026-11-06. **Estado:** PR DRAFT. **CI específica verde** en [run 42222303679](https://github.com/amehcgracia-byte/Montara/actions/runs/42222303679) (tests de contrato y dos contenedores Docker reales). E2E general separado y pendiente de cierre en última consulta. **No desplegado, no integrado con Engine real y NO apto aún para beta pública**.

## Decisión de arquitectura
Por indicación del propietario, **no habrá cola global obligatoria entre usuarios**. Una cuenta puede tener un trabajo dentro de su runtime mientras otras cuentas utilizan sus propios procesos simultáneamente. Los bloqueos U13B/U13D aplican únicamente a operaciones incompatibles del mismo runtime.

## Implementación concreta
- `urano/container_isolation.py`: generador de argumentos explícitos para Docker. Imagen requerida con digest sha256 inmutable; un contenedor por identidad con nombre restringido; root filesystem read-only; `--network none`; `--cap-drop ALL`; `no-new-privileges`; límites de memoria, CPU y PIDs; UID/GID no root; /tmp tmpfs temporal y montaje **único** de datos del propietario en `/workspace`.
- `tests/test_urano_container_isolation.py`: tests de contrato y rechazo de configuración insegura (tag mutable, UID root, root symlink, mounts fuera del workspace, recursos fuera de rango).
- `tests/urano_docker_isolation_smoke.py`: prueba negativa ejecutada con Docker **real** en CI: crea carpetas sintéticas Alice/Bob, arranca dos contenedores en paralelo y exige que cada uno lea su fichero pero no los ficheros de otro workspace. Sin credenciales, medios reales ni servicios persistentes.
- Workflow `urano-u13d2b-container.yml`: tests acumulados U10–U13D2B y Docker smoke independiente, contenedores efímeros.

## Límites críticos
**No se puede afirmar aislamiento de producción todavía.** La prueba usa la configuración de Docker runner hospedado, no el host real; no mide escapes del kernel, ACL de host, sockets extra ni vulnerabilidades de imágenes. El orquestador de confianza es una pieza aún pendiente: los nombres y rutas no deben venir de HTTP ni del usuario; una identidad no puede elegir un workspace ajeno. Antes de conectar la infraestructura, se exige un directorio privado con titularidad correcta y reglas de montaje, además de aislamiento de engine, archivos temporales, procesos FFmpeg, render/export y almacenamiento global.

Tampoco hay lanzamiento automático de `PrivateWorkerSupervisor` dentro de estos contenedores, heartbeat, recuperación ante caída del orquestador, registro de eventos, protección de secretos, ingress autenticado ni trabajo de vídeo real. En particular, el supervisor U13D implementa comunicación stdin/stdout local; para Docker se debe conectar ese protocolo sin exponer un servicio público y garantizar el cierre y la revocación de generaciones de U13B.

## Próximas pruebas
1. **Gate U13D2C**: prueba de acceso cruzado negativa entre workers con directorios, identidades y permisos reales; conectar supervisor U13D a contenedor sin Docker socket ni rutas host, proceso detenido y estado invalidado al caer.
2. **Gate U13E**: dos proyectos sintéticos sobre Engine real + un vídeo de prueba con apertura, cambios, export, cierre y recuperación, dos cuentas sin fuga.
3. **Beta Chema**: solo con TLS privado, credenciales individuales fuertes, autenticación y controles de acceso revisados, recursos limitados, datos de prueba, smoke E2E y rollback.

La arquitectura sigue sin cola FIFO global y conserva el plan de pruebas de capacidad **1,2,4,8,10,25 usuarios**, con carga compartida Companion/servidor y sin suponer capacidad antes de medir.

**No tocar `main`, producción Vercel, Cloudflare Pages estático, servicios FER/JM, DNS ni datos.** Documentar resultados CI reales y actualización del handoff.

## Historial de fallos detectados y corregidos en CI

- Primera ejecución: el script independiente no encontraba el módulo `urano`; corregido usando `PYTHONPATH=.` exclusivamente para la prueba.
- Segunda ejecución: Docker rechazó `--mount type=bind,...,rw`, porque `rw` no es un campo válido en esta sintaxis. Docker usa bind RW por defecto si no se especifica `readonly`. Corregida la construcción del argumento y el contrato asociado.
- Tercera ejecución: **PASS** para las dos pruebas (contrato y Docker real) en run 42222303679; dos contenedores sin red, sin root y sin montajes cruzados de las carpetas ficticias. Esto NO certifica un entorno multiusuario comercial.
