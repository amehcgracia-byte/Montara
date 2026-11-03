# JÚPITER EX-14H-15G — Audio iPhone 4K vs HEVC 360, estimación de 97 s sin confirmar

Fecha: 2026-11-04. Dos fuentes originales montadas sin copiar: `/home/fer/lab-clips/originales/IMG_0044.MOV` (H.264 3840x2160, AAC mono 44100, 986.825s) y `/home/fer/lab-clips/originales/VID_20260824_204524_00_004.mp4` (HEVC 3840x1920, AAC estéreo 48000, 911.64s). Metadatos de creación sugieren arranques a 18:43:47 UTC y 18:45:24 UTC respectivamente, diferencia nominal 97 s. No se ha validado exactitud de relojes ni continuidad de grabación.

## Ensayo independiente exploratorio

Script de terminal usó `ffmpeg -ss ... -t 20 -ac 1 -ar 4000 -f f32le pipe:1` para 3 ventanas 360, y la ventana iPhone desplazada 97 s. Correlación cruzada scipy.signal.correlate FFT en ±8 s, con normalización RMS de cada ventana y reporte del pico absoluto, sin descarte formal de periodicidades.

| ventana 360 | residual correlación | pico absoluto |
|---|---:|---:|
| 10–30s | +3.1568s | 0.0569 |
| 310–330s | −0.9045s | 0.0448 |
| 610–630s | +3.1915s | 0.0493 |

**Resultado: INCONCLUSO, no PASS.** Los picos son débiles y las tres ventanas no tienen residual consistente. Dos de ellas están cerca de +3.17s, insuficiente para atribuir sincronía: patrón musical recurrente o ruido posible. La búsqueda estuvo limitada a ±8s desde 97s; no descarta sincronía a offsets mayores ni demuestra fallo del motor. Proyecto `montara-focus-*` tiene `sync:done` heredado, ruta única `/home/fer/montara-e2e-01/data-stage/Projects/E2E stage.zuckervid/artifacts/sync_map.json` que corresponde a clips artificiales camera-a/b de 20s con 0s offset; no prueba sincronía de iPhone/360 originales.

## Próxima investigación

Búsqueda gruesa audio de offsets de mayor amplitud y picos múltiples, con normalización energética correcta de ventana deslizante y corroboración en tres tramos antes de integrar SyncStage. No modificar originales, no dejar cachés ni exportaciones, no suponer que los relojes tienen exactitud sub-segundo. Los resultados numéricos preliminares deberán etiquetarse candidatos, no sincronización validada, hasta confirmación independiente por transitorios y concordancia de tres ventanas.

Motivación: proporcionar a EX-14H-15 un gate real de sincronización iPhone y 360, separado del experimento EX07/13 de optimización de reproyección Stage.
