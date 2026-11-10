# MONTARA I11 — Revisión objetiva de aislamiento, coste y ciclo de vida del Engine

**Fecha:** 2026-11-10. **Estado:** decisión arquitectónica provisional fundamentada; **sin instalar Docker, LXD ni cambiar el Engine desplegado**. **Base:** `fernando/integracion`. Evaluación específica para arquitectura *local-first* con Companion Windows/macOS, backend Linux de 8 vCPU / 31 GiB RAM / 96 GB disco, ~49 GB libres al examinar.

## 1. Pregunta correcta

Separar tres conceptos:
1. **Cuenta de propietario:** persiste en catálogo y autenticación; **no requiere ejecución permanente**.
2. **Proyecto:** registro duradero (UUID, receta, revisión, referencias verificadas y permisos); **no exige un directorio ni VM por cuenta**, aunque los archivos temporales que se precisen tienen aislamiento y vida limitada.
3. **Ejecución Engine (job):** activo solo cuando una tarea real lo necesita. Puede ser un proceso Linux, contenedor OCI o worker remoto, con capacidad y límites por job. Al terminar, cerrar procesos y borrar temporales según TTL sin eliminar proyectos. Los originales permanecen en Companion y los exports finales son locales.

**Resultado:** No plantear "Docker por usuario permanente" como requisito. Un *worker efímero por job*, o un *worker por propietario activo* reutilizable con TTL, es una política a medir; la seguridad exige aislamiento de contextos incluso cuando se reutiliza. El cambio de proveedor GCP/Oracle/Azure y de frontend Cloudflare/Vercel no debe alterar contratos API, proyectos ni recetas.

## 2. Evidencia de los ensayos históricos

- **U13D2B** (`docs/lab/URANO_U13D2B_CONTAINER_ISOLATION_2026-11-06.md`): contenedores Docker Linux de prueba con mounts exclusivos de workspace sintético, `--network none`, raíz read-only, usuario no root, sin capabilities, `no-new-privileges`, límites CPU/RAM/PIDs, pruebas de carpetas Alice/Bob inaccesibles entre sí. En *GitHub Actions*, NO en VM GCP.
- **U16B** (`docs/lab/URANO_U16B_TWO_PRIVATE_REAL_ENGINE_2026-11-08.md`): 2 Engine reales abriendo proyectos en paralelo dentro de contenedores, identidades Google falsificadas en laboratorio pero JWT criptográficamente validados. **No** render simultáneo, no Companion físico, no proxy ni MP4 local. Usó `0777` en carpetas temporales del runner de CI (inaceptable como esquema de permisos para producción).
- Imagen de CI/Engine `Dockerfile` basada en **`python:3.11-slim-bookworm`**, con etapa Node 22 Bookworm para obtener Deno, instalación FFmpeg/fuentes/bibliotecas, paquetes Python y copia de código más submódulos Engine/Mixer. Es un **Linux Debian** dentro de contenedor; no instala Windows/macOS ni ejecuta Companion. **No existe medida registrada de su tamaño comprimido/descomprimido, memoria RSS por worker ni número real de cuentas soportadas.** La imagen general actual incluye piezas que se podrían evitar en una imagen worker más delgada; optimización pendiente de medir, no hecho.
- `container_isolation.py` define el comando seguro; `ContainerWorkerBridge` aplica el protocolo privado. Los resultados no acreditan un daemon Docker de producción seguro ni política de cancelación para FFmpeg de datos reales.
- **Estado VM read-only 2026-11-10:** no hay CLI Docker/Podman; LXD snap y `lxc` presentes, 0 instancias. La `/dev/kvm` no existe en el host observado; el intento *rootless* `unshare --user --map-root-user` falla en `uid_map` con EPERM a pesar de sysctl de userns activo. No debilitar kernel/AppArmor ni solicitar nested virtualization sin motivo; rootless Docker **no debe asumirse disponible**. VM compartida con servicios de Chema; no instalar ni inicializar runtimes privilegiados en esta fase.

## 3. Modelo de espacio (distinto de CPU/RAM)

**Contenedores OCI/Docker:** una única imagen base inmutable en disco, compartida por capas copy-on-write para todos los contenedores del mismo host; cada ejecución añade una capa fina y los datos temporales propios. No multiplicar tamaño de imagen × usuarios para estimar capacidad. Aproximación:

`disco_total ≈ imágenes_únicas + bases/catálogos + Σ(proxies temporales de trabajos) + Σ(capas escritas) + logs + backups + margen`.

