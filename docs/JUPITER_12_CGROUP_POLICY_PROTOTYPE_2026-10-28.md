# JÚPITER-12 — Primer cambio funcional propuesto: planificación CPU/RAM cgroup-aware

Fecha: 2026-10-28. Rama experimental `fernando/continuacion-montara`. Cambios **solo** en `experiments/container_budget/`. No modificar `main`, submódulos, ni backend, ni pagar servicios.

## Entregado
- `resource_policy.py`: política pura candidata con `inspect`, `segment_workers`, `overlap_allowed`. Lee CPU `cpu.max`, RAM `memory.max`, consumo `memory.current`, `MemAvailable` y RAM/CPU host. Elige el menor techo aplicable. Considera max/valores ausentes y evita cero workers. NO decide ni lanza jobs.
- `test_resource_policy.py`: cuatro escenarios de datos sintéticos: 2CPU/8GiB host 32CPU/128GiB; 8CPU/16GiB; sin límite cgroup; medio CPU/1GiB. Ejecutar con `python -m pytest -q experiments/container_budget/test_resource_policy.py` desde el directorio del experimento o con `PYTHONPATH=experiments/container_budget`.
- `diagnose.py` y `test_diagnose.py` de ronda anterior: lector read-only y fixtures, complementarios.

## Por qué esto es distinto de la política actual
Referencia `engine/core/stages/export.py` anclada en main `60a7b7e9`: `_segment_worker_count` considera `os.cpu_count` y RAM físicas; si `segment_workers>2`, permite hasta 8 sin cgroup. `_verification_overlap_enabled` comprueba RAM host en Linux. En contenedores CPU/RAM asignados <host, esto puede ser un riesgo de sobreparalelización y falsos positivos del overlap; no se ha demostrado OOM ni impacto real de rendimiento.

## Advertencia importante
La política experimental limita `workers` a la mitad del presupuesto CPU efectivo (en 2 CPU → 1 worker), **por diseño más conservador que el default histórico de 2 workers**. Esto podría reducir velocidad en ciertos montajes: no sugerir aplicar a producción sin benchmark A/B. Los mínimos de RAM utilizados son heurísticos, no una caracterización de FFmpeg. `inspect` solo cubre cgroup v2 directo, no cgroup v1, montajes anidados, `cpuset`, `memory.high` o casos de múltiples jerarquías.

## Plan de aceptación antes de tocar el motor de José Manuel
1. Ejecutar pruebas unitarias de la rama y confirmar no hay regresiones; capturar SHA y Pytest.
2. Docker QA sobre host con mucha RAM/CPU pero limitar a `2CPU/8GiB` y `1CPU/2GiB`. Verificar recursos observados mediante `diagnose.py`. Comparar función actual con política candidata **sin render inicial**.
3. En QA desechable, mismo fixture `much-to-me`, plan de edición congelado con mismo SHA, `segment_workers=1` frente `2` frente `auto`, comparar tiempos frío/caliente, pico de memoria cgroup y errores; incluir 360 en un segundo conjunto. Mantener misma calidad de salida.
4. Validar `overlap` en host>16GiB con contenedor 8GiB y contrastar con habilitación manual, midiendo si hay presión memoria real y latencia.
5. Solo después de observar que una política cgroup-aware evita un riesgo sin penalización excesiva, proponer patch pequeño en `engine/` **como PR separada autorizada**. No hacer monkeypatch del motor ni copiarlo al repositorio.
6. Si 1 worker empeora inaceptablemente los tiempos, ensayar un modelo de presupuesto que permita dos con 2CPU cuando cgroup lo tolere. La política nueva no es óptimo probado.

## Estado de validación
- Durante desarrollo se ejecutaron localmente cuatro pruebas para una implementación funcionalmente equivalente: 4 passed. **No afirmar que se ejecutaron los archivos GitHub exactos ni benchmark de render**; quedan pendientes ejecutar desde checkout contra rama.
- Disponibilidad ARM64 y Oracle sigue siendo una investigación independiente; esta corrección está motivada por **todos** los contenedores Linux, tanto x86_64 como ARM.
