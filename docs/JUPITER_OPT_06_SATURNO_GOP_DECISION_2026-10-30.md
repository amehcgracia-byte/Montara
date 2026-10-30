# JÚPITER-OPT-06 — Decisión sobre GOP selectivo y siguiente experimento (2026-10-30)

## Decisión
**Cerrado el repaso de Saturno; NO lanzar un nuevo render A/A/B ni implementar otro empaquetador.** La selección GOP demuestra factibilidad de transferencia, pero no acelera apreciablemente el render para el caso Stage controlado. El siguiente candidato debe demostrar una disminución de trabajo de decodificación/filtrado o de tiempo hasta la primera edición con material real.

## Evidencias leídas (datos históricos, no prueba nueva)
- `docs/SATURNO_20_SELECTIVE_GOP_RESULTS_2026-10-29.md`: fuente sintética 90 s, H.264 GOP cerrados sin B-frames; 19.756.759 → 4.383.338 bytes (−77,81 %), conservadas dos ventanas y hashes BGR idénticos. No certifica producción.
- `docs/SATURNO_24_FULL_SELECTIVE_ISOLATED_RESULTS_2026-10-29.md`: Stage controlado con vídeos extendidos artificialmente, A / A_repeat / B. Exportaciones 543,0805 / 542,1211 / 541,4727 s. A/B 3007/3007 frames idénticos, audio PCM idéntico, cronología idéntica, SHA256 MP4 idéntico. Medios 9.549.037 → 5.744.051 bytes (−39,85 %). **Ahorro B frente A: 1,61 s, 0,30 %; NO evidencia de aceleración notable de exportación.** Se emplearon ajustes QA del decodificador y encoder y aislamiento de originales; resultados limitados a fixtures controlados.
- `docs/SATURNO_25_CONTROLLED_TRANSFER_RESULTS_2026-10-29.md`: ZIP A 9.260.068 bytes / B 5.682.115 bytes (−38,64 %). Transporte HTTP en 127.0.0.1: mediana 8,23 ms vs 5,10 ms; **NO WAN**. Tiempo de preparación 2,60 s incluye construir fuentes artificiales.
- `docs/JUPITER_OPT_05_EXPORT_STREAM_COPY_2026-10-30.md`: fixtures E2E 720p no pueden usar stream copy para salida YouTube 1080p; no modificar los gates para forzarlo.

## Implicaciones prácticas
1. Separar tres objetivos: **menos bytes subidos**, **menos CPU de preparación** y **menos CPU de exportación**. No atribuir al render ahorros de transferencia.
2. La selección GOP sirve de posible transporte selectivo, no necesariamente de optimización de FFmpeg cuando el plan consume las mismas ventanas.
3. Reutilizar código probado, no reabrir pruebas de equivalencia extensas con el mismo fixture.
4. La referencia actual es 8 vCPU/31 GiB RAM; si la VM vuelve a 4 vCPU, registrar CPU/memoria/carga. Los renders anteriores estaban bajo otras condiciones.
5. El encargo iPhone HEVC 4K HDR VFR queda priorizado al recibir clips reales; primero papers/documentación técnica vigente y luego perfil de filtros con `montara-bench`, no asumir el cuello de botella.
6. **Próxima tarea específica:** preparar inventario y matriz de material real para elegir un único perfil representativo (Sony H.264 1080p/4K, iPhone HEVC HDR VFR, 360 real). Si no hay clips, limitarse a auditoría de decodificaciones repetidas en el exportador en modo solo lectura; nunca benchmark grande sin advertencia.

## Normas
Mantener `fernando/continuacion-montara`, no editar `main`, `engine`, `mixer`, ni el HOME/servicios de jm. Trabajos pesados bajo `montara-bench`. Sin datos sensibles ni metraje en repo público. Comprobar sistema de autoapagado a 40 minutos antes de renders largos.

## Estado
OPT-06: **REVISIÓN CERRADA** con base documental, sin nuevos renders ni promesas de speedups. Continuación: **OPT-07 perfiles representativos y análisis de desperdicio real**.
