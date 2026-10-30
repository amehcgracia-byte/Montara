# FOCUS A/C — resultado mini prueba cámaras reales (2026-10-30)

## Resultado observado en Júpiter
`experiments/media_optimization/focus_ac_real_two_camera_mini.py` sobre proxies **reales** de 4 segundos de iPhone `IMG_0044.MOV` (4K, recorte original a partir de 10 s) y Sony `C0188.MP4` (1080p, igual desplazamiento temporal). Se usaron cobertura/máster de referencia **sintéticos, no sincronizados** con esas cámaras; no confundir con validación de sincronía real.

- Estado `PASS_REAL_CAMERA_PROXY_EDIT_ORIGINAL_EXPORT_MECHANICS`.
- Tiempo total **231.567 s**, editor hasta terminar **218.846 s** (~94.5 %), diferencia posterior ~12.721 s; FFmpeg del segmento **6.122 s**, render de segmento total **6.591 s**.
- Preflight CPU **0.06 %**.
- El plan eligió **únicamente Sony C0188.MP4**, segmento 4.0 s desde original 10.0 s. **El iPhone se presentó al editor, pero NO fue elegido ni exportado.** No afirmar validación de render 4K iPhone.
- Segmento `rendered_from=original`, `cached=false`, MP4 resultante **15,268,804 bytes**.
- Git limpio tras ejecución.
- La prueba no da tiempos desglosados internos de EditStage. No atribuir 218.846 s a decodificación iPhone sin profiling.
- Código en motor `core/stages/edit.py`: `EditStage.run` primero ejecuta `_with_director_quality` en YouTube y después `_load_or_analyze_beats`, selección de cámaras y escritura de plan. Son lugares a instrumentar individualmente; no hay evidencia sobre cuál consumió el tiempo.
- No hay medida de calidad A/B, ni validación audio, ni verdadero alineamiento de cámaras. El script de prueba construyó parte del registro probe manualmente y usó referencia sintética: **no es flujo real integral**.

## Comunicación a Chema
Entregar hallazgo técnico concreto: mini caso real tarda 231.567 s de los que 218.846 s ocurren antes de que termine EditStage; el render seleccionado fue SONY y duró 6.122 s de FFmpeg. Se necesita medir por separado director-quality, audio-beats y selección de cámara, y hacer export forzada de iPhone. No compararlo causalmente con render 4101 s / 4 vCPU.

## Siguiente control
Instrumentación ligera con marcas monotónicas en un harness, o perfil con logs sin modificar `engine`; prueba forzada iPhone 4K en 2–4 s y comparación con Sony, con el mismo pipeline y contexto de carga, si Chema cede CPU. Documentar cámara seleccionada y tiempo por fase.
