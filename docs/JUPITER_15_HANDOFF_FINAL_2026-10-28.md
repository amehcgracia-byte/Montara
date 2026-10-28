# JÚPITER-15 — Cierre técnico del parche de memoria (2026-10-28)

**Estado: candidato revisable y pruebas unitarias ejecutadas; NO integrado en submódulo, NO validado con E2E.**

## Qué se ha verificado de verdad
- Código candidato: `experiments/container_budget/cgroup_guard.py`.
- Se ejecutó `python -m pytest -q` en copia de los dos archivos de guardarraíl bajo `/mnt/data/jupiter15`: **7 passed in 0.04s**. Son siete pruebas de la función candidata aislada, NO de `engine/core/stages/export.py`.
- Se comprobó la restricción real del entorno: cgroup v2 `cpu.max = 400000 100000` (4 CPU), `memory.max = 4294967296` (4 GiB).
- Se reconstruyó una copia **solo del fragmento relevante** de `_verification_overlap_enabled` consultado en el commit fijado y se ejecutó `git apply --check` contra el fichero reconstruido, con salida correcta (0). El contexto coincide literalmente con la función inspeccionada en GitHub. **No es** aplicar la modificación al checkout completo ZuckerVideos ni ejecutar su suite de regresión.
- El parche separado `experiments/container_budget/patches/engine_overlap_cgroup_v2_candidate.patch` no modifica `main` ni `engine/`.

## Alcance mínimo del cambio propuesto
Corregir solo la condición de habilitación del overlap de verificaciones en Linux bajo cgroup v2. Si memoria física host >=16GiB y MemAvailable host >=2GiB, comprobar `memory.max`: si límite finito <16GiB, desactivar; si >=16GiB, comprobar `memory.current` y asegurar al menos 2GiB de margen. Si cgroup no existe o memoria.max=max, preservar comportamiento actual. Si límite finito pero lectura errónea, desactivar por seguridad. No tocar número de workers, calidad de export ni modificación de cachés.

## Limitaciones y revisión de diseño
- El experimento no implementa cgroup v1, rutas cgroup anidadas, memory.high, memory swap ni cpuset. Por tanto NO se puede certificar seguridad de todo Linux container.
- `memory.max-current` es margen estimado, NO reserva de memoria ni predictor de pico. Una carga concurrente puede hacer variar RAM después del chequeo.
- La versión candidata lee filesystem en cada consulta; impacto trivial presunto pero no cronometrado.
- Los tests aislados no prueban que se mantengan todas las condiciones macOS y Linux en el módulo original; se exige añadir tests reales en `engine/tests/test_export_verification_overlap.py`.
- El parche es una propuesta para José Manuel: el propietario decide si el motor se cambia en una PR propia de `zucker_videos` y luego se actualiza el SHA del submódulo en Montara. Evitar parchear submódulo indirectamente desde la app o romper el pin.

## Pasos cerrados antes de autorizar integración (handoff)
1. Aplicar el diff en una rama de ZuckerVideos, nunca en su main, y verificar `git apply --check` sobre checkout real y pruebas específicas existentes del motor.
2. Añadir unit tests cgroup v2 monkeypatch sobre función integrada, y probar en contenedor 2CPU/8GiB montado en host con RAM >=16GiB, con/sin espacio disponible.
3. Ejecutar render Stage QA mismo proyecto/plan y settings con y sin parche, validar audio/vídeo y memoria cgroup peak. La condición de overlap podría afectar velocidad (verificación serial vs paralela), por eso hace falta A/B y no hay beneficio de rendimiento demostrado.
4. Cuando pase, PR ZuckerVideos, actualización explícita de pin `engine` en Montara con revisión del autor.

**Recomendación:** la hipótesis de exceso de permisos de verificación bajo cgroup merece corrección preventiva, pero mantener este punto en **listo para revisión del propietario, aún no desplegable** hasta pruebas del motor. No invertir más rondas de documentos: siguiente trabajo debe ser integración real aprobada por José Manuel o siguiente objetivo arquitectónico.
