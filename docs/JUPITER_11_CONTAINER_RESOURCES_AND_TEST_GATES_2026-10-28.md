# JÚPITER-11 — Hallazgo crítico de planificación de CPU/RAM en contenedores y agenda de validación

Fecha: 2026-10-28. Auditoría estática de Montara main y ZuckerVideos pinned `60a7b7e9a39077b36f45057811abd6a833a168ef`. **No se han modificado motores, no se ha desplegado nada, no se han ejecutado benchmarks de Montara.**

## Hallazgo P1 (incompatibilidad potencial, aún no incidencia reproducida)
1. `engine/core/stages/export.py:674-691` `_segment_worker_count` utiliza `os.cpu_count()` y `os.sysconf(SC_PHYS_PAGES)` para elegir workers; el setting `segment_workers>2` fuerza hasta 8 sin revisar cgroups. En contenedor con cuota CPU y límite RAM inferiores al host, este cómputo puede exceder el presupuesto efectivo.
2. `engine/core/stages/export.py:696-719` `_verification_overlap_enabled` en Linux calcula `memory` por páginas físicas host y `available` por `/proc/meminfo`; no consulta `memory.max` de cgroup. En contenedor 8GiB sobre host >16GiB puede admitir solapamiento de verificación aunque límite efectivo sea menor. Es un riesgo de RAM/latencia/cancelación, no prueba de OOM en su CI.
3. `deploy/preflight.py:29-46` **ya tiene una fuente correcta para reportar** `/sys/fs/cgroup/memory.max` y `/sys/fs/cgroup/cpu.max`. Reutilizar conceptos/lecturas en el motor tras aprobación, no crear otro subsistema de telemetría.
4. `engine/tests/test_export_verification_overlap.py` prueba memoria faltante o baja en **macOS**, y la parada ante fallo de verificación; no aparece un test de memoria limitada de Linux en ese archivo. Confirmar toda la suite antes de añadir uno.
5. `compose.yaml` limita 2 CPU/8GiB y `deploy/README.md` confirma 1 instancia/usuario. Con el default `segment_workers=2` la cifra real podría ser 2, por lo que **no afirmar sobreparalelización efectiva** sin inspeccionar settings en runtime. El riesgo está en decisiones bajo host y en `overlap`.

**Corrección explícita de informe previo:** es incorrecto asumir que Oracle de 12GiB desactivará `_verification_overlap_enabled`; el código Linux puede ver memoria host >=16GiB. La política necesita considerar cgroup.

## Reproducción controlada sugerida al autor, sin medios de clientes
- Linux x86_64 con Docker 2CPU/8GiB sobre host con >16GiB; segundo contenedor 1CPU/2GiB; mismos pins, settings y script de inspección. Registrar para cada uno `os.cpu_count()`, sysconf RAM, `/proc/meminfo MemAvailable`, `cpu.max`, `memory.max`, `memory.current/peak`, `cpu.stat`, número de workers real, flag de overlap y errores. **No cambiar límite de RAM de producción ni usar proyecto activo**.
- Comparar `_verification_overlap_enabled` observado con política conservadora `effective_ram=min(host_total, cgroup_limit)`; `effective_available=min(host_available, cgroup_limit-memory.current)` con reserva de seguridad y tratamiento de errores. Considerar v1 y v2; no imponer fórmula final sin perfilado.
- Comprobar si `os.sched_getaffinity(0)` y cgroup cuota revelan CPU efectiva, y cómo se comportan workers configurados explícitamente. No dividir 2 OCPU por threads sin benchmark.
- Tests deterministas con monkeypatch de `os.cpu_count`, sysconf, archivos cgroup y MemAvailable; casos: sin cgroup, memory.max=max, 1GiB/8GiB con host 64GiB, cgroup 12GiB, cuota CPU fraccionaria, fallo lectura; preservar política macOS y compatibilidad.
- Gate de seguridad: mismos fotogramas, audio y corte antes/después; mejora esperada es **límite de riesgo**, no inventar speedup. Cambiar submódulo solo por José Manuel tras aprobar reproducción.

## Otras comprobaciones de esta ronda
- `deploy/requirements-linux.lock`: fijado x86_64 Python3.11; 80 paquetes aprox, incluyendo av14.2.0, llvmlite0.45.1, ctranslate2 4.8.4, onnxruntime1.31.1, numba0.62.1, opencv-python-headless4.11.0.86. Metadatos PyPI confirman wheels ARM64 para algunos, **resolver el conjunto todavía pendiente**.
- Docker multi-arch y Deno requieren build y arranque real; no confundir build bajo QEMU con benchmark ARM nativo.
- `tests/e2e_journey.py` usa navegador+motor real; `--base-url` modifica el proyecto activo (destructivo): QA con volumen aislado obligatorio.
- `experiments/media_optimization/benchmark_b03_proxy_cache.py` ya cubre cold/warm proxy; `benchmark_b07_original_export.py` verifica receta y originales, no E2E. No duplicarlos.
- `engine/tools/benchmarks/render_ab.py` utiliza `vm_stat`, `pgrep` y `git show` de refs históricos; no sirve tal cual como benchmark neutral de ARM/GPU.
- Contenedor x86 histórico 2 CPU/8GiB Stage ~100.234s output; export 329.192s, peak cgroup 1.84GiB, 16 cortes; no extrapolar a 360 5K / 30GB.
- GitHub main ya incorporó selecciones de proxy Fer; la integración de UI local sigue pendiente. No confundir cache reutilizable con política global terminada.
- GPU RunPod exige transferencias explícitas; cronometrar E2E y mantener calidad. Oracle Free ARM no incorpora NVIDIA.
- Reproducibilidad exige mismo SHA Montara/engine/mixer, plan SHA, fuentes, parámetros e identidad de entorno, mediana/dispersión de 3+ repeticiones si procede; el warm cache no es primer render.

## Priorización propuesta
**P0 documentación/validación**: avisar a José Manuel del riesgo cgroup y pedir reproducción/PR de tests en engine (no cambios unilaterales). **P1 compatibilidad ARM64**: resolver wheels del lock en build aislado, sin nube. **P2 benchmark CPU**: congelar plan que realmente sea idéntico y levantar QA x86. **P3 hardware**: probar Oracle ARM y Google CPU; RunPod GPU después de precio/transferencia. **P4 arquitectura híbrida**: adaptador estable de fuentes y ownership multiusuario, solo cuando pruebas anteriores pasen.

No hay garantías de disponibilidad free tier de proveedores ni nuevas cifras de velocidad en este estudio.
