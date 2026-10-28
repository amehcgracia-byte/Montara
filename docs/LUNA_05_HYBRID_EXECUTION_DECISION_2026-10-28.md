# LUNA JÚPITER-05 — decisión arquitectónica previa al despliegue híbrido
Fecha: 2026-10-28. Solo investigación y contrato; NO cambia motor ni main.

## Procedencia verificable
Montara main actualizado (PR #7 server readiness; PR #8 integración selectiva Fer), en particular `deploy/README.md`, `docs/ANTES_DEL_SERVIDOR.md`, `docs/INTEGRACION_FER_2026-10-28.md`, `local_media/session_proxies.py`. Documentación externa: https://ffmpeg.org/ffmpeg.html ; https://github.com/Netflix/vmaf ; https://bazel.googlesource.com/bazel/+/a86cff2e91eadbb69328b4e6ca3c184954c8465d/site/en/docs/remote-caching.md . No benchmark nuevo ejecutado.

## Lo que ya funciona, no repetir
- Aceptación Linux x86_64 en contenedor privado: 2 CPU, 8 GiB, flujo Stage de 100.233991s/1920x1080 con tres cámaras y 16 cortes; ingest 47.993s, sync 12.040s, cut 0.008s, edit 12.691s, render 329.192s, recorrido navegador completo 811s; pico memory.peak cgroup 1,972,752,384 bytes. No equiparar tiempos del motor con los de UI ni comparar con otras pruebas que usan planes diferentes.
- Docker y lock de dependencias explícitamente fijados para Linux x86_64; el motor usa versiones exactas de submódulos. No hay validación Linux ARM64.
- Montara backend tiene estado global de proyecto: pruebas privadas **una instancia/volumen por usuario**. Gunicorn workers extra no aíslan correctamente trabajos.
- Local proxy cache seleccionado de la rama de Fer, pero no integrado con UI ni export final: `local_media/session_proxies.py` produce IDs/metadatos sin paths públicos, no browser API.
- Estado local `Project` ZuckerVideos v1 ya existe; no añadir esquema alternativo.

## Fronteras de ejecución y contratos necesarios (sin implementarlos todavía)
### Plano de control
- Web del usuario: selección de archivos, ediciones y UX; guarda autorización local revocable; define intención de exportación (calidad, coste permitido). Evitar prometer acceso local al backend remoto.
- Orquestador/planificador: decide si un trabajo puede procesarse con medios disponibles en local/server; evita simultaneidad incompatible con estado global; gestiona propiedad, cuota, cola, cancelación y registro del ejecutor. No diseñar servicio nuevo hasta verificar contratos ya existentes.
- Ejecutor: actual Linux CPU x86_64 validado; candidatos Linux ARM64 CPU gratis, PC local, GPU remota. Cada uno declara capacidades reales: OS/arch, ffmpeg codecs, hwaccels, CPU/RAM/disk/VRAM, versiones de motor y restricciones de fuente; siempre mantener fallback probado.

### Plano de datos
- Fuente original inmutable y su identidad. Resolver de fuente lógica a ruta *local al ejecutor*; un browser FileSystemHandle nunca se transmite como si fuera una ruta POSIX.
- Receta versionada y auditable, derivada de `project.json` actual, no inventada desde cero. Mantener identidad, fps/timebase, offsets, color/HDR, proyección 360, decisiones manuales, efectos y versiones.
- Artefactos de caché con huellas de entradas, parámetros y versión de algoritmo. Reutilización entre máquinas SOLO si resultado compatible; evitar confundir hash de archivo con hash de operación. Inspiración: Bazel action cache y CAS, no obligación de adoptar Bazel.
- En remoto: transferencia explícita de originales o fragmentos, con checksum, cuota, borrado y permisos; logs de bytes subidos y descargados.

## Regla de decisión que debemos medir
- Local: T_local = T_preparación_local + T_cola_local + T_proceso_local + T_verificación_local.
- Remoto: T_remoto = T_empaquetado + T_subida + T_cola_remota + T_proceso_remoto + T_descarga + T_verificación_remota.
- Coste remoto = tiempo CPU/GPU facturado + almacenamiento + egreso + cola/overhead del servicio, con free tier verificado.
- No se invoca GPU cuando T_remoto >= T_local para mismo nivel de calidad, salvo que el objetivo sea reducir carga en el equipo del usuario y el usuario lo elija. Para procesos no interactivos, ofrecer prioridad de coste vs tiempo en el futuro, no introducir UI antes de necesidad.
- Comparar en muestras 10min, 1h, sesión larga; incluir formatos y fuentes representativas, mismo plan y calidad. Controlar cold/warm, tamaño de transferencia y memoria/disco pico. Resultados de 100s del fixture son base funcional, NO proyección de 30GB.

## Matriz de viabilidad provisional
| Destino | Estado real | Bloqueo primario | Próxima prueba |
|---|---|---|---|
| Linux x86_64 CPU privado | Aceptado con muestra Stage | un usuario/instancia, coste y calidad con material real | baseline repetida mismo plan, cold/warm, uso disco |
| Linux ARM64 CPU Oracle Always Free | NO validado | dependencias de lock compilado para x86_64, CPU/FFmpeg, instalación y almacenamiento | build arm64 smoke+functional+render, sin suponer rendimiento |
| Windows/macOS local | Prototipo proxy; macOS engine probado; Windows navegador básico | compatibilidad backend y permisos, empaquetado local opcional | resolver fuente, export original y medir sin instalar complementos en usuario final aún |
| GPU remota on demand | NO medida | datos disponibles, CUDA/driver/modelos, transferencias y costes | un A/B de mismo render, después de baseline |
| Browser-only | directorio JSON/preview local confirmado | export final multicámara/FX motor Python no corre en JS | no reescribir, identificar qué subsistemas sí son viables |

## Gate de calidad y seguridad
- Original nunca sobrescrito, trabajo temporal recuperable; mismo montaje y salida visual/audio según tolerancias; fotogramas, FPS, offsets, drift, HDR 360, color y composición.
- Autorización explícita por archivo/carpeta y separación de cuentas y jobs.
- No publicar endpoint multiusuario sin ACL, ownership de proyecto y almacenamiento; Basic Auth privado no es identidad comercial.
- Para proxies: VMAF/SSIM y revisión visual solo con frames alineados y referencia comparable. El VMAF de Netflix es herramienta, no métrica suficiente para 360 reproyectado o efectos.
- FFmpeg indica que HW acceleration puede introducir copias GPU->CPU y no siempre acelerar. Benchmark extremo a extremo.

## Propuesta de siguiente entregable concreta, útil al autor
Una hoja de capacidad por ejecutor en JSON **como ejemplo documental**, no implementación: arquitectura, formatos soportados, RAM/disk observado, tareas aprobadas y fuente accesible. Completarla con una corrida reproducible en Linux x86_64 y una prueba ARM64 (cuando exista máquina) antes de escribir scheduler o gateway. El siguiente cambio de código solo debe surgir de incompatibilidad reproducida o mejora A/B demostrada.
