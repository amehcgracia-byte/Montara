# FOCUS A/C — Editor real sobre proxies físicos: PASS (2026-10-30)

Operador ejecutó `experiments/media_optimization/focus_ac_true_proxy_edit.py` en VM, bajo `montara-bench FER-FOCUS-AC-TRUE-EDIT-01`, con proyecto aislado `/home/fer/montara-focus-ac-true-edit-01`. Se reutilizó cobertura youtube/ritmo del E2E sintético 20 s y dos proxies físicos de 360p existentes.

Resultado:
- **PASS_TRUE_EDIT_FROM_PROXIES**, `EditStage.run()` real del motor anclado.
- **6 segmentos**, dos cámaras, las seis parejas `source_path` original + `clip_path` proxy resueltas con `_segment_source_info`.
- Tiempo reportado **1.617 segundos**, preflight CPU 0.12%, load 0.27 en ocho vCPU. No afirmar comparación de rendimiento con ejecución original; caches de beats/calidad y condiciones pueden diferir.
- Plan: primeros segmentos camera_ids alternados: `33a2c3c3840d42fe9ef6a00155e28639`, `5bbff51930ce4b32a48b54f0f5eba43f`; six cuts coverage begins 0.0, 3.566667, 7.166667, 13.8, 16.333333, 17.866667 seconds. Duraciones 3.566667,3.6,6.633333,2.533333,1.533334,2.133333.
- Git limpio tras ensayo. Report local: `/home/fer/montara-focus-ac-true-edit-01/focus_report.json`.

**Límites**: 20 s de datos **sintéticos**; `EditStage.run` real, pero no toda la cadena de ingest/cut sobre proxies. No export desde originales, no A/B de imagen, audio y sincronía; posible distinta selección de cortes por análisis de proxies. No modificar los tres originales reales ni el engine principal.

**Siguiente gate**: comparar el plan nuevo con el plan original `/home/fer/montara-e2e-01/data-stage/Projects/E2E stage.zuckervid/artifacts/edit_plan.json` mediante `focus_ac_plan_invariants.py`. Diferencias son resultado experimental, no fallo automático de producto. Luego export corto aislado desde originales si los medios/resolución/times se validan; usar `montara-bench` y ventana Chema.
