# JÚPITER EX-14G-02 — Coste de fallback VideoToolbox en Linux

Fecha 2026-11-03. Rama `fernando/continuacion-montara`. **Benchmark sintético real informado por operador; no es Stage E2E.**

## Hipótesis y código
En ZuckerVideos `claude/recover-montara-engine`, `core/stages/export.py::_render_segment`, salvo `force_cpu`, se construye primero `_video_encode_args("h264_videotoolbox", ...)` y se llama a `render(command)`. Ante `FFmpegError` cae a `libx264`. La VM GCP de FER (Linux Ubuntu, 8 vCPU, FFmpeg 6.1.1-3ubuntu5) reporta `libx264` disponible y no anuncia `h264_videotoolbox`; el script de microbenchmark confirmó que uno falla y el otro funciona. Los logs de export existentes no registraron menciones a VideoToolbox (EX-14G-01), resultado no concluyente por el sistema de logging temporal.

## Medición
Preflight: CPU 0,4% en muestra 2s; load1 2,76; 0 procesos FFmpeg observados antes del benchmark. Fichero sintético lavfi `testsrc2`, 320x180, 15 fps, duración 0,4s (6 fotogramas), salida MP4 temporal. Cinco rondas alternando orden entre intento fallido `h264_videotoolbox` y codificación correcta `libx264` con `subprocess.run`, cada ejecución con timeout 15s. Se confirmó fallo del primer codec y éxito del segundo. Sin modificación del repo ni medios personales. Temporales eliminados.

| Ronda | VideoToolbox fallo (ms) | libx264 éxito (ms) |
|---:|---:|---:|
| 1 | 70.60 | 109.90 |
| 2 | 70.42 | 101.21 |
| 3 | 75.63 | 103.85 |
| 4 | 73.79 | 111.53 |
| 5 | 68.88 | 105.69 |
| Mediana | **70.60** | **105.69** |

La ruta fallback estimada por suma de medianas sería 176.29 ms frente a 105.69 ms para ir directamente a libx264 **en esta prueba artificial**. El ahorro estimado por segmento sería 70.6 ms; por seis segmentos 423.6 ms, por 20 segmentos 1.412 s, por 100 7.06 s **solo si todos recorrieran una ruta de fallo equivalente y si el costo fuera el mismo**. En el benchmark real de export FOCUS A/C seis planos total 43.365s, ese ahorro hipotético sería ~0.98%, no medido causalmente.

## Alcance y cautelas
- Microprueba con fuente lavfi, 320x180, sin los filtros y fuentes de Stage; no mide sobrecoste exacto del intento en el método Zucker.
- El esquema `_render_segment` puede fallar con `SegmentInactivityError`, tener render 360 nativo o entrar por `force_cpu` y `stream_copy`; **no extrapolar a todos los planos** ni a Mac.
- El proceso y librerías del FFmpeg fallido pueden arrancar de forma distinta bajo filtros de Stage; sin registro explícito de latencia de fallback y comandos efectivos, cuantificación global desconocida.
- Pequeña ineficiencia: **no atribuir a ella las exportaciones largas**. Nunca saltarse verificación ni cambiar parámetros de encoder por este dato.
- Un posible parche por plataforma, bajo flag y PR revisable, debe preservar VideoToolbox en macOS y sus fallbacks por fallo real; priorizar después de costes 360 importantes.

## Decisión
**Hipótesis de fallo confirmada para FFmpeg Linux; coste microbench ~70.6 ms; prioridad BAJA para speedup Stage.** Cerrar nuevas iteraciones de microbenchmark hasta que surja motivo para corregir ruta por plataforma. Priorizar perfil 360 y export Stage real con instrumentación ya existente, evitando duplicar SATURNO y JÚPITER previos.

EX14G_02_MEDIDO_Y_DOCUMENTADO.
