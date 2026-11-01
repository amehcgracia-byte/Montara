# JÚPITER — Triaje estático de 218.846 s en EditStage (2026-11-01)

## Evidencia
Ensayo real FOCUS A/C con fuentes iPhone+Sony, 4 segundos de segmento elegido, editor_finished_sec=218.846, export FFmpeg segmento Sony 6.122 s, elapsed experimento 231.567 s. Los artefactos del proyecto ocupaban 52 KB y caché local 20 KB. Solo había export.log, sin registro detallado de edit. **No se dispone de desglose temporal interno.**

## Orden observado en el código del submódulo, read-only
`EditStage.run` (edit.py:207 en checkout estudiado) para plataforma YouTube:
1. `_with_camera_roles(load_coverage(...))`.
2. `_with_director_quality` (desde run alrededor de línea 221), que llama sucesivamente a `analyze_handheld_director_quality` y `analyze_non_music_sources` (edit.py:382+).
3. `_load_or_analyze_beats` (cache por fingerprint, o análisis si no coincide, que puede incluir `analyze_samples` / `analyze_instruments`).
4. Eventual `build_filler_bank` si hay filler.
5. `_youtube_multicam_plan`.
6. Escritura/validación de `beats.json` y `edit_plan.json`.

## Inferencias NO demostradas
- El análisis visual previo a elegir un segmento es **candidato prioritario**; no está demostrado que explique la mayor parte de 219s.
- La función de análisis de beats y posible separación instrumental también puede consumir tiempo; la existencia de un archivo beats con fingerprint coincidente en el ensayo anterior no está confirmada.
- Poco tamaño de artefactos no prueba ausencia de trabajo intensivo de CPU o subprocess.

## Próximo paso recomendado
Inspeccionar el cuerpo de `_with_director_quality`, `analyze_handheld_director_quality`, `analyze_non_music_sources` y cache fingerprint y la sección `_load_or_analyze_beats`, y analizar entradas/ventana del proyecto; preferir un pequeño harness que cronometre bloques sobre datos **ya existentes**, sin rerender y bajo lock, solo después de decidir qué medir. No tocar el submódulo compartido sin Chema.
