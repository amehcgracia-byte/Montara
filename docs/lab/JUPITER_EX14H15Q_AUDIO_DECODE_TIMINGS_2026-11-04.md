# JÚPITER EX-14H-15Q — coste de decodificación de audio original

Fecha: 2026-11-04. Ejecución manual en VM de pruebas, motor experimental `0f9ec03`, sin cambios productivos.

## Ensayo

Para cada original se ejecutó FFmpeg con `-i <fuente> -map 0:a:0 -vn -ac 1 -ar 22050 -f null -`, descarta la salida. Se cronometró desde Python con `time.perf_counter()`. No se escribió WAV ni vídeo.

| Fuente | Duración de vídeo | Tiempo de la prueba | Estado |
|---|---:|---:|---|
| `IMG_0044.MOV` — iPhone H.264 3840x2160, AAC mono 44.1k | 986.825 s | 3.520 s | OK |
| `VID_20260824_204524_00_004.mp4` — fuente 360 HEVC 3840x1920, AAC estéreo 48k | 911.640 s | 18.295 s | OK |

La fuente 360 tardó aproximadamente **5.20 veces** más en una pasada; la fuente iPhone fue más rápida en esta subetapa. El comando tiene `-vn` y no codifica WAV físico: no atribuir este diferencial a decodificación del vídeo HEVC ni extrapolarlo a `SyncStage` completo. La lectura/demultiplexado, diferencias de audio, tamaño de archivo y estado de caché SO podrían influir. Son medidas de **una sola iteración**, no benchmark reproducido.

## Contexto y cautelas

EX14H15I encontró offset independiente (t_iphone = t_360 - 19.0369s) mediante correlación PCM mono de tres ventanas; `SyncStage` nativo está aún sin ejecutar con estos dos originales. Los proyectos `montara-focus-*` referencian mapas de fixture 20s antiguos, no equivalen a una sincronización validada.

Implementación `core/stages/sync.py` versión 5 reutiliza WAV y envelopes mediante caché global y puede hacer fallbacks spectral/HPSS y verificaciones de tercios. El coste total no está medido y pueden dominar pasos posteriores. Mantener fuentes intactas y >12 GiB libres.

## Próximo paso

Repetir la decodificación audio con orden ABBA y timing por fuente, `-nostdin -hide_banner -loglevel error -map 0:a:0 -vn -ac 1 -ar 22050 -f null -`, guardar solo texto de las métricas. Usar repeticiones para evaluar efecto de caché caliente; posteriormente instrumentar fases internas de SyncStage de forma aislada, sin tocar producción.