CPU/RAM **sí son consumidos por cada proceso de Engine/FFmpeg realmente activo** y por cachés/memoria de páginas parcialmente compartidas; los límites de cgroup controlan abuso pero no crean recursos ni garantizan rendimiento. La política que más impactará capacidad puede ser **cuántos Engine simultáneos** y **qué trabajo permanece en Companion**, no el overhead de Docker. Medir caché caliente/fría y bytes de proxy.

**LXD:** almacenamiento depende de backend y configuración (dir/ZFS/Btrfs/etc); las capas/copia optimizada dependen de driver, no presuponer que cada LXD duplica todo Linux ni que no gasta disco. **UID/systemd:** sin imagen por worker, menor sobrecoste de filesystem, pero mayor responsabilidad sobre distribución de dependencias, permisos, escalado y aislamiento real.

## 4. Alternativas y descarte basado en requisitos

| Alternativa | Aislamiento multi-tenant | Espacio / overhead esperado *cualitativo* | Portabilidad / complejidad | Veredicto |
| --- | --- | --- | --- | --- |
| Mismo UID + subprocess | Insuficiente: puede ver otros archivos del mismo UID | Bajo | Fácil; no puede proteger usuarios | **Descartado** para cuentas reales |
| **UID distinto + systemd system units** | Separación Linux DAC + hardening con unidad de **sistema**, seccomp/LSM verificados; límite compartido kernel | Sin imagen por sesión; memoria de procesos real | Necesita broker administrativo de privilegios mínimos, alta/baja UID, filesystem y despliegue reproducible | **Alternativa ligera válida**, no automáticamente más segura |
| **OCI/runc en contenedores efímeros** (Docker o containerd/Podman compatibles) | Namespaces, mounts, cgroups, seccomp, capabilities; idealmente userns/idmap. Kernel compartido | Imagen única compartida + capa/temporales por job | OCI facilita cambiar runtime/nube; daemon/privilegios/almacenamiento necesitan gobierno | **Candidato preferente provisional**, no elección definitiva hasta prueba |
| **LXD no privilegiado** | user namespaces, `security.idmap.isolated=true`, perfiles AppArmor/seccomp, límites | Depende de pool/snapshot; imagen/instancia potencialmente más pesada que proceso OCI | LXD ya disponible, pero requiere provisionamiento/servicio fiable y no exponer su socket al portal | **Candidato B** si seguridad/host inclinan la decisión |
| **gVisor/runsc** | Kernel en userspace, mayor separación de syscalls | Coste extra memoria/syscalls; depende de carga de archivos | Compatible con parte de OCI; requiere benchmark FFmpeg y compatibilidad | **Solo si riesgo multi-tenant exige mayor aislamiento** |
| **Kata/Firecracker microVM** | Aislamiento por kernel VM, mayor frontera | Guest kernel/memoria, inicio y disco de imagen; números externos no extrapolables | `/dev/kvm` ausente actualmente; necesidad de nested virtualization o cambio de host | **No para VM actual** |
| Kubernetes/cluster | Orquestación, no mecanismo de aislamiento intrínseco | Capa operativa extra | Excesivo para beta de 2–4 testers | **No ahora** |

Importante: LXD/Docker no implican que el propio Companion deba ejecutarse en Linux. Companion sigue en Windows/macOS; solo ejecuta FFmpeg y tareas **locales**. El servidor ejecuta Engine Linux sobre proxies autorizados. La comunicación requiere contratos de versión e integridad, nunca una carpeta compartida entre máquinas ni originales remotos obligatorios.

## 5. Papers y fuentes examinados (peso de evidencia)

**Investigación revisada por pares:**
1. **Jarkas et al., "A Container Security Survey: Exploits, Attacks, and Defenses", ACM Computing Surveys 57(7), 20-02-2025.** Riesgo residual importante del kernel compartido; la elección no puede basarse solo en throughput o CI. https://doi.org/10.1145/3715001
2. **Manakkal et al., "LITESHIELD: Secure Containers via Lightweight, Composable Userspace μKernel Services", USENIX ATC, julio 2025.** Modelo de aislamiento avanzado con POSIX, resultados de laboratorio; no reemplazo turnkey probado para nuestro Engine FFmpeg. https://www.usenix.org/conference/atc25/presentation/manakkal
3. **Jang et al., "Understanding File System Operations of a Secure Container Runtime Using System Call Tracing Technique", IEICE Transactions 107-D(2), febrero 2024.** La traducción de operaciones de filesystem mediante gVisor puede multiplicar *número de syscalls* (ej. 48× open y 6× read/write en condiciones de su prueba): no significa directamente 48× latencia/tiempo de render, pero alerta sobre cargas de I/O y compatibilidad. https://doi.org/10.1587/transinf.2023EDL8039
4. **"Faascale: Scaling MicroVM Vertically for Serverless Computing with Memory Elasticity", ACM SoCC 2024.** Evidencia de que la elasticidad de memoria en microVMs es un problema de ingeniería relevante; no datos directamente transferibles a Montara. https://doi.org/10.1145/3698038.3698512
5. **Agache et al., "Firecracker: Lightweight Virtualization for Serverless Applications", USENIX NSDI 2020.** MicroVM rápida y eficiente bajo infraestructura adecuada; requiere KVM. El paper no demuestra ventajas en nuestra VM compartida sin `/dev/kvm`. https://www.usenix.org/conference/nsdi20/presentation/agache

