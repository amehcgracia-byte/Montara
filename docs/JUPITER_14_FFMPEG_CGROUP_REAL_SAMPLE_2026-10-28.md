# JÚPITER-14 — Primer benchmark FFmpeg aislado bajo cgroup (28 oct 2026)

**Resultado real ejecutado, parcial.** Máquina de ejecución del asistente (NO Oracle, NO Google, NO RunPod, NO Montara E2E): Linux con `cpu.max=400000 100000` (cuota 4 núcleos) y `memory.max=4294967296` (4 GiB). FFmpeg local. Fuente sintética `testsrc2` 1280x720, 30 FPS, 24 s, H.264. Para cada ejecución: ocho trabajos de 8 s, filtrado escala 960x540 + brillo distinto, libx264 `veryfast`, CRF 24, `-threads 1` para decodificador y codificador. Cada ejecución procesa los ocho clips con 1, 2 o 4 trabajos FFmpeg simultáneos. Salidas suman 6.565.642 bytes por ejecución; no se hizo validación perceptual audiovisual.

## Medidas observadas (no inventar faltantes)
| Nº procesos paralelos | Ejecución | Wall seconds | Pico observado memory.current |
|---:|---:|---:|---:|
| 1 | 1 | 10.930 | 742,551,552 bytes |
| 2 | 1 | 6.116 | 836,177,920 bytes |
| 4 | 1 | 4.976 | 1,015,742,464 bytes |
| 4 | 2 | 4.711 | 1,022,431,232 bytes |
| 2 | 2 | 6.181 | 856,338,432 bytes |

La ejecución completa planificada de 9 rondas se interrumpió por límite de tiempo de herramienta tras estas cinco; **no tenemos tres muestras por configuración, ni mediana de 1 trabajador**. Los picos de memory.current son del *cgroup total* (incluye otros procesos/cache) y muestreados durante las operaciones, NO RSS específico de FFmpeg. Son procesamientos de muestra sintética muy corta, no representan render 360 o multicámara.

## Interpretación
- Primer pase: 4 trabajos terminan un 54.5% más rápido que 1 en este ensayo, aun cuando CPU total tenga cuota 4. 2 también supera 1; 4 supera 2 (~18.6% en comparación de primeros pases).
- Esta observación contradice adoptar a ciegas la heurística experimental `floor(effective_cpus/2)`, que con cuota 2 CPUs propone 1 trabajador; NO demuestra cuánto deberían usar 2 CPUs porque este benchmark fue con cuota **4**, ni valida 8 trabajos.
- No demuestra por sí solo riesgo de OOM del motor actual, ni acelera el motor. La propuesta sigue siendo observar y respetar cgroups, sin fijar un número de workers a priori.
- Próxima prueba: benchmark de Montara/Zucker del mismo montaje real congelado en contenedor de QA con 2 CPU/8 GiB y límites host significativamente mayores, comparando 1/2/4 workers, cold/warm, memory.peak y calidad completa. No tocar `main` ni submódulos antes de este A/B.

## Fuente de experimento
Los comandos ejecutados eran equivalentes a generar un `testsrc2` 1280x720 H264 y lanzar 8 procesos:
`ffmpeg -threads 1 -i source.mp4 -vf scale=960:540,eq=brightness=... -t 8 -an -c:v libx264 -threads 1 -preset veryfast -crf 24 out.mp4`.
No se lanzó la suite de Montara.
