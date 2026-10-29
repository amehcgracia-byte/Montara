# SATURNO — Informe de ejecución real A/B y puerta pendiente (29-10-2026)

## Alcance y veredicto
**Hallazgo significativo:** el renderizador **real** `core.stages.export._render_plan` de Zucker produjo B con el original de cámara oculto; el paquete regenerado contiene exactamente los mismos fotogramas decodificados en la ventana solicitada antes de entrar en Zucker, pero en la última ejecución el output B diverge de A en **los índices 57, 58 y 59 de 60**. **Criterio de aceptación C: FALLIDO (57/60), no aprobado.**

Esta prueba aislada usa un solo clip plano `cam-fixed.mp4`, 2s de `reel_horizontal`, un máster MP3 original compartido. **No es la edición Stage de tres cámaras y movimiento 360.** No demuestra que un paquete mínimo libre de originales de todos los tipos se pueda importar a Zucker.

## Evidencias CI y resultados
- Stage E2E principal en `main` histórico: https://github.com/amehcgracia-byte/Montara/actions/runs/40679255918 pasó Stage, Push, Mix, Session. No proporciona baseline de paquete parcial.
- Stage en rama de investigación: https://github.com/amehcgracia-byte/Montara/actions/runs/40857115100 falló porque el runner carecía de FFmpeg. Corregido.
- https://github.com/amehcgracia-byte/Montara/actions/runs/40857477670 falló esperando la transición `#cameras/#making` tras 120s, antes de render.
- https://github.com/amehcgracia-byte/Montara/actions/runs/40858399424 falló por YAML CI inválido, corregido.
- https://github.com/amehcgracia-byte/Montara/actions/runs/40858502289 volvió a fallar en la transición incluso con 300s; no produjo `render.mp4`. Los artefactos no pudieron subirse por cuota CI agotada. Evidencias importantes legibles en logs.
- https://github.com/amehcgracia-byte/Montara/actions/runs/40858961342: render aislado A y B de Zucker con dos segundos; pixel SHA distinto. Paquete 327533 bytes, original 1416641; output A/B 501795 / 501834 bytes; tiempos 5.93 / 5.88 s. Original B no se ocultó en este primer pase.
- https://github.com/amehcgracia-byte/Montara/actions/runs/40859368866: original oculto durante B; **55/60** fotogramas idénticos, ambos outputs 60 frames, 2s. B demuestra render sin el clip fuente accesible, pero no igualdad completa.
- https://github.com/amehcgracia-byte/Montara/actions/runs/40859730136: paquete con 1s de contexto previo/posterior; **53/60** frames iguales. Aumentar padding no resuelve por sí solo.
- https://github.com/amehcgracia-byte/Montara/actions/runs/40860115536: misma variante con diagnóstico antes de exportar. Hash de píxeles decodificados de fuente 4–6s == paquete 1–3s: `62d437e0f15f98aa77d7f81df5b86805a59f06149a0f0a0ca97ef25e26359c92`; **17.280.000 bytes** cada uno. A/B export duran 2s y 60 frames, **57/60** hashes por frame iguales, diferencia exactamente en frames **57,58,59**. Render A **4.68s**, B **5.19s** (solo dos ejecuciones, no inferir tendencias); output **501761 vs 501760 bytes**; paquete vídeo **577828 bytes** (40.789% del original de cámara, 1416641 bytes), excluye máster y overhead. `original_absent_during_B=true`. `status=FAIL_NATIVE_AB_PIXELS`.

## Interpretación científica
El paquete de 4s con codificación H264 lossless demuestra igualdad **pre-render** de la ventana decodificada elegida, y B se renderizó sin el fichero original de vídeo. La divergencia final se introduce en el recorrido de exportación, o por tratamiento de PTS/cadencia/terminación diferente por origen, **pero no se ha aislado el componente causal exacto**. `_segment_video_command_base` aplica `-ss` y `-t` a los dos orígenes con tiempos relativos distintos; `_segment_filtergraph` aplica `_exact_cadence_filter`, fades de entrada/salida y `tpad`. Los tres fotogramas al final orientan la investigación, no prueban la causa concreta. No modificar el motor a ciegas.

**El corte con `-qp 0` no es cierre GOP mínimo ni stream copy y sí usa recodificación en la fase de preparación.** La reducción de bytes observada se limita a este minifixture, no a 80GB. El máster audio completo sigue a disposición de B; no es teletransporte audiovisual completo aislado. Ninguna prueba 360 nativa.

## Estado de los cuatro hitos
| Hito | Resultado |
|---|---|
| A export Zucker fuente completa | **Sí** en _render_plan aislado (2s). Stage E2E de rama **falla antes de exportar**. |
| B paquete reducido e integración externa | **Sí** para un solo clip plano, con reencode lossless y plan relativo; no un paquete mínimo ni 360/audio independiente. |
| C comparación A/B exacta con original fuente inaccesible | **FALLA** por 3 de 60 frames en último pase, aunque B se generó sin original. |
| D tiempo/bytes/rentabilidad | **Medidos** bytes y tiempos de 1 ejecución aislada; **no** tiempo de empaquetado, transferencia, coste remoto, red, 80GB ni viable final. |

## Requisitos que faltan para declarar los cuatro hitos completados
1. Diagnosticar y recuperar Stage real a partir del paso UI atascado, ejecutando el plan real y preservando hashes + plan. La ruta de test previamente superada en `main` es buena referencia, pero un pase histórico no sustituye el A actual.
2. Acreditar igualdad A/B de 60/60 (y audio/sincronización) para plan completo; diagnosticar PTS/últimos tres frames **sin alterar motor sin autorización expresa del mantenedor**.
3. Contemplar original 360 movimiento final, master audio íntegro y cajas aisladas; no extrapolar desde plano único.
4. Recoger tiempos reales de preparación, transferencia y render remoto si se quiere D económico.

## Gobernanza
Todas las variantes se han ejecutado en GitHub Actions QA sobre rama `fernando/continuacion-montara`; sin cambios en `main`, ni en los submódulos ni gasto de RunPod. Cierre de **ronda de experimentos**, no aprobación final de SATURNO. La elección de rumbo queda sin resolver hasta que el usuario decida qué requisitos adicionales probar.
