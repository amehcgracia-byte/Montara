# SATURNO — Puerta de decisión final y cierre en dos tacadas (29-10-2026)

## Estado verificable

Primera tacada: se ha incorporado a la rama `fernando/continuacion-montara` el workflow `.github/workflows/saturno05-baseline.yml`, que lanza el recorrido Stage **existente** `tests/e2e_journey.py` con submódulos recursivos, FFmpeg, Playwright y el fixture privado `tests/fixtures/much-to-me`. La ejecución GitHub Actions número **40857115100**: https://github.com/amehcgracia-byte/Montara/actions/runs/40857115100 . La ejecución fue observada inicialmente **in_progress**, por lo que este documento NO afirma éxito de exportación. El job conserva logs y artefactos e impone salida fallida cuando no hay MP4, `summary.json` válido y `passed:true`.

La medición del workflow es de **wall-clock de recorrido completo**, NO cronometraje de `ExportStage.run` únicamente. No atribuir esta duración solo al exportador.

## Segunda tacada: gate de ingeniería, no más microprototipos

Se admite desarrollar el paquete de fragmentos **solo después** de una referencia A superada y congelada (hash del MP4, plan de edición/identidad de fuentes, versiones del motor, características de 360, audio). Para obtener B/C se necesita que José Manuel revise/autoricе un adaptador QA de metadatos, rutas y tiempos y cualquier implicación de `_spherical_uses_original_motion`. No se modificarán `main` ni submódulos sin aprobación explícita.

Prueba B: paquete construido desde originales con cierre de dependencias verificable, manifiesto de hashes, origen temporal por fuente y audio; caja de ejecución con originales A y caches A inaccesibles.

Prueba C: **el mismo exportador Zucker** procesa el mismo plan en A y B, sin salida alternativa de FFmpeg que suplante el motor. Comparación de frames decodificados, duración, audio y sync; log de lecturas a originales; bytes reales y tiempo de preparación. Los requisitos de igualdad deberán ser fijados por el mantenedor si el motor codifica con opciones no deterministas.

Prueba D: usar volumen y duraciones A/B **medidas** como entradas de SATURNO-04; costes de proveedor y red efectiva por separado. Umbral económico hipotético NO constituye decisión de despliegue.

## Política de stop

**Si A falla:** se corrige únicamente infraestructura QA y se diagnostica; no continuar con B.

**Si A pasa, pero no hay una vía B aprobada y aislada:** declarar `SATURNO_PARTIAL_RENDER_UNPROVEN`, archivar investigación como optimización futura y seguir con JÚPITER/local-first. No invertir otra serie de ensayos con medios sintéticos.

**Si A/B son equivalentes:** medir D y elegir arquitectura por datos; no asumir que nube ganará.

**Costes:** GitHub Actions puede consumir minutos CI; no se ha contratado ni iniciado RunPod. Ningún motor ni rama main se ha alterado.

## Documentos de evidencia
- `docs/SATURNO_03D_ZUCKER_REAL_E2E_GATE_2026-10-29.md`
- `docs/SATURNO_04_BREAK_EVEN_DECISION_2026-10-29.md`
- `docs/SATURNO_04_FIXTURE_VOLUME_BASELINE_2026-10-29.md`
- `docs/SATURNO_05_REAL_BASELINE_GATE_AND_REMAINING_WORK_2026-10-29.md`
