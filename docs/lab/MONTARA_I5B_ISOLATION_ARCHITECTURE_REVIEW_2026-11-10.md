# MONTARA · I5B — Auditoría de aislamiento y arquitectura del Engine por propietario

**Fecha:** 10 de noviembre de 2026. **Tipo:** decisión técnica y revisión de evidencia, **solo documentación, sin despliegue**. **Base:** `fernando/integracion` tras I5A. **NO** se ha elegido ni instalado todavía ningún ejecutor.

## Resumen de decisión

**Recomendación provisional para la beta inicial de 2–4 cuentas confiables:** procesos Engine *separados por identidad Unix real* (una cuenta de servicio no privilegiada por propietario, NO la cuenta del portal), gestionados por unidades **systemd del sistema** y un **broker administrador con funciones estrictamente permitidas**. El broker es un componente de infraestructura distinto de la app web, y **jamás** ejecuta rutas, comandos, nombres de cuenta o flags propuestos por el navegador. No cambiar `OwnerRuntimeController` para confiar en un subprocess sin pruebas. Este diseño reutiliza I4 y U13D.

**Alternativa preferente si no podemos demostrar los límites de cuentas Unix, o se amplía a cuentas no confiables:** contenedores LXD **no privilegiados** por propietario, con `security.idmap.isolated=true`, sin acceso del proceso web al socket administrador, limitaciones CPU/RAM/PIDs, espacios y secretos privados, sin red cuando la integración Engine lo permita, y pruebas negativas reales. La VM ya tiene el snap LXD, pero NO se ha configurado ni lanzado un contenedor.

**Propuesta no recomendada:** subprocesses de dos propietarios **bajo el mismo UID**: sus permisos y ficheros son compartidos. Docker no es requisito de funcionalidad ni alternativa a considerar instalada en la VM; microVM/gVisor/nsjail son opciones interesantes para otro escenario pero, ahora, elevan la complejidad sin prueba de compatibilidad con Engine/FFmpeg.

## Qué estaba resuelto en nuestras ramas

| Componente | Evidencia histórica | Estado |
| --- | --- | --- |
| Catálogo propiedad | U10–U12, en main; I1–I3 | Integrado en FER |
| Binding propietario ↔ Engine | U13A #91, I4 | Pruebas de contrato, no apertura vía HTTP |
| Reserva persistente / generación | U13B #92, I4 | Probada, no recuperación automática de caída del propio supervisor |
| Protocolo Engine separado | U13C #93, I4 | Ensayo con Engine falso y pruebas anteriores de Engine real |
| Supervisor POSIX | U13D #94, I4 | Handshake, cierre y timeout, **sin aislamiento UID** |
| No cola global | U13D2A #95, I5A | Prueba de dos procesos concurrentes, no benchmark productivo |
| Contenedores Docker con controles | #96–#98, U16B #128, U22 #137 | CI real de runner aislado, no instalación GCP |
| Google → worker → Stage | U19–U22 #134–#137 | Contratos/laboratorio; `OwnerRuntimeController` acoplado a `ContainerWorkerBridge` Docker |
| Acceso Google en VM | C8 / I3 | Portal privado funciona, Engine no aprovisionado |

Los informes **completos** U13A–U13D, U13D2A/U13D2B, U16B y U19 advierten expresamente que separar procesos no es separar los permisos del sistema. El aparente diseño resuelto en Docker CI debe recibir un ejecutor nuevo y pruebas en host real antes de activar cuentas.

## Comprobaciones no destructivas GCP — 2026-11-10

