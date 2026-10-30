# JÚPITER-OPT-07C — Desglose del export manifest y siguiente decisión (2026-10-30)

## Origen
Salida íntegra de `performance` del fichero local `/home/fer/montara-e2e-01/data-stage/Projects/E2E stage.zuckervid/artifacts/export_manifest.json`, recuperada por el operador. Baseline: Stage E2E sintético de dos cámaras 720p, export YouTube 1080p, 6 segmentos; con carga FFmpeg compartida de jm durante el test. **No benchmark nuevo.**

## Datos
- `total_wall_sec=186.427`, `wall_sec=109.354`; `segment_workers=2`; `segment_count=6`; seis `cached=false`, seis `rendered_from=original`; `stream_copy_count=0`.
- `phases`: assembly `direct_concat_audio`; cadence 5.308 s; intro 30.824 s; outro 26.829 s; mux 1.702 s; source_prepare 0.0 s; source_proxy_count=0. Concatenación 0.0 s. **No sumar fases ni los tiempos FFmpeg como si fueran secuenciales: hay solapamiento.**
- Duraciones de montaje por segmentos de `edit_plan.json`, observadas en el preflight FOCUS A/C, usadas únicamente para normalizar tiempos:

| Segmento | Duración vídeo (s) | FFmpeg (s) | FFmpeg por segundo de vídeo (s/s) | Verificación (s) |
|---:|---:|---:|---:|---:|
| 1 | 3.567 | 36.097 | 10.12 | 2.466 |
| 2 | 3.600 | 33.826 | 9.40 | 2.764 |
| 3 | 6.633 | 64.501 | 9.72 | 3.932 |
| 4 | 2.533 | 26.828 | 10.59 | 1.932 |
| 5 | 1.533 | 11.233 | 7.33 | 0.923 |
| 6 | 2.133 | 23.349 | 10.94 | 1.971 |

El segmento 3 tiene **mayor tiempo absoluto, pero no necesariamente mayor coste relativo**; la variación depende de duración, contenido, posición en cola, recursos compartidos y opciones FFmpeg. Por tanto **no diagnosticarlo como fallo por ser el máximo**. Las verificaciones de segmentos suman 13.988 s de duración medida de tareas, no ahorro directo en wall-time.

## Datos ausentes
No hay por-segment CPU utilization, tiempo de decodificación vs filtro vs codificación, concurrencia real de jm, cache-hit en segundo export del mismo plan, ni pruebas con originales 4K/HDR/360. El formato del manifiesto no prueba qué parte forma el camino crítico ni da un desglose por filtros.

## Decisiones
1. **No optimizar mux ni concat**: mux 1.702 s; fases no dominantes según estas observaciones.
2. No crear otra caché: ya hay caché de segmento y de logo. No desactivar verificaciones para ganar segundos sin validar seguridad.
3. **Hipótesis prioritaria**: FFmpeg por segmento, empezar por segmentación/escala/decodificación y versión/adaptación del encoder; comprobar primero las opciones efectivas de comandos ya registrados o por lectura del motor. No cambiar motor en esta rama.
4. La mejora de `ffprobe -read_intervals` agrupado reduce 72.6% el microbenchmark (0.5378→0.1474 s), pero **no está conectada a un cuello de botella demostrado del exportador**; evitar un parche sin traza.
5. **ALTO A RENDERS**: última carga `30.64/27.21/16.22` con 8 vCPU. Coordinar con jm una ventana de CPU libre; `montara-bench` no coordina servicios jm independientes.
6. Al llegar los vídeos 5,7K / originales de mayor resolución, combinar test F4 con FOCUS A/C y generar un único perfil reproducible en vez de múltiples rondas.
7. Para trabajo intermedio sin muestras: auditoría estática de construcción de comandos FFmpeg en export y reglas existentes de selección de encoder, con hipótesis de optimización precisa, **sin ejecución ni cambio de pin**.

## Estado
`OPT-07C: DIAGNÓSTICO ESTÁTICO Y DE MANIFIESTO CERRADO`. El próximo objetivo `OPT-08` es auditar la receta de exportación por segmento y recoger evidencia de comandos reales en la siguiente prueba aprobada.
