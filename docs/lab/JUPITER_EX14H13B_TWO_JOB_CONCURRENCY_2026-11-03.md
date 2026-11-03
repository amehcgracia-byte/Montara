# JÚPITER EX-14H-13B — Primer ensayo de dos trabajos simultáneos (8 vCPU)

Fecha: 2026-11-03. Trabajo en laboratorio FER aislado; VM GCP Linux 8 vCPU (afinidad 0..7), 31 GiB RAM. Experimento no productivo. Motor checkout experimental `0f9ec03`, flags EX07/EX13 TRUE (B). Dos trabajos `ExportStage.run` reales, cada uno 60 cuadros 360 HEVC, Reel 1920×1080 30 fps con audio, root/caché/proyecto distintos. Benchmark 1 pareja secuencial y 1 pareja simultánea; todos los archivos temporales eliminados.

## Incidente inicial y corrección
Primera ejecución: secuencial completó 16.723 s; fase paralela bloqueada por el umbral `load1>2.0` (2.10) tras generar carga con nuestros propios jobs. El load average incluye historia y no equivale a CPU ocupada instantánea. Corrección commit `c420691`: comprobar load estricto solo en preflight inicial; mantener guardas RAM, disco y tareas `jm` en todo el ensayo. No se lanzó el paralelo en primera prueba y esos datos NO se mezclan con el segundo intento.

## Segundo intento completo (éxito)
Preflight: 18.78 GiB libres, 30.37 GiB MemAvailable, load1 0.51.

| Configuración | Grupo wall | Stage jobs individuales | Segmentos individuales | Jobs/min |
|---|---:|---|---|---:|
| 2 secuenciales | 17.035 s | 5.791 / 5.816 s | 4.379 / 4.397 s | 7.044 |
| 2 paralelos | 11.656 s | 8.746 / 8.598 s | 7.343 / 7.045 s | 10.295 |

- Rendimiento del grupo +46.15% jobs/min, o **−31.57%** wall para completar los dos trabajos. A cambio la latencia media individual de Stage pasa de 5.8035s a 8.672s (**+49.43%**) con la concurrencia.
- 60 cuadros por job en cuatro trabajos; audio PCM hashes exactamente iguales, cada ejecución vídeo válido, fuentes originales intactas; **no** se comparó fidelidad del vídeo final entre los jobs.
- Los tiempos del grupo incluyen carga de proyecto, inicializaciones de Python, exportación Stage y verificación final de fotogramas/audio; por tanto se solapan también los preparativos y el post-procesado del verificador (y puede haber coste del propio runner). **No atribuir +46.15% a escalado del núcleo de render.** Jobs/min calculado sobre wall del grupo no es capacidad sostenida a lo largo de minutos/horas.

## Decisión y prioridades
1. **Uso individual actual de Chema:** favorecer latencia individual y estabilidad. No forzar concurrencia por defecto.
2. **Multiusuario futuro:** la concurrencia mejora throughput observado, pero penaliza latencia por trabajo; estudiar políticas de admisión y límites de CPU/hilos/memoria/datos. Dos trabajos no demuestran que 10 simultáneos sean viables.
3. **Próxima prueba científica:** hacer 2-3 ciclos breves de comparación alternada (secuencial/paralelo/paralelo/secuencial) con la misma fuente/flags, separar startup, Stage, comprobación hashes, y registrar presión CPU/RAM real de los trabajadores. Antes verificar que la VM compartida permanece libre y que hay espacio suficiente; no más de dos jobs a la vez.
4. Comparar después con cargas representativas, planos planos + 360, otros formatos y duración >2 s, preferentemente en entorno de benchmark no compartido.

No modificar producción, no ajustar FFmpeg global, no suprimir controles de seguridad de la VM, no fusionar el motor sin revisión de Chema.