- Usuario de pruebas `fgardel00`, UID 1006, grupos incluyendo `lxd`. Los HOME de tres operadores (`jm`, `fer`, `fgardel00`) muestran permisos 0750. Esto **no** equivale a aislamiento de cuentas de usuarios finales ni autoriza leer ficheros de otros operadores.
- VM: **8 vCPU, 31 GiB de RAM, ~29 GiB disponibles** al verificar, sin swap, cgroups v2; disco de 96 GB con ~51 GB libres en la inspección.
- `systemd-run`, `setpriv`, `prlimit`, `unshare` presentes. Docker/Podman CLI ausentes.
- LXD snap 5.21.9 instalado; `lxc list --format=json` devolvió `[]`. No se crearon ni iniciaron contenedores.
- `kernel.unprivileged_userns_clone=1`, `kernel.apparmor_restrict_unprivileged_userns=0`, pero `unshare --user --map-root-user --mount-proc …` **falló** escribiendo `uid_map`: `Operation not permitted`. **No atribuirlo automáticamente a AppArmor**: comprobar restricciones del sistema, perfiles, UID map y filtros si se retoma la opción rootless. **No debilitar sysctls ni AppArmor** para forzar el resultado.
- Portal real de FER: `/healthz` HTTP 200, servicio activo. Sin cambios de puertos, permisos, kernel, secretos, servicios de Chema o almacenamiento de medios.
- La cuenta `fgardel00` forma parte de `lxd`; ese grupo tiene potencial de administración amplia. **Nunca otorgar el socket LXD ni `sudo` al proceso de la aplicación web.**

## Diseño de referencia propuesto para procesos por UID

1. Un **owner_id interno** (derivado de Google `sub` validado) corresponde a una identidad de servicio del SO cuya asignación es realizada por infraestructura confiable, nunca por datos del navegador.
2. Portal HTTPS recibe cookie de sesión y CSRF; resuelve `project_id` en catálogo y autorización; **no recibe ni admite rutas Engine ni comandos**.
3. Un broker privado, con API mínima de operaciones conocidas (`start(owner, project)`, `state`, `cancel`, `stop`), comprueba los vínculos autorizados antes de pedir una unidad systemd de sistema; no puede utilizarse para ejecutar comandos arbitrarios. El Engine puede usar stdio/un socket Unix privado detrás de este control.
4. Unidades systemd de sistema con UID distinto, grupos mínimos, `NoNewPrivileges`, protecciones filesystem que realmente apliquen, `WorkingDirectory` privado, directorios de estado con permisos restrictivos, `TasksMax`, `MemoryMax`, `CPUQuota`, `KillMode=control-group`, `TimeoutStopSec` y política explícita de red según pruebas de Engine. Comprobar cuáles funcionan en el host real; no afirmar aislamiento por declarar settings.
5. Cada Engine/FFmpeg solo recibe proxies verificados y metadatos de su propietario. El render de originales sigue en Companion local. Nunca montar HOME ajeno o el directorio de secretos de Google en un worker.
6. Catálogo y reserva de ejecución deben sobrevivir caídas; un estado `ready` solo se restablece tras verificar *live worker*, UID, cgroup y proyecto activo. Al cancelarse o morir, comprobar que FFmpeg descendiente no sigue escribiendo antes de invalidar ticket.
7. Cuotas y duración razonables para la beta; sin cola global obligatoria, pero admisión por disponibilidad y capacidad host para evitar que varios trabajos tumben la VM.

**Importante:** systemd documenta que opciones de filesystem como `ProtectHome` no están disponibles en unidades del **gestor de usuario**. El diseño requeriría gestor del sistema o alternativa equivalente revisada; no se despliega mediante el servicio de usuario existente sin esos controles.

## Matriz de alternativas

| Vía | Encaje beta | Seguridad | Complejidad / dudas |
| --- | --- | --- | --- |
| Subprocess mismo UID | No | Insuficiente para proyectos personales | Sencillo, rechazado para dos cuentas |
| **UID separado + systemd** | **Candidato principal** | Separación DAC Linux, reforzable con unit sandbox y MAC; **no es VM** | Provisionado/root broker; permisos, reinicio, cgroup, FFmpeg, permisos de montaje |
| **LXD no privilegiado aislado** | **Plan B fuerte** | user namespaces e idmap aislado; perfiles seccomp/AppArmor, límites | Administración LXD confiable, ciclo de vida, imagen y almacenamiento |
| Docker aislado por owner | Referencia de CI | Contenedores con restricción positiva | No instalado en GCP; instalar y operar un nuevo daemon |
| gVisor (runsc) | Revisión futura | Kernel de aplicación en userspace | Compatibilidad y overhead de syscalls, necesidad de runtime/OCI |
| Firecracker/microVM | Escalado futuro | VM individual, separación fuerte | KVM/anidamiento, imágenes, memoria, operación; sobredimensionado para 2–4 |
| nsjail/bubblewrap rootless | Investigable, no asumido | Namespaces/seccomp condicionados al host | Rootless UID map **falló en nuestra VM**; no cambiar seguridad del host para hacerlo pasar |

