# SATURNO-07 — Localización de la divergencia en el primer paso FFmpeg (2026-10-29)

## Evidencia reproducida con Zucker REAL
Instrumentación QA de `experiments/saturno_05/native_ab.py`: intercepta exclusivamente la función Python `core.stages.export._run_ffmpeg_progress`, conserva comandos, duraciones, SHA256 y hashes decodificados de cada salida intermedia en el momento de su creación. El motor y sus submódulos NO se modifican, ni `main`. Todos los proyectos QA fuerzan `force_rerender_segments=True` para evitar falsas igualdades de caché.

Ejecución [40865264794](https://github.com/amehcgracia-byte/Montara/actions/runs/40865264794): **A/A mismo archivo y ruta, fotogramas exactos del primer paso FFmpeg: 55/60, diferencias índices 53–57.** La etapa siguiente de salida mostró **55/60** y los mismos índices: **el primer desacuerdo ya existe en el primer segmento renderizado, no se crea en el ensamblado final**. A/B con copia byte idéntica y original oculto: **53/60** desde el primer intermedio, diferencias 53–59. El MP4 final conserva esa divergencia. Dos pasos FFmpeg en cada ejecución.

El comando del primer paso usa `-ss 4.000 -t 2.000` sobre cámara, `scale`, `format=yuv420p`, `eq`, `colorbalance`, `fps=30:round=near:start_time=0`, `trim=start_frame=0:end_frame=60`, `setpts=N/(30*TB)`, `fade`, `tpad`, filtros de espacio de color, reencode y una segunda etapa de unión. **Se observó por trazas**. La fase de divergencia se ha aislado al primer render, pero no se ha aislado el filtro concreto ni el origen exacto (PTS / extraer / escala / codificación).

## Control FFmpeg con un hilo de filter_complex
Ejecución [40865665003](https://github.com/amehcgracia-byte/Montara/actions/runs/40865665003). Se intercepta el comando en el proceso QA y se inyecta `-filter_complex_threads 1` inmediatamente antes de `-filter_complex` (sin editar Zucker). `SATURNO_QA_FILTER_THREADS_ONE=1`. Resultados A/A primer intermedio **53/60**, diferencias 53–59, y output final igual **53/60**. **FAIL: un hilo no elimina las diferencias**. No se puede afirmar que el paralelismo de filtros sea causa necesaria.

## Lectura de los resultados
- Se ha probado un recorrido real de `_render_plan`; es una prueba aislada de 2s, cámara plana, master compartido, no una edición Stage real con 360.
- Las diferencias del primer vídeo intermedio invalidan culpar de entrada a mux de audio o concat final.
- Los fundidos desactivados tampoco eliminaron la divergencia ([40862910889](https://github.com/amehcgracia-byte/Montara/actions/runs/40862910889)).
- **No afirmamos que Zucker sea no determinista universalmente**, solo que el mismo input produjo resultados distintos en estas condiciones con rerender forzado.
- Estabilidad A/A, exactitud B, audio independiente, 360 y rentabilidad siguen pendientes.

## Próxima prueba de mayor valor
Comparar `ffprobe -show_frames` (PTS/timescale, duración, número de imágenes) del input, el primer intermedio y el MP4 final. Registrar configuración y versión exactas de FFmpeg y hash del comando. Comparar salida antes/después de `fps` y `trim` con ejecutables de FFmpeg separados. Antes de alterar `core/stages/export.py`, discutir evidencias con José Manuel y acordar tolerancias de equivalencia.

**Estado:** causa aislada a primera fase de render; no existe A/B completo aprobado ni se han usado créditos RunPod.