**Fuentes primarias operativas (preferibles para configuración):**
- Docker capas compartidas y COW: https://docs.docker.com/engine/storage/drivers/
- Docker límites y riesgo OOM: https://docs.docker.com/engine/containers/resource_constraints/
- Docker rootless y requisitos: https://docs.docker.com/engine/security/rootless/
- OCI portable: https://opencontainers.org/faq/
- systemd exec sandbox y limitaciones de user units: https://www.freedesktop.org/software/systemd/man/latest/systemd.exec
- LXD idmap aislado: https://canonical.com/lxd/docs/default/explanation/security/ y https://canonical.com/lxd/docs/default/reference/instance_options/
- gVisor performance/compatibilidad: https://gvisor.dev/docs/architecture_guide/performance/
- Google GKE Sandbox gVisor/microVM comparativa específica y su coste **no exportable al host local sin medir**: https://docs.cloud.google.com/kubernetes-engine/docs/concepts/sandbox-pods

**Calidad de la inferencia:** Papers de syscalls no proporcionan un benchmark de Montara ni demuestran coste por propietario. No usar cifras externas genéricas para calcular densidad en 8 vCPU ni adjudicar ganador por ser el artefacto más avanzado.

## 6. Recomendación concreta 2026-11-10

**No elegir "Docker por usuario permanente".** Elegir arquitectura **`JobSpec` → `ExecutorBackend`**, contratos de Engine/Companion ya existentes, con *worker efímero por trabajo* (o por propietario activo con TTL si abrir Engine repetidamente cuesta más que mantenerlo caliente). ID de propietario canónico en catálogo, autorización de proyecto y rutas decididas exclusivamente por broker. Los originales nunca se suben por defecto.

**Para la primera implementación real**, en un host Linux donde se permita provisioning seguro, evaluar primero **contenedor OCI Linux mínimo no privilegiado** con imagen compartida, mount exclusivo y subdirectorios privados, recursos/pids/TTL y seguridad de daemon. **Docker es una implementación posible, no obligación del producto**. Lo preferimos inicialmente como candidato por equilibrio técnico de portabilidad/aislamiento/distribución, no porque existan pruebas anteriores. Si instalar/aislar el daemon es inviable en GCP, comparar contra **systemd system-unit + UID real** mediante las mismas pruebas; LXD como tercera opción si el coste de provisionamiento resulta aceptable. No agregar capas gVisor/VM sin necesidad de riesgo/compatibilidad. La decisión de runtime permanece **condicionada a un gate corto**, no a una arquitectura indefinida.

**Gates antes de conectar web al Engine:**
1. Medir una sola imagen real con tamaño on-disk y push/pull, tiempos arranque frío/caliente, CPU/RSS/peak por worker, proxy temp, FFmpeg y cleanup.
2. Mismos jobs sintéticos primero en OCI Linux y systemd+UID; probar archivo propio permitido, archivo ajeno y secretos denegados, owner A no puede acceder a proyecto B, cancellation mata descendientes, no sockets de control accesibles.
3. Reproducir trabajo Stage real sobre proxy fijo y al menos un render final Companion local, verificar original no subido y checksums/receta.
4. Bench de un usuario real desde cliente Windows/Mac con red WAN; después 2/4 en VM, registrando CPU, RAM, disco, latencia p95, apertura, cierre, picos de ffmpeg, impacto en otras sesiones. **No comprometer 10 usuarios antes de estos datos**.
5. Host con permisos verificados para runtime elegido; preservar Chema 8101–8103, Owner 8115, secreto OAuth y no debilitar user namespaces. Registro de rollback/backup.

**Migración a main:** llevar primero interfaces y contratos de identidad/propietario/recetas, luego el adaptador de ejecución elegido bajo feature gate; no imponer nuevo Docker daemon como dependencia de `main` ni forzar los tests de Linux/Companion Mac a requerir contenedores.

**Este ADR no introduce runtime ni efectos sobre servicios; queda abierta la elección final hasta los gates anteriores.**
