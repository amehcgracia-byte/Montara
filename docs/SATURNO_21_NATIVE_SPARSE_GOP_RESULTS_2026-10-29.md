# SATURNO-21 — Zucker native 360 sobre paquete de GOP selectivos

Fecha: 2026-10-29. Fuente primaria: [GitHub Actions 40921604948](https://github.com/amehcgracia-byte/Montara/actions/runs/40921604948), job 123616017541, conclusión operacional `success`. Script `experiments/saturno_21/native_sparse_reprojection.py`. Motor intacto `60a7b7e9a39077b36f45057811abd6a833a168ef`.

## Resultado medido y criterios

`SATURNO21_SUMMARY`: `status=NATIVE_SPARSE_GOP_AB_EXACT`; `AA_exact=true`; `AB_exact=true`; `frames_total=360`.

| Medida | Original A | Paquete B |
|---|---:|---:|
| Archivo MP4, bytes | 19756759 | 4383338 |
| GOP | 45 | 10 |
| Paquetes vídeo | 2700 | 600 |

Ahorro del contenedor: **15373421 bytes (aprox. 77.81%)**. Se conservaron los paquetes seleccionados con hash de payload y PTS/DTS idénticos. Dos ventanas: segundos [20,26] y [50,56], cada una de 180 cuadros. A, A_repeat y B produjeron dos fragmentos reproyectados de 180 cuadros; se observaron dos intervenciones QA en cada variante (una por ventana). La comparación de SHA-256 de los dos MP4 reproyectados fue exacta para A/A_repeat y A/B; también sus framehashes. El control `-fps_mode passthrough` se aplicó solo en memoria al decodificador, y `-threads:v 1` al codificador. Sin cambios al motor.

## Alcance científico

**Demostrado:** en un H.264 sintético de 90 segundos, GOP cerrados de 2 s, sin B-frames, el sistema de selección y reproyección 360 nativa de Zucker produce exactamente los mismos dos fragmentos de salida aunque se descarten 35/45 GOP (77.81% de bytes del contenedor).

**Pendiente:** un proyecto Stage completo con audio, inspección de color, corte/concatenación y B aislado de archivos originales; pruebas representativas con codificaciones reales, GOP abiertos/B-frames y tamaños típicos; transferencia de red medida y coste. La identidad exacta del montaje completo de SATURNO-18 se obtuvo con paquete conservador, no con este paquete selectivo. SATURNO-21 es una prueba de fragmentos reproyectados, no de la aplicación completa.

## Siguiente hito

Combinar selección de vídeo de SATURNO-21 con la integración completa y aislamiento de SATURNO-18 en un plan donde exista vídeo sobrante; primero analizar dependencias y adaptar fixture/plan con controles de hash, después ejecutar A/A/B integral de manera económica. Mantener el hito D (transferencias/costes remotos) como pendiente.

## Reproducibilidad

Run 40921604948; `SATURNO21_RENDER` para A, A_repeat y B; `SATURNO21_SUMMARY` y `SATURNO21_PRESERVED`; test script bajo `experiments/saturno_21/`. No edición de `main`, `engine` ni `mixer`. Tokens reales no disponibles.