## Papers / investigación contrastada

1. **LITESHIELD (USENIX ATC 2025)**, arquitectura de aislamiento de contenedores con servicios de microkernel en espacio de usuario. Interesante para explorar a largo plazo; investigación, **no** producto listo para instalar ni integración con FFmpeg verificada. https://www.usenix.org/conference/atc25/presentation/manakkal
2. **ParaCell (arXiv, mayo 2026)**, sistema experimental de contenedores seguros y gestión de memoria; evidencia sobre el compromiso aislamiento-rendimiento, **no** motivo para reemplazar servicios actuales. https://arxiv.org/abs/2605.20906
3. **Isolation Failure From Shared Storage (arXiv, julio 2026)**, demuestra canales laterales de caché compartida incluso en ciertas configuraciones contenedor/VM: recordar que aislamiento no es una afirmación absoluta. https://arxiv.org/abs/2607.17518
4. **gVisor (proyecto Google)**: ejecución con kernel de aplicación en userspace y `systrap` apta para hosts dentro de VM; documentación advierte limitaciones de compatibilidad y overhead de syscalls. https://gvisor.dev/docs/ y https://gvisor.dev/docs/architecture_guide/performance/
5. **nsjail**: namespaces, seccomp y límites, pero requiere confirmar permisos de kernel y políticas locales. https://github.com/google/nsjail

**Conclusión de la revisión de papers:** no se encontró un candidato emergente que, hoy, supere claramente en simplicidad y adecuación las alternativas nativas Linux/systemd/LXD para nuestra beta. Los papers orientan a futuro; no certifican compatibilidad con Zucker Engine, FFmpeg, acceso a proxies ni nuestra VM.

## Fuentes técnicas primarias

- systemd exec sandbox y DynamicUser: https://freedesktop.org/software/systemd/man/latest/systemd.exec.html
- LXD Security: https://canonical.com/lxd/docs/default/explanation/security/
- LXD Hardening: https://canonical.com/lxd/docs/default/howto/security_harden/
- LXD resource limits: https://canonical.com/lxd/docs/default/reference/instance_options/
- Incus socket privilege warning (aplicable como precaución conceptual): https://linuxcontainers.org/incus/docs/main/explanation/security/
- Linux kernel namespaces resource control: https://kernel.org/doc/html/latest/admin-guide/namespaces/resource-control.html

## Puertas de aceptación I5B (antes de conectar Engine real)

1. Aprobación del modo elegido y del alcance de configuración host. No crear cuentas de servicio ni unidades privilegiadas sin permiso.
2. Experimento **aislado de dos identidades** y dos carpetas sintéticas: acceso al propio permitido, acceso al otro denegado, acceso a secretos portal denegado; no ejecutar procesos como root.
3. Crash/cancel con un árbol de procesos que incluya FFmpeg falso/real no destructivo, verificar ausencia de huérfanos y generación de runtime invalidada.
4. Límite por worker de CPU/RAM/PIDs, registro y recuperación de states al reiniciar, no interferencia con `jm` ni `fer`.
5. Un solo Engine real + proyecto y proxy sintético en entorno separado; después dos Engines y E2E Stage → descriptor firmado → Companion local. Validar identidad proxy↔original, prohibición de subida silenciosa.
6. Coordinar PR de producto con Chema al refrescar main, preservar submódulos y Companion Mac vigente; **nunca** sobrescribir ramas históricas.
7. Backups, retención limitada y rollback antes de beta pública.

**Estado:** revisión técnica documentada; ninguna prueba de aislamiento fuerte ni despliegue realizado en este paso.
