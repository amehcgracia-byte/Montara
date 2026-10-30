# FOCUS A/C — primera muestra real 3 cámaras (2026-10-30)

## Ejecución aportada por operador
`montara-bench FER-FOCUS-AC-REAL-01`; script `experiments/media_optimization/focus_ac_real_stage_01.py` en rama `fernando/continuacion-montara`, ejecución local `/home/fer/montara-focus-ac-real-01/report.json`.

**PASS_REAL_MEDIA_HANDOFF_FIXTURE**, 14.995 s globales; preflight CPU 5.9 %, carga 1 min 2.94 sobre 8 vCPU. El exportador del motor resolvió los tres pares de rutas original/proxy. No se ejecutó el editor verdadero ni export final.

| Cámara | Original | Proxy | Duración proxy | Transcode |
| --- | --- | --- | --- | --- |
| iPhone H264 4K | 3,551,746,708 bytes | 640x360; 160,397 bytes | 4.004 s | 2.674 s |
| Sony H264 1080p | 570,452,494 bytes | 640x360; 258,570 bytes | 4.0 s | 1.771 s |
| 360 HEVC 3840x1920 | 2,521,799,326 bytes | 960x480; 278,101 bytes | 4.0 s | 3.026 s |

El script verificó el par tamaño/mtime de los originales antes y después, pero **no calculó SHA-256**. Los tiempos son solo de fragmentos de 4 segundos.

## Bloqueante funcional descubierto antes de siguiente etapa
Los proxies creados contienen el rango original `[10,14)` s, pero los segmentos del laboratorio declaran `clip_start_sec=10` tanto con fuente original como proxy. Ese tiempo **no está dentro del proxy recortado [0,4)**. Por ello el PASS demuestra resolución de rutas en `_segment_source_info`, no demuestra correspondencia temporal ni posibilidad de render real con esos mismos segmentos. Para la siguiente fase, establecer explícitamente `proxy_t = original_t - 10` y probar el mapeo para cada corte, o crear proxies que mantengan la línea temporal completa. Evitar modificar `clip_start_sec` en el plan final si la exportación espera tiempo absoluto del original.

Además, FFmpeg aplica autorrotación al iPhone (-180° de display matrix); verificar orientación visual y orientación declarada tras proxy y en salida original.

## Política VM comunicada por Chema
Autoapagado tras 1 h sin actividad web, 2 h sin teclas SSH; no se apaga con FFmpeg o `montara-bench` activos. **Todas las tareas largas y desatendidas deben usar `montara-bench`.** Los costes ~0.30 EUR/h fueron presentados como estimaciones, no comprobados por facturación.

## Decisión
Resultado útil y limitado: 3 pares reales correctos. Próximo gate: semántica de offsets + plan **realmente producido desde proxy** + export desde original, con coordinación de CPU. No declarar FOCUS A/C completado.
