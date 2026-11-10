# I16 — Engine real rootless Linux: cgroup real, PID namespace y cancelación

**Fecha:** 2026-11-10. **Estado:** pruebas físicas sobre la VM FER; script reproducible opt-in para laboratorio. **Sin producción, sin desplegar**, sin modificar `main`, Cloudflare Owner ni servicios 8101–8103 de Chema. Se conserva la arquitectura multi-cloud y CPU/arquitectura neutral: un ejecutor por trabajo activo, no un contenedor permanente por usuario.

## Prueba física con recursos del kernel

Se ejecutó el **Engine real** del submódulo pinneado `b5e48317ef85225f901adc69af8cc17aa8146880` y un proyecto generado mediante `core.project.new_project_document`. Utilizamos la raíz/mounts de I15 (solo código, entorno Python y proyecto sintético visibles, sin red externa) y **añadimos `unshare --pid --fork`** para obtener PID namespace independiente (el Engine informó `worker_pid=1`). El controlador temporal es `systemd-run --user --pipe --wait --collect`: service cgroup efímero, **sin crear unidades globales**, y con configuración:

- `MemoryMax=512M` **512 MiB** para todo el árbol del job;
- `TasksMax=24` limita tareas/procesos;
- `CPUQuota=100%` equivale a un núcleo de CPU en el intervalo de cuota.

Se comprobaron los tres valores leyendo `systemctl --user show` sobre el cgroup **mientras el Engine estaba abierto**, además de `MemoryCurrent`, `MemoryPeak`, `TasksCurrent` y la ruta del cgroup que coincidía con la unidad efímera.

**Primera ejecución observada:** handshake `2,03 s`, apertura `~0,02 s`, cierre total `2,36 s`. Cgroup informó **83,10 MiB de `MemoryPeak`** en ese instante antes de abrir proyecto; no es el pico absoluto de la carga (la memoria varía durante el trabajo). Segundo ensayo limpio del programa I16: handshake `2,211 s`, total `2,502 s`, y pico cgroup hasta handshake `83,37 MiB`. Resultado del protocolo `ready` / `opened` / `stopped` OK, servicio eliminado automáticamente y directorios temporales borrados.

**Importante:** el `worker_pid=1` no equivale a usuario root del host. Se mantiene el mapeo rootless UID dentro del namespace. Las librerías y código siguen compartidos con mounts readonly y el workspace es efímero. Esta ejecución usa el runtime Python existente de la VM y **no prueba** rendimiento ARM64/Windows/macOS ni costes con vídeo.

## Cancelación forzada: evidencia aún incompleta

El primer intento `systemctl --user stop montara-i16-lab-<id>.service` interrumpió la ejecución del laboratorio y posteriormente se verificó que **no quedaban procesos `engine_worker_process`, servicios `montara-i16-lab-*` ni carpetas de prueba**. Pero el proceso orquestador no devolvió un resultado JSON completo con confirmación del método de cierre tras esa interrupción. **Por tanto la cancelación forzada NO está certificada todavía**: necesitamos una prueba controlada de comunicación/confirmación y *reaping* de descendientes (especialmente FFmpeg), con un controlador de ejecución independiente que mantenga logs y estado aunque se detenga el servicio y que vuelva a leer el cgroup.

Este es un resultado honesto: disponer de `systemctl stop` y observar ausencia posterior de procesos **no** prueba por sí solo la cancelación determinista de un árbol de FFmpeg bajo carga.

## Limitaciones antes de usar con datos reales

1. **No se ha probado seccomp/AppArmor de aplicación ni bloqueo de todos los escapes posibles**; kernel compartido y `unshare` mantienen una superficie de riesgo. UID real host de laboratorio todavía coincide con el operador, no con un broker/UID específico de tenant.
2. No se ha medido uso de disco, temporales Stage, caché y limpieza bajo ficheros multimedia, ni efectos de rendimiento bajo CPUQuota/RAM de producción.
3. El código de `PrivateWorkerSupervisor` actual verifica que el PID devuelto por el worker coincide con `Popen.pid`. Eso ya **no se cumple con `systemd-run --pipe` y `unshare --pid --fork`**, porque hay wrappers intermedios y el worker es PID 1 en su namespace. Requiere un adaptador de transporte confiable que mantenga el protocolo y valide la identidad de la unidad a través de cgroups, sin relajar arbitrariamente el handshake de la clase existente.
4. El CLI de laboratorio `tests/urano_i16_cgroup_real_engine_lab.py` no es un `PrivateExecutor` desplegado en I13 y **no se debe montar en el Worker público**. No existen accesos al editor ni nuevos vídeos desde usuarios por esta prueba.
5. La prueba general Linux de GitHub Actions no equivale a E2E físico Companion → Stage → MP4. Se mantiene pendiente.

## Próximo gate técnico de alto valor

Crear un **broker de lanzamiento temporal** con cgroup y canal stdio, verificación de identidad de servicio, tiempo y reaping, cancelación de descendientes, y espacio/propietario con UID real separado. Probar FFmpeg sintético bajo esas protecciones y medir `memory.peak` y el disco de temporales. Si esto requiere más complejidad que OCI estándar, comparar contra contenedor OCI de recursos limitados con **el mismo job y los mismos parámetros**, sin casarse con Docker ni instalar Docker en la VM compartida sin plan de host.

**Principio preservado:** la interfaz `PrivateExecutor` de I13, el catálogo y las recetas no dependerán de GCP, Cloudflare, Docker, sistema operativo de Companion ni modelo concreto de CPU.
