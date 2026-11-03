# JÚPITER EX-14H-12F — 8 vCPU, Stage x264 threads y planificación de recursos

Fecha 2026-11-03. Ensayo experimental de laboratorio FER, NO sistema productivo, sin integración. Los datos proceden del output del usuario de `ex14h12f_real_stage_encoder_thread_budget.py`, modo 360 HEVC original -> Stage Reel 1080p30, 2s/60 frames, 1 ejecución por configuración, flags EX07/13 OFF.

## Corrección explícita de máquina
- **VM actual GCP: 8 procesadores lógicos visibles al proceso** `os.cpu_count()=8`, afinidad `[0,1,2,3,4,5,6,7]`. En etapas anteriores la VM tenía 4 vCPU; **no describir la máquina actual como 4 vCPU**. RAM e instancia concreta actual requieren comprobarse de nuevo; 8 lógicos no demuestra núcleos físicos dedicados ni exclusividad de uso.
- **Dónde ocurren nuestras pruebas**: EX14H11-12 realizadas en la VM Linux, en `/home/fer/zucker-videos-ex14h09`, utilizando FFmpeg `/usr/bin/ffmpeg` instalado **en la VM**. No se ha probado el ordenador personal de FER, ni se ha ejecutado su Companion, ni GPU Vulkan real.
- En producción, `ffmpeg` corre **donde se lanza el proceso**: Stage render local via Companion cuando proceda, en servidor para pipeline remoto, no «necesariamente en navegador». La interfaz web orquesta; confirmar topología concreta por tipo de export y versión en vez de universalizar.
- Producto hoy: prioritario uso individual de Chema para QA; **10 jobs simultáneos no son su flujo actual**. Concurrencia y reparto multiusuario son una línea separada de diseño futuro. No ejecutar diez renders sobre VM compartida por defecto ni reclamar capacidad a partir de un microbenchmark.

## EX-14H-12F — datos
| libx264 output threads | Stage wall s | Segment s | Bytes MP4 |
|---|---:|---:|---:|
| 2 | 6.748 | 5.322 | 4521413 |
| 0 automático | 6.451 | 5.058 | 4469950 |
| 1 | 8.484 | 7.063 | 4574464 |
| 4 | 6.428 | 5.028 | 4492113 |

- En cuatro ejecuciones **audio PCM idéntico** (`e6215d07a7acf3fb6292e4a0c32c05d93769d9bf61bff60ef274b9d101ab16e3`) y 60 frames; MP4 y RGB decodificados difieren. No se midió calidad objetiva/perceptual entre threads.
- Orden fijo 2,0,1,4, **n=1 por opción**. NO inferir que 4 gana a automático por 0.023 segundos (3.6 décimas porcentuales); ventaja indistinguible de ruido sin repeticiones. El modo 1 hilo sí sale mucho más lento en esta muestra, pero n=1 no determina una regla global.
- El propio Stage utiliza `libx264 -preset veryfast` y **no pone `-threads`**, por lo que ya utiliza selección automática y no se puede añadir el ahorro aislado EX14H12D 39.38% como mejora de producción.

## Literatura y documentación contrastadas
- FFmpeg `threads=0/auto` selecciona automáticamente, `thread_type` distingue frame/slice threading; documentación https://ffmpeg.org/ffmpeg-all.html.
- *Heterogeneous cloud resource allocation: a case study on real-time transcoding in live streaming*, Li et al., *Expert Systems with Applications* 298 (2026), 129700, DOI https://doi.org/10.1016/j.eswa.2025.129700; modelo proactivo-reactivo de recursos heterogéneos para transcodificación. Orienta **diseño futuro del scheduler**, no demuestra mejoras en Zucker Stage.
- *Joint Configuration Optimization and GPU Allocation for Multi-Tenant Real-Time Video Analytics on Resource-Constrained Edge*, IEEE TMC 24(2) 2025, DOI https://doi.org/10.1109/TMC.2024.3465434. Ajuste conjunto carga y recursos, pero aplica analytics DNN, no a render x264 puro; solo analogía.
- *Octopus: Accuracy-aware resource scheduling for multi-video streaming inference at the edge*, *Computer Networks* 275 (2026), 111887, DOI https://doi.org/10.1016/j.comnet.2025.111887. Nuevamente inferencia DNN, transferibilidad limitada.
- Revisión multilingüe: consultas incluyeron inglés y chino, pero **no hay barrido exhaustivo por todos los idiomas ni todas las universidades**. Para hipótesis posteriores priorizar fuentes primarias, repositorios chinos (CNKI/arXiv) y japoneses/alemanes si hay términos y valor claro. No prometer cobertura universal.

## Agenda de dos carriles
**Carril actual — Chema uso individual**: más escenas reales, fidelidad de EX07/13, medir Stage/Push completo, CPU/RAM, confirmar encoding/filtros y necesidades macOS/local. Comparar ahorro frente a costo/fiabilidad.
**Carril exploratorio — Montara multiusuario futuro**: modelo per-job de CPU, memoria, disco, origen local/VM/GPU, latencia de transferencia; medir throughput y latencia con **máximo dos** renders simultáneos sobre VM compartida y solo si no hay trabajos activos, con protección de CPU/disco/RAM. Preferible tests fuera de horas de Chema. Scheduling adaptable, no activar diez procesos ni presuponer capacidad. Diferenciar 'auto threads por encoder' de 'admission control' por trabajo y de core affinity.

## Siguiente tarea pendiente
Primero usar monitorización read-only de CPU/RAM/carga real y estado de procesos compartidos, después pequeño contraste A/B de dos jobs aislados en procesos distintos (NO threads compartidos Python; cada job con root y proyecto propios), en ventanas seguras, con límite de tiempo, presión y disco, y sin riesgo de cortar los servicios productivos. Si la VM está ocupada, no lanzar.
