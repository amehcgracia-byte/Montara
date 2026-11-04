# JÚPITER EX-14H-15R — Audio FFmpeg ABBA iPhone vs HEVC 360

Fecha 2026-11-04. Ensayo manual read-only en GCP VM; sin WAV, MP4 ni modificaciones a originales. Mismo comando que EX14H15Q: `ffmpeg -hide_banner -loglevel error -nostdin -i <source> -map 0:a:0 -vn -ac 1 -ar 22050 -f null -`, ejecutado en orden A-B-B-A, cronómetro Python monotónico perf_counter.

| Repetición | Fuente | Tiempo |
|---|---|---:|
| A1 | IMG_0044.MOV iPhone 4K, H.264, 986.825s, AAC mono | 5.307 s |
| B1 | VID_20260824_204524_00_004.mp4 360 HEVC, 911.64s, AAC estéreo | 6.929 s |
| B2 | 360 | 9.839 s |
| A2 | iPhone | 6.723 s |

Medias A = **6.015s** y B = **8.384s**, relación B/A = **1.39x**. Una sola ejecución previa EX14H15Q arrojó A=3.520s y B=18.295s (relación 5.20x). Hay variación sustancial; no atribuir diferencia a un códec de vídeo, FFmpeg excluye vídeo de salida, ni concluir estabilidad estadística con n=2 por grupo.

Conclusión: extracción/decodificación audio iPhone de ~3.5–6.7 segundos en los ensayos realizados, insuficiente por sí sola para explicar esperas largas que Chema haya observado. Posibles costes posteriores en `SyncStage`: `librosa` de audio completo, FFT + lazo Python por todos los offsets, fallbacks spectral/HPSS ante baja confianza, verificación en tres tercios. Todavía **no se midió `SyncStage` nativo** sobre estos originales. La hipótesis de una causa de lentitud específica del iPhone no ha sido demostrada.

Referencia acústica independiente EX14H15I: t_iphone ≈ t_360 − 19.0369s, tres ventanas estables con dispersión 31.75ms; contraste nativo pendiente. Notar convención de SyncStage: `master_time = clip_time + offset` (puede cambiar el signo según qué archivo se elija master).

Próxima prueba: instrumentación aislada de SyncStage, no realizar otra ronda solo de extracción FFmpeg; medir extracción/caché, onset, búsqueda, fallbacks y verificación, con fuente de verdad acústica y recursos limitados. No alterar producción ni limpiar cachés existentes; espacio libre previo ~20GiB.
