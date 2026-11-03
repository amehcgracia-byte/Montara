# JÚPITER · EX-14H-14B — ABBA rendimiento real 15 s, ventana 600–615 s

Fecha de registro: 2026-11-04. Fuente: output completo de la ejecución FER en GCP 8-vCPU, checkout experimental de motor `0f9ec03`. Original HEVC equirect 3840×1920 con tramo 600–615 s, 450 frames a 30 FPS, destino Stage Reel horizontal 1920×1080 con master audio. EX07/EX13 opt-in flags A false/false, B true/true; sin modificaciones en producción; proyectos/cache aislados; trabajo uno por vez. Los tiempos de este ensayo NO incorporan hooks de hash BGR/mapa.

## Datos exactos

| orden | modo | Stage wall s | FFmpeg segmento s | bytes output |
|---|---|---:|---:|---:|
| 1 | A | 41.610 | 34.451 | 32873523 |
| 2 | B | 36.347 | 29.352 | 32875180 |
| 3 | B | 36.374 | 29.432 | 32875511 |
| 4 | A | 40.022 | 33.096 | 32874177 |

Stage A mean `40.816` s, B mean `36.3605` s, reducción **10.9185% (10.92% redondeado)**, ahorro **4.4555 s** por exportación de 15 s. Segmento FFmpeg A mean `33.7735` s, B mean `29.392` s, reducción **12.97%**. B1/B2 difieren 0.027 s; A1/A2 1.588 s. No afirmar significancia estadística de cuatro observaciones ni extrapolar a una jam multicámara.

Todos los runs nativos desde original HEVC, 450 cuadros por Stage, sin warnings; audio PCM idéntico SHA256 `267b89c2ce251dfe3511c50335acd4297a2bbfa7f2a26503bd576d3f3d0c6b12`. RGB final codificado y decodificado con hashes distintos (incluso A/A o B/B), como se observó en ensayos previos. La equivalencia exacta **anterior** del mismo tramo está en EX14H14B fidelidad 15s: mapas, input BGR y salida preencoder idénticos entre A/B 450/450.

Ejecución `--mode performance --duration 15 --window-start 600` completada y con limpieza de temporales reportada. MemAvailable ~30.4 GiB y disco libre ~18.66 GiB al inicio.

## Interpretación y próxima decisión

La ventaja Stage 10.92% a 15s concuerda con ABBA a 2s EX14H11F 11.37%; un solo tramo y dos repeticiones por variante no constituyen validación universal. Repetir mismo experimento `--mode performance --duration 15 --window-start 840` para contrastar material visual distinto, sin extender duración todavía. Luego valorar 18s y compilación de gate de integración selectiva de EX07/13 para Chema. Incidencia externa de apagado GCP #71: Cloud Audit Logs estableció `gcloud compute instances stop` desde macOS por identidad de Chema, no timer Linux; confirmar protección de procesos largos antes de cargas prolongadas.
