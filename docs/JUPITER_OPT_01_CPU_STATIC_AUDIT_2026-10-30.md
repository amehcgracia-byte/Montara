# JÚPITER-OPT-01 — Auditoría estática CPU-first, primera pasada (2026-10-30)

## Alcance
Repositorio `amehcgracia-byte/Montara`, rama `fernando/continuacion-montara` (árbol `c4e6320`), exclusivamente código del orquestador visible en GitHub. No se ejecutaron benchmarks ni se modificaron ZuckerVideos/ZuckerMixer. No hay extrapolación de resultados a otras CPU.

**Regla:** primero optimización algorítmica universal y equivalencia; parámetros de CPU adaptativos después. GPU y planificador híbrido: únicamente interfaces futuras, sin implementar.

## Hallazgos contrastados con código

| Candidato | Evidencia | Hipótesis | Riesgo / verificación |
|---|---|---|---|
| A. Remapeo de subtítulos después de borrar cortes | `show_cut_edit.py`, `delete_shot`: para cada nueva frase `cue` calcula `matches=[entry for entry in kept if ...]` sobre todos los `kept`. Bucle anidado O(C·K). | Barrido de intervalos ordenados / índice temporal reduce comparaciones cuando hay muchos subtítulos. | Hay que preservar exactamente la selección `max(matches, key=overlap)`, empates, texto corregido, y todos los tests. Pocos cues pueden no justificar complejidad. **Primer microbenchmark recomendado.** |
| B. Texto de escenas | `show_cut_edit.py`, `delete_shot`: cada escena crea texto con `' '.join(w for w,x,y in words if scene['start']<=x<scene['end'])`. O(S·W). | Preindexar tiempos e identificar rangos por búsqueda binaria, si las palabras están ordenadas y el contrato lo permite. | Verificar orden, solapamiento de escenas, marcas repetidas y comportamiento ante tiempos anómalos antes de cambiar nada. |
| C. Vista continua Show | `show_playback.py`, `render`: una entrada desde mínimo inicio al máximo fin, filtro `trim/atrim` para cada segmento, `concat` y codificación x264. | Para segmentos dispersos, estudiar si decodificar ventanas independientes ahorra trabajo; alternativa de caché por segmento. | Una entrada compartida puede ser más eficiente en escenarios densos. Desfase audio/vídeo y PTS deben ser bit a bit / a nivel de tolerancia verificados. No asumir mejora. |
| D. Probes repetidos de ventanas | `experiments/export_profile/benchmark_cadence_batch.py` ya prueba `ffprobe` individual versus intervalos agrupados y comprueba igualdad de timestamps. | Reutilizar resultados de esa investigación antes de inventar otra. | Es un experimento, no evidencia de adopción por todo el motor. |
| E. Caché de proxies | `local_media/proxies.py` tiene hit estadístico previo a `ffprobe` y protección por lock. | No volver a optimizar un fast path ya presente sin perfiles que evidencien un problema. | Respetar invalidación y coherencia. |
| F. Caché de ShowPlayback | `show_playback.py` usa hash de ruta/size/mtime/segmentos para reutilizar salida. | Investigar invalidación y hit rate antes de proponer caché nueva. | Versionar parámetros y evitar resultados obsoletos. |

## Priorización

**P1 experimental (sin FFmpeg):** A y B, porque muestran patrones de listas anidadas en el orquestador, conectados con Loop Interchange / sweep line / índices temporales; medir con datos sintéticos de diferentes tamaños y comparar igualdad de salida. No aplicar el cambio hasta superar tests funcionales de `delete_shot`.

**P2 perfil CPU de exportación:** consultar etapas y subprocesos en `experiments/export_profile` y el motor (con permiso/colaboración de Chema), porque el E2E Stage del 30/10 registró `export=195.097 s` con carga concurrente. El coste de FFmpeg probablemente domina sobre operaciones Python, pero **no está cuantificado**.

**P3 windows/GOP/ShowPlayback:** hipótesis de decodificación selectiva para fuentes con segmentos lejanos; banco de prueba aislado, equivalencia estricta y ejecución controlada bajo `montara-bench`.

## Plan para la siguiente iteración
1. Escribir un microbenchmark **stdlib** `experiments/cpu_optimization/benchmark_interval_index.py` sobre el patrón de escenas/palabras y/o cue-overlaps; exportar CSV/JSON con medianas y comprobación de igualdad.
2. Ejecutarlo con carga pequeña inicialmente; no requiere datos ni renders de Chema.
3. Con resultados positivos, preparar propuesta experimental revisable; **no** integrar en `show_cut_edit.py` directamente sin validar contratos ni resultados con Chema.
4. Medir sobre más de una CPU antes de hablar de escalabilidad proporcional. El objetivo es portabilidad funcional, no un speedup idéntico.

## Distinciones esenciales
- **Observado en código:** estructuras O(S·W) y O(C·K), caches de proxies/playback, interfaz de filtros.
- **No observado:** que esos bucles sean cuellos de botella significativos del E2E ni que aplicar tiling produzca beneficios en Python.
- **Hipótesis, NO resultado:** la búsqueda temporal y el barrido pueden reducir CPU en proyectos con grandes cantidades de escenas/subtítulos.
- **Estado:** auditoría estática parcial del orquestador. Revisión directa del código de engine/mixer pendiente; no confundirla con auditoría completa.
