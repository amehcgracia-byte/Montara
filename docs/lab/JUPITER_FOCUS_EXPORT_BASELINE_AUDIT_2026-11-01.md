# JÚPITER — FOCUS EXPORT: auditoría previa, sin benchmark (2026-11-01)

## Objetivo
Decidir el primer experimento causal de exportación sin duplicar laboratorios, sin modificar `engine/` y evitando renders largos en VM compartida.

## Evidencia existente
1. `main:docs/lab/RUNS.md`: Chema 2026-10-30, 4 vCPU, 654s salida, export 4101.5s; 8 vCPU, 628s salida, export 1388.1s. **No son A/B**: CPU, fuente, cantidad de cámaras, encuadres y mezcla 360 cambiaron simultáneamente.
2. `main:docs/lab/INVENTORY-FER.md`: F7 (siete ffprobe vs uno) ahorro menor, baja prioridad; F4 interpolación v360 candidata; F8 proxy esférico bajo demanda había supuesto ~866s desaprovechados en un caso histórico; no atribuirlo a cada export actual.
3. `fernando/continuacion-montara:docs/lab/JUPITER_F4_REAL_360_CLOSURE_2026-11-01.md`: muestra 360 HEVC real, 5s, bilineal 9.17s vs Lanczos 14.90s, ahorro 38.46%, SSIM 0.990657. **Microbenchmark de v360 no E2E**.
4. FOCUS A/C: validación de edit proxy→export original; mini Sony e iPhone 4K real; no repetir mecánica de relink salvo regresión.
5. `main:docs/lab/STATUS-JM.md`: PR #59 registra paso de puntuación de planos sobre proxy ligero, reduciendo redundancia previa.

## Hallazgo de arquitectura a revisar antes de optimizar
`zucker_videos:core/stages/export.py` (rama `claude/show-after-44`) declara `SPHERICAL_EXPORT_MOTION_MODE = "native_remap"` y conserva ruta `v360` para holds estáticos. La prueba F4 con filtro FFmpeg `v360` **no prueba la mejora del camino dinámico native_remap predominante**, ni conocemos la cuota real de cada modo en los renders de Chema. No sugerir un simple cambio global de `interp` sin inspeccionar las llamadas y costes efectivos.

## Preguntas científicas priorizadas
A. ¿Cómo se reparte wall-time de export entre vídeo plano original, 360 estático, 360 dinámico/native_remap, intros/transiciones y composición final? Sin tiempos por segmento/método es imposible atribuir mejora global.
B. ¿Qué proporción de fotogramas exige ruta 360 dinámica, y cuánto cuesta proyección vs decodificación y codificación? Comparar solo con control mismo input, encoding, resolución, número de hilos, segmentación, VM y caché.
C. ¿Hay costes repetidos evitables ya contemplados por caché global/versionado, o preparación esférica cuando no se usa? Inspeccionar el código actual, no suponer que el hallazgo histórico persiste.
D. Condiciones de éxito: comparación A/B de mismo segmento real, calidad visual y duraciones, no solo SSIM ni wall-time; CPU compartida con Chema y disco limitado.

## Decisión actual
**Fase EX-00 documental aprobada**; siguiente paso EX-01 es SOLO mapa estático de funciones y manifiestos/timestamps ya producidos. Evitar benchmark costoso hasta determinar qué modo 360 se usa, si hay telemetría aprovechable y qué medición mínima falta. No tocar engine ni main. Una única candidata A/B después de la auditoría de instrumentación, y cierre si no demuestra impacto.
