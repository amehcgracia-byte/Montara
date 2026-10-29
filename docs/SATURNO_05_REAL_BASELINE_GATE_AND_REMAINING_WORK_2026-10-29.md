# SATURNO-05 — Puerta para medir el E2E auténtico (2026-10-29)

## Diagnóstico
La fase ha acumulado experimentos válidos de FFmpeg, pero no se ha ejecutado **ningún A/B Zucker auténtico** desde el paquete parcial. No conviene seguir llamando a los prototipos un avance del render end-to-end. La ruta corta es congelar un **A de referencia** ejecutando el runner que YA existe en Montara: `tests/e2e_journey.py`, que arranca `app.py` y usa Playwright/Chromium y el motor real. El fixture privado `tests/fixtures/much-to-me` tiene tres cámaras, master y nueve pistas; el script `--mode stage` selecciona el master si el fixture existe.

## Artefacto preparado
`SATURNO_05_BASELINE_RUNNER_2026-10-29.zip` adjunto a la conversación, SHA-256 `03f6dd465f61a06f3ddc3868fe0a1adcf8ae456418a264bbe3edc05e54cd955e`. Contiene `measure_e2e.py`, `test_measure_e2e.py`, `README.md`. **El ZIP no está subido a GitHub**.

Pruebas de la envoltura ejecutadas aquí: **5/5 PASS**, incluyendo caso de salida de proceso 0 sin render, runner ausente, fallo de proceso y prohibición de escritura en checkout. No es la ejecución de Montara.

Uso en **clon completo de QA**, con motores, dependencias, FFmpeg, Chromium y fixture disponibles:

```bash
python -m pytest -q /ruta/saturno05/test_measure_e2e.py
python /ruta/saturno05/measure_e2e.py --repo /ruta/Montara --out /tmp/montara-saturno05-stage --mode stage
```

Devuelve `MEASURED_E2E` solo con proceso 0, `summary.json` válido con `passed:true` y export `render.mp4`; guarda logs, wall-clock, SHA256 de exportación y hashes de `edit_plan.json` si el programa lo genera. **Mide el recorrido completo, no export-only**. Requiere un cronómetro específico para el paso export si se quiere comparativa de motor.

## Puertas y límite de esta iteración
1. **Ahora:** baseline A real, una vez en un clon QA con runtime operativo.
2. Después: inspeccionar y congelar plan auténtico con fuentes resueltas, time bases, 360, master, hash y tolerancias.
3. Después: adaptador aprobado por José Manuel y export B sin acceso a originales/cachés A.
4. Solo tras A/B: contrastar calidad, tiempo y bytes reales con modelo de SATURNO-04.
5. Si el B exige nueva ingeniería desproporcionada, alternativa local-first de JÚPITER debe seguir siendo candidata.

**Bloqueo efectivo:** esta sesión permite inspeccionar código GitHub pero no incluye checkout ejecutable completo, los submódulos y fixture descargados; no existe benchmark A que declarar. Sin gasto RunPod, sin modificaciones de main ni de ZuckerVideos/ZuckerMixer.
