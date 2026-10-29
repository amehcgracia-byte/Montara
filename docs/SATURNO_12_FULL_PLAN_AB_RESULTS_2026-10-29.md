# SATURNO-12 — recuperación y auditoría del A/A y A/B completo

Fecha: 2026-10-29. Recuperación de evidencia existente; **ningún render nuevo**.

## Procedencia y estado

- Rama: `fernando/continuacion-montara`.
- Antes de esta recuperación, HEAD seguía en `81fb50b955afc51dcd0b78c36fe3ab254a363916`; no había commits posteriores en esta rama.
- [Workflow 40887892958](https://github.com/amehcgracia-byte/Montara/actions/runs/40887892958), intento 1, estado consultado: completed/failure; actualizado el 29 de octubre a las 14:37:17 UTC (15:37:17 Madrid).
- [Job 123496424010 y sus logs](https://github.com/amehcgracia-byte/Montara/actions/runs/40887892958/job/123496424010).
- Programa ejecutado: [full_gate.py en el commit probado](https://github.com/amehcgracia-byte/Montara/blob/81fb50b955afc51dcd0b78c36fe3ab254a363916/experiments/saturno_10/full_gate.py).
- Los cuatro JSON se recuperaron de los bloques `SATURNO_FULL12_{A,A_repeat,B,REPORT}_BEGIN/END` del log descargado. Se conserva su contenido, sin sustituir resultados por resúmenes.
- Evidencia recuperada: [A](../experiments/saturno_12/A.json), [A_repeat](../experiments/saturno_12/A_repeat.json), [B](../experiments/saturno_12/B.json), [REPORT original](../experiments/saturno_12/REPORT.json).
- Engine sigue fijado en `60a7b7e9a39077b36f45057811abd6a833a168ef`; mixer en `c7a46a6d8388c6e0703ef54983f2d627ea189f32`. Esta recuperación añade documentación y evidencia; no modifica producto, motores, referencias de submódulos ni workflows.

## Pregunta y diseño comprobado

¿Reproduce el paquete conservador el mismo montaje Stage que los originales, después de comprobar repetibilidad A/A?

Se reutilizaron `experiments/saturno_10/stage_edit_plan.json` y `stage_project.json`: plan real previamente obtenido, con 19 segmentos, tres cámaras y siete segmentos 360. Este experimento llama al renderizador real con el plan guardado; **no vuelve a ejecutar ingestión, sincronización, interfaz o decisiones creativas**.

El código lanza A, A_repeat y B en procesos distintos. Crea carpetas y `ZUCKER_DATA_ROOT` separados, exige caché inicialmente vacía y activa `force_rerender_segments=True`. Los JSON confirman caché vacía y siete llamadas nativas 360 exitosas por ejecución; los hashes del proyecto y plan coinciden entre A y A_repeat.

B se ejecuta mediante `sudo unshare --mount --propagation private`. Se montan tmpfs vacíos sobre toda la carpeta de fixtures y las carpetas A/A_repeat, ocultando sus resultados, runtimes y cachés. Los cuatro originales (tres cámaras y master) constan ausentes. Esto acredita el aislamiento implementado, sin equivaler a una certificación de un importador de producción completo. El software instalado y sus recursos gráficos siguen compartidos.

Control experimental: se añade en memoria `-threads:v 1` a libx264 en las rutas ordinaria y 360. **El A/A estable corresponde a este control QA**, no demuestra determinismo universal de la configuración por defecto.

Runtime según workflow y paquetes instalados en el log: Ubuntu 24.04, Python 3.11 solicitado, FFmpeg `7:6.1.1-3ubuntu5`, libx264 `2:0.164.3108+git31e19f9-1`.

## Resultados

| Criterio | A/A_repeat | A/B |
| --- | --- | --- |
| Fotogramas finales | 3007 / 3007 | 3007 / 3007 |
| Fotogramas idénticos en el mismo índice | **3007 / 3007** | **782 / 3007** |
| Audio PCM completo idéntico | Sí | Sí |
| JSON completo de paquetes/streams idéntico | Sí | No |
| Archivo MP4 completo idéntico | Sí | No |
| Gate original | Control aprobado | **FAIL_FULL_PLAN_AB** |

| Salida | Segundos de exportación | Bytes | SHA-256 MP4 registrado |
| --- | ---: | ---: | --- |
| A | 558.183901 | 203924811 | `6cd59941714fd3bb74ef7f5c95ead50612f5c1a9fbe3b48342417186e4cd5bb6` |
| A_repeat | 557.102038 | 203924811 | `6cd59941714fd3bb74ef7f5c95ead50612f5c1a9fbe3b48342417186e4cd5bb6` |
| B | 555.704695 | 204977186 | `e0f6a4eec27ce0b21675f4565ad7ac4ed2123ba37a5f8a85d5d4c50708b4ad8b` |

Las diferencias finales afectan a 2225 fotogramas: índices base cero 735–2700 y 2748–3006. La primera diferencia está a 24,5 s. Estas cifras miden igualdad exacta, no severidad perceptual.

La auditoría offline descomprime las cronologías guardadas y verifica su SHA-256: los 3007 pares PTS/duración de vídeo, ordenados por presentación, son iguales. La lista completa en orden de paquetes de vídeo difiere. Los 4318 paquetes de audio coinciden íntegramente. Ambos vídeos duran 100,233333 s a 1920×1080; ambos audios 100,232993 s. **No interpretar el timeline_exact=false como prueba de desincronización audiovisual.**

## Localización con hashes intermedios existentes

Se comparan únicamente llamadas exitosas; el registro también contiene intentos fallidos de h264_videotoolbox, no disponible en este Linux. Hay 19 intentos fallidos por ejecución, seguidos de las rutas de codificación exitosas. Las listas warnings están vacías, pero eso no significa que todos los intentos de codificador tuvieran éxito.

- Los doce segmentos ordinarios de cámaras planas tienen archivos MP4 idénticos A/B.
- El segmento 360 `segment-0001.mp4` también es idéntico.
- Difieren los otros seis MP4 360: `0003, 0006, 0008, 0012, 0016, 0019`.
- Los siete comandos nativos 360 exitosos coinciden argumento por argumento salvo el último argumento, la ruta de salida. Incluye los filtros de color capturados.
- [Tabla completa de hashes](../experiments/saturno_12/intermediate_comparison.json).

Esto localiza una divergencia en salidas 360 anteriores al ensamblado final. No identifica todavía la causa. Los comandos capturados reciben vídeo BGR por pipe; no registran los hashes de esos píxeles ni toda la selección temporal/pose anterior al pipe. La igualdad de argumentos de codificación no demuestra igualdad de entrada.

## Tamaños y límites de portabilidad

El paquete conserva **todos los GOP de vídeo**. Su ahorro procede de eliminar el audio de cámara, conservando completo el master. No demuestra ahorro por transportar únicamente ventanas de vídeo.

- Originales de medios: 6678870 bytes.
- Medios + plan/proyecto del paquete: 4722348 bytes.
- ZIP originales (solo medios): 6509709 bytes.
- ZIP paquete (incluye plan/proyecto): 4238474 bytes; reducción aproximada 34,89 %, con contenidos distintos declarados.
- Preparación del paquete: 0,673477 s; preparación de ambos ZIP: 0,329938 s.
- Hashes de cada componente, ZIP, master y dos recursos gráficos declarados: REPORT original.

Son mediciones de este fixture y runner. No hay transferencia remota real ni coste cloud de producción medidos; el hito D no está completo. La portabilidad exacta de imágenes de este montaje (C) falla. No procede declarar completados los cuatro hitos A–D ni decidir aún Saturno frente a Júpiter.

## Reproducción de la auditoría sin render

Desde la raíz del repositorio:

```sh
python experiments/saturno_12/audit_saved_evidence.py
```

Solo usa Python estándar, lee los JSON, reconstruye las comparaciones, verifica cronologías comprimidas y contrasta la tabla intermedia. No invoca FFmpeg, red ni GitHub Actions. Resultado obtenido durante esta recuperación: `PASS_SAVED_EVIDENCE_CONSISTENCY`.

Esta comprobación acredita coherencia y trazabilidad de los registros recuperados. No recalcula hashes a partir de los MP4: esos vídeos no se conservan aquí. Los hashes de medios son mediciones registradas por el runner, no una inspección visual independiente posterior.

## Próximo bloque propuesto, aún no ejecutado

Investigar un único segmento 360 divergente (0003), conservando el contexto del plano previo. Primero revisar selección de fuente, tiempos, pose y comandos reales del decodificador; después diseñar una prueba que compare imágenes antes y después de la reproyección, sin repetir tres exports completos. Las hipótesis de decodificación/cadencia, contexto de movimiento o referencias siguen abiertas.

Regla operativa para pruebas futuras: un bloque con pregunta y condición de cierre explícitas. Si necesita una ejecución larga, comunicar enlace y duración estimada y cerrar el turno sin sondeos continuos. Documentar el resultado antes de iniciar otro bloque. Esta recuperación termina con el informe y la evidencia guardados; no inicia ese experimento.
