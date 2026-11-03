# JÚPITER — EX-14H-14B · Dos ventanas 15 s, rendimiento ABBA consolidado

**Registro:** 2026-11-04. Laboratorio FER VM GCP 8 vCPU / 31 GiB RAM, motor experimental aislado `0f9ec03`, fuente original HEVC equirectangular 3840×1920 911.64s, Stage real Reel 1080p30, 450 cuadros por export; audio máster 20s. EX07/EX13 flags opt-in A(false/false), B(true/true). Sin cambios productivos. Cada corrida con proyecto y caché aislados; cuatro exportaciones secuenciales A-B-B-A por ventana; ninguna instrumentación pesada de mapas/BGR en esta batería de rendimiento.

## Resultados íntegros de las ocho ejecuciones

| Tramo original | Run | Variante | Stage wall s | Segment FFmpeg s | MP4 bytes |
|---|---:|---|---:|---:|---:|
| 600–615s | 1 | A | 41.610 | 34.451 | 32873523 |
| 600–615s | 2 | B | 36.347 | 29.352 | 32875180 |
| 600–615s | 3 | B | 36.374 | 29.432 | 32875511 |
| 600–615s | 4 | A | 40.022 | 33.096 | 32874177 |
| 840–855s | 1 | A | 40.803 | 33.864 | 33135031 |
| 840–855s | 2 | B | 35.742 | 28.821 | 33134985 |
| 840–855s | 3 | B | 35.284 | 28.338 | 33138454 |
| 840–855s | 4 | A | 40.546 | 33.486 | 33132575 |

| Ventana | Mean A Stage | Mean B Stage | Stage ahorro | Mean A segment | Mean B segment | Segment ahorro |
|---|---:|---:|---:|---:|---:|---:|
| 600–615 | 40.8160 | 36.3605 | 10.92% | 33.7735 | 29.3920 | 12.97% |
| 840–855 | 40.6745 | 35.5130 | 12.69% | 33.6750 | 28.5795 | 15.13% |
| **Combinado** | **40.74525** | **35.93675** | **11.80%** | **33.72425** | **28.98575** | **14.05%** |

Por exportación de 15s Stage se ahorraron en media **4.8085s**. Descriptivo para material y configuración probados, no intervalo de confianza ni predicción global de jam. Los dos ABBA muestran mejora y ambos B fueron más rápidos que ambos A dentro de cada ventana. Estas son 8 exportaciones totales de rendimiento, 4 por ventana; fidelity se realizó como batería adicional aparte.

## Gate de fidelidad previo

En EX14H14B `--mode fidelity --duration 15` para ambos mismos tramos, dos A/B por tramo, 900 fotogramas de entrada BGR A/B idénticos, 900 fotogramas reproyectados BGR preencoder idénticos, 900 mapas equivalentes, y audio PCM idéntico. En las 8 corridas de rendimiento audio PCM también idéntico SHA256 `267b89c2ce251dfe3511c50335acd4297a2bbfa7f2a26503bd576d3f3d0c6b12`, cada vídeo 450 fotogramas y sin warnings. Hashes RGB MP4 finales cambian incluso en dos A o dos B, variación conocida tras remap, no aprobada como equivalencia final de contenedor/píxel.

## Condiciones de entorno

Preflight ambos tests: disco libre ~18.66 GiB y MemAvailable ~30.4 GiB. Limpieza de temporales confirmada por el runner `EX14H14B_COMPLETE`. El apagado externo GCP del 03-11-2026 22:39:30 UTC fue identificado mediante Cloud Audit Logs como orden `gcloud compute instances stop` autenticada con la cuenta de Chema, desde cliente macOS `from-script/True`, issue #71. Este evento fue anterior a estas mediciones. No afirmar que controles dentro de VM protegen frente a scripts externos.

## Interpretación científica y próximos gates

- Mejora 10.92–12.69% en dos ventanas largas, compatible con 11.37% de EX14H11F en 2s. El tramo fijo EX14H14A (1 mapa por 60 cuadros) no debe extrapolarse a escenas en movimiento: el ahorro principal procede de creación de mapas.
- Motor actual `affe97a4` no ha sido actualizado ni flags activados por defecto. EX06 interp=bilinear sigue separado por cambio visual.
- Aún faltan fuentes de vídeo distintas, movimientos/presets alternativos en segmentos largos, exportación multi-cámara de duración real, pruebas macOS Metal/Windows y evaluación perceptiva del output final.
- Propuesta: un ABBA corto independiente de 18s (máster 20s y fuente suficiente) si la política de autoshutdown externa está controlada; posteriormente no dedicar más tiempo al mismo HEVC sino preparar dossier de revisión selectiva para Chema y ampliar diversidad de fuentes.
