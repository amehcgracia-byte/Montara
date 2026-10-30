# JÚPITER — Comparativa observada 4 vCPU / 8 vCPU (2026-10-30)

## Procedencia y estado
- Rama `fernando/continuacion-montara`; suite `experiments/cpu_optimization/run_cpu_comparison_suite.py`.
- Operador ejecutó en VM con **8 vCPU y 31 GiB RAM**, carga inicial 0.00, bajo `montara-bench FER-CPU-COMPARISON-8VCPU`.
- Resultados locales: `/home/fer/montara-bench-8vcpu-20261030/` (manifest.json, logs, CSV/JSON). Git limpio.
- Duración reportada de subprocesses: 4.56 s intervalo; 2.09 s F4; 2.16 s cadencia. **Tres ejecuciones PASS**, pero el desglose numérico de cadencia no fue pegado aún.
- Baseline previo 4 vCPU procede de mensajes del operador: `benchmark_interval_index.py` tamaños 200/1000/3000 y F4 fixture reducida. Para comparación definitiva, recuperar los JSON originales y comparar revisión, versión y entorno.

## Datos 3.000 elementos: mediana en ms
| Caso | 4 vCPU original | 4 vCPU indexado | 8 vCPU original | 8 vCPU indexado |
|---|---:|---:|---:|---:|
| Scenes | 38.36 | 1.300 | 17.790 | 0.555 |
| Cues | 742.328 | 427.563 | 359.157 | 289.806 |

En 8 vCPU los speedups **dentro del mismo entorno** fueron escenas x32.056 y cues x1.239; en 4 vCPU x29.511 y x1.736. Comparar tiempos absolutos entre VMs **no identifica causalidad por número de núcleos**: este Python es predominantemente monohilo; puede cambiar CPU físico, frecuencia, concurrencia, scheduler y otros factores.

## F4 v360
- 8 vCPU: lanczos 0.325 s, bilinear 0.193 s, reducción mediana 39.8%, SSIM 0.994127.
- 4 vCPU (histórico): reducción mediana 45.67%, SSIM 0.994127.
- Fuente de **muy baja resolución**, 2 s, dos repeticiones y codificador con `--threads 2`: **no** valida calidad en 360 real ni escalado 4→8.

## Limitaciones y decisión
1. No se repitió el E2E Stage (anteriormente 410.831 s navegador / 195.097 s exportación; compartía CPU con procesos jm). No se permite una comparación 4/8 de exportación con ese dato.
2. La VM reiniciada perdió `/var/lock/montara/`. El operador lo restauró con `sudo install -d -o root -g root -m 1777 /var/lock/montara`. Considerar creación persistente controlada a futuro, previa coordinación.
3. Existe apagado/suspensión tras 40 min de inactividad; pendiente confirmar con Chema si reconoce FFmpeg/bench activos.
4. Próxima prioridad: **JÚPITER-OPT-06**, revisar evidencias Saturno GOP/selectivo e identificar experimento candidato de impacto. No repetir renders sin hipótesis y criterios claros.
