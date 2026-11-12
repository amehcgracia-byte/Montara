# I15 — Evaluación física: Engine real en espacios Linux privados SIN Docker

**Fecha:** 2026-11-10. **Estado:** laboratorio opt-in, no conectado a HTTP ni desplegado como servicio. **Objetivo:** obtener evidencia adicional para decidir entre OCI y Linux + namespaces/systemd; **no** elegir solución por inversión anterior en Docker. **Entorno:** VM Linux GCP compartida, 8 vCPU, 31 GiB RAM, ~48 GiB de disco libre, `kernel 7.0.0-1014-gcp`, Engine `b5e48317ef85225f901adc69af8cc17aa8146880` igual al submódulo pinneado. Los detalles del proveedor/CPU son medición, NO requisitos de Montara.

## Técnica probada: laboratorio sin instalación

Se usa `unshare --user --map-root-user --mount --net` **sin fork PID** (para mantener handshake supervisor PID), monta una raíz `tmpfs` privada, incluye `/usr` de lectura, monta explícitamente el checkout Engine, los módulos URANO, el virtualenv y la instalación Python de solo lectura, y monta **un único workspace sintético** de lectura/escritura. `/tmp` tiene `tmpfs` aparte de 64 MiB, sin montar `/proc`, `/run`, ni el HOME completo del operador; red aislada, `chroot`, y `setpriv --no-new-privs --bounding-set=-all --inh-caps=-all --ambient-caps=-all`. Límites demo con `ulimit` para memoria virtual (4 GiB), CPU (60 segundos de CPU) y descriptores (256); **no son cuotas cgroup de memoria real/CPU/PIDs**. La raíz temporal es de 96 MiB. Todos los procesos hijos reciben las mismas restricciones de namespace a través del fork; los procesos se cierran con el supervisor.

*El proceso muestra UID 0 **solo dentro del user namespace**, mapeado al UID sin privilegios del operador en el host. No adquiere root del servidor. Aunque montajes y falta de red sean obstáculos reales, una barrera defensiva de producción requiere endurecimiento adicional; no concluir que el host es invulnerable a escapes del kernel.*

**No hay copia de una imagen Linux por usuario:** los directorios de Python/librerías/Engine se comparten de lectura desde el host; el workspace propio es la única fuente de datos montada con escritura. Esto **no mide** cuota de espacio para vídeos/proxies, tamaño de paquetes descargados, contención de recursos ni estabilidad entre proveedores.

## Qué se observó en VM real

| Prueba | Resultado | Limitación |
| --- | --- | --- |
| Importación de Engine real dentro del sandbox | PASS | Librerías disponibles en entorno específico |
| Apertura real del proyecto sintético por `PrivateWorkerSupervisor` + Engine | PASS, con confirmación de Engine | No vídeos ni export |
| Proyecto UUID de otro propietario | Rechazado | Autorización lógica del catálogo |
| Archivo sintético de otro propietario fuera de los mounts | Invisible | No prueba escape kernel / vulnerabilidades |
| Carpeta personal/configuración del host | No montada | `/usr` compartido de lectura sigue visible |
| Ruta de código Engine | Mount readonly comprobado | No mide manipulación de cachés/sockets futuros |
| Red exterior | Conexión bloqueada | No prueba todos los syscalls/escape por descriptores abiertos |
| Namespaces user/mount/net propios | Diferentes del padre | **PID namespace no aislado** |
| Prueba de cierre | Worker detenido y guardia `idle` | No cancela un FFmpeg con varios descendientes |
| Una ejecución aislada inicial | ~1,81 s hasta handshake; ~0,03 s abrir | Sin vídeos, orden y cachés puntuales |
| Segunda ejecución aislada | ~2,18 s hasta handshake; ~0,06 s abrir | Variabilidad real del entorno |
| Ejecución tras probes + límites | ~2,15 s hasta handshake; ~0,03 s abrir | Mismo hardware |
| Dos ejecuciones concurrentes tras límites | Worker A 2,83 s, B 2,76 s, total pared 3,37 s | Dos fixtures sin carga multimedia |
| RSS una muestra del worker | ~130,5 MiB | **No** pico del árbol ni del cgroup |
| Exposición HTTP pública | **No existe** | Portal C8 sigue sin ruta Engine I13 |
| Prueba Companion/Stage/MP4 | **No** | Requiere el siguiente recorrido físico |

## Limitaciones importantes: aún NO apto para tenants reales

1. **No hay PID namespace ni cgroups aplicados a cada worker.** `ulimit` de memoria virtual no equivale a `MemoryMax` de cgroups; tampoco limita la suma del árbol de procesos. Falta TasksMax/PIDs, cuotas de disco de workspace y detener FFmpeg/reap bajo errores.
2. **No hay seccomp/AppArmor específico**, ni garantía formal frente a escapes de rootless user namespace y host kernel compartido. La compatibilidad de FFmpeg bajo esas restricciones necesitará pruebas.
3. **Los procesos del host y los workspaces siguen perteneciendo al UID real del operador** en el host. Aunque el worker chrooteado no vea rutas ajenas, el usuario host que opera la API conserva más acceso; para producción se necesita un broker privilegiado mínimo, separación de identidades o contenedor OCI reforzado. No compartir socket Docker/LXD con HTTP.
4. Falta validar FFmpeg real sobre proxies, caching, artefactos, cancelación, el protocolo con Companion, WAN, seguridad cross-project bajo usuarios adversariales y E2E de MP4. No recomendar este shell como ejecutor general de producción ni acoplar I13 a él.
5. No se habilita la API Engine ni se toca la configuración de Cloudflare, la rama `main`, los servicios 8101–8103 de Chema, la cuenta Google real ni la BD del portal.

## Decisión después de I15

**Resultado parcial:** Linux userns/mountns + raíz privada es **viable para abrir el Engine real**, con coste temporal sin instalación ni imágenes por owner. OCI sigue siendo una alternativa igualmente válida: comparte capas, tiene integración de cgroups/PIDs/seccomp y distribución de imágenes más estandarizada; una prueba pequeña de Docker en CI no justifica por sí sola adoptarlo. La decisión final se basará en comparar una configuración OS segura de ambos, no únicamente los tiempos de apertura sintética.

**Próximo gate de máximo valor:** introducir límites cgroup reales o sandbox OCI equivalente; PID ns y pruebas adversariales; medir memoria pico de todos los procesos y disco por job con proxy real; luego elegir una implementación, conectar I13 detrás de feature gate y ejecutar 1-user E2E con Companion local. Mantener independencia GCP/AWS/Azure/Oracle y x86_64/ARM64 a través de `PrivateExecutor`.

## Reproducción manual (operador autorizado en Linux)

El laboratorio usa actualmente el checkout `montara-integration-i13` y la instalación de Python/Engine que ya existía en la VM. El script acepta rutas explícitas, **no es un servicio instalable**. Se invoca opt-in por el operador: `PYTHONPATH=tests python tests/urano_i15_namespace_real_open_lab.py`. Verifica el SHA Engine antes de trabajar. En otro host habrá que proporcionar sus rutas aprobadas y una instalación Python compatible; no convertir el directorio de laboratorio ni el gestor `uv` en requerimiento de producto.

Las validaciones automáticas de CI solo comprueban el contrato *safe by default* y sintaxis; **no lanzan namespaces ni requieren privilegios de runner**. Los resultados físicos anteriores se comprobaron directamente en la VM de FER.
