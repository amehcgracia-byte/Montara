# JÚPITER-OPT-07B — Cadencia recuperada y ventana de rendimiento (2026-10-30)

## Evidencia recuperada de logs existentes
Origen: salida del operador de `/home/fer/montara-bench-8vcpu-20261030/cadence.log`; vídeo fixture `cam-360.mp4`, 7 ventanas de 2 s, 3 repeticiones:
- Individuales: 0.5815, 0.5378, 0.5308 s; mediana **0.5378 s**.
- Agrupadas: 0.1662, 0.1474, 0.1396 s; mediana **0.1474 s**.
- Medianas: reducción **72.59 %**, 3.6486× en el microbenchmark; comparación de timestamps `true` en las tres repeticiones.
- No atribuir este ahorro al render Stage: aún no se ha probado que el motor repita consultas equivalentes en su ruta crítica. No cambiar ZuckerVideos sin trazado causal.

## Salud del laboratorio
- `find` mostró aviso por directorio de trabajo `/home/fgardel00` inaccesible para `fer`, pero sí encontró `/home/fer/montara-e2e-01/data-stage/Projects/E2E stage.zuckervid/artifacts/export_manifest.json` (13.450 bytes). Solución para futuras lecturas: `cd /home/fer` dentro del shell de fer.
- `uptime`: **load averages 31.12 / 26.10 / 14.78** sobre 8 vCPU, equipo compartido. **No lanzar benchmarks/render ni inferir velocidad bajo esa carga.** Las causas de la carga no se han verificado.
- El manifiesto existe, pero todavía **no se ha inspeccionado su estructura ni fases críticas**. Siguiente paso: extraer localmente en Python stdlib solamente claves y `performance`, sin rutas completas ni datos de usuarios; no subir manifiestos privados a GitHub.
- Si el vigía de apagado está activo, una sesión SSH no garantiza permanencia; lecturas cortas no requieren lock; trabajo prolongado debe protegerse con `montara-bench`.

## Decisión
Continuar en modo estático y de lectura. OPT-07B no constituye certificación de una mejora de exportación. Próximo análisis: manifiesto de fases/solapamientos y confirmar si hay evidencia de llamadas `ffprobe -read_intervals` en la ruta de exportación antes de proponer parche.
