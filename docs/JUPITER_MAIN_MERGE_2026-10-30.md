# JÚPITER — Integración experimental de main en rama Fernando (2026-10-30)

## Alcance y decisión
Se probó en un worktree temporal una fusión de `main` sobre `fernando/continuacion-montara`. Tras resolver conflictos y ejecutar pruebas seleccionadas, se realizó un merge commit `58d8d7e` y se incorporó a **la rama de Fernando** mediante fast-forward; publicado y sincronizado con GitHub. **No se modificó `main`**, ni el checkout/servicios de JM. No es aprobación E2E ni de producción.

## Referencias exactas
- FER anterior: `3bbee90` (fix JS para dos selectores de cámaras; `node --check` OK).
- `main` integrado: `e46b685` (10 commits exclusivos de main vs 224 de FER antes de fusionar).
- Merge: `58d8d7e`, padres `3bbee90` y `e46b685`.
- `engine`: `60a7b7e9a39077b36f45057811abd6a833a168ef` → `c89e7791ff6200e29c4281b79e84307277f9527f`; `git merge-base --is-ancestor` positivo tras recuperar historial.
- `mixer`: `c7a46a6d8388c6e0703ef54983f2d627ea189f32`, sin cambio.
- Verificación final: ambos submódulos coinciden con los pins; rama FER limpia y sincronizada con `origin`.

## Conflictos y resolución
1. `local_media/proxies.py`: FER rechazaba no-POSIX con `RuntimeError`; `main` permite seguir generando proxies fuera de POSIX sin bloqueo interproceso. Se eligió la implementación `main`.
2. `tests/test_proxy_singleflight.py`: conflicto add/add; `main` añadía prueba que simula selección `nt`. Se eligió `main` para conservar esa cobertura.

**Límite de madurez:** el archivo `local_media/proxies.py` describe la función como prototipo no integrado todavía con subida web pública ni renderizador final. Permitir la ruta no POSIX no certifica compatibilidad real Windows ni single-flight interproceso en esa plataforma. La revisión de PR #8 no convierte el prototipo en producto terminado.

## Validación reproducible
Con Python 3.11.18 y pytest 9.2.0 del entorno FER, desde el worktree temporal:
```bash
/home/fer/montara-jupiter/.venv/bin/python -m pytest -q \
  tests/test_local_proxies.py \
  tests/test_local_proxy_preview.py \
  tests/test_proxy_signature.py \
  tests/test_proxy_cache_fastpath.py \
  tests/test_proxy_singleflight.py \
  tests/test_server_readiness.py
```
Resultado comunicado: **21 passed in 2.93s**. Antes de añadir readiness: **14 passed in 3.09s**. `git diff --cached --check` correcto, sin conflictos pendientes. `pip check`: «No broken requirements found». Esto último verifica consistencia del entorno existente, **no** la instalación completa de nuevos requisitos del `main` integrado.

## Incidencias de Git
Un fetch con recursión de submódulos falló al consultar el commit histórico de engine `bf5d0066` («not our ref»). Se recuperó `main` con fetch sin submódulos; luego se inicializaron por separado el motor `c89e779` y el mixer. El primer clon superficial no contenía el commit histórico de FER; al ampliar el historial con `--unshallow`, la prueba de ascendencia resultó positiva.

## Pendientes de auditoría
- Tests adicionales del repositorio; E2E de editor en Linux, revisión de capturas, comprobación de motores/importaciones con las dependencias actualizadas.
- Validación de experiencia de usuario Stage/Show/Mixer y del flujo público de subida + proxies; pruebas Windows reales y WAN.
- Benchmarks comparables solo con mismos submódulos, máquina y manifiesto. No trasladar métricas de Saturno 24/25 sin establecer la equivalencia del nuevo motor.

## Coordinación
Aviso de madurez del prototipo y validación parcial compartido con el laboratorio JM en el issue #13 de GitHub. Solicitar auditoría selectiva: A novedades, B duplicidades, C reutilización, D riesgos, E recomendaciones. Chema conserva la decisión de PR selectivas hacia `main`; no se propone fusionar toda la rama FER.
