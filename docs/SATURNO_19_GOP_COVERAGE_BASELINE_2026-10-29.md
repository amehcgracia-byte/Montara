# SATURNO-19 — cobertura GOP del fixture real y siguiente ensayo selectivo

Fecha 2026-10-29. Rama `fernando/continuacion-montara`; motor sin cambios.

## Pregunta

¿Permite el fixture actual seleccionar solo parte de los GOP manteniendo ventanas del plan Stage y las muestras de color?

## Evidencia

Fuente: `experiments/saturno_10/packet_results_40886014059.json`, `report.sources`, obtenida en SATURNO-11. Se ha leído su evidencia guardada, no ejecutado un FFmpeg nuevo.

| Cámara | GOP existentes | GOP elegidos | Bytes payload de vídeo | Bytes payload retenidos |
|---|---:|---:|---:|---:|
| cam-sony.mp4 | 10 | 10 | 1567163 | 1567163 |
| cam-fixed.mp4 | 10 | 10 | 570443 | 570443 |
| cam-360.mp4 | 10 | 10 | 431510 | 431510 |
| **Total** | **30** | **30** | **2569116** | **2569116** |

La selección guardada retiene todos los grupos `[0..9]` en cada una de las tres fuentes. La fracción de payload de vídeo conservado es 1, y los bytes de payload descartados son 0. El paquete SATURNO-18 sí reducía bytes al eliminar el audio de cámaras, pero no por selección de GOP.

El selector `choose_gops` preserva primer y último GOP y selecciona los que intersectan ventanas de uso y muestras de color, con un margen temporal de un frame. El plan multicámara corto hace que se seleccionen todos los GOP. No se debe extrapolar de este ensayo que no pueda existir ahorro en vídeos de mayor duración con largos tramos sin usar.

## Artefacto reproducible

`python experiments/saturno_19/audit_gop_coverage.py`

El script utiliza solamente la biblioteca estándar y el JSON versionado. Verifica continuidad de grupos, número de paquetes y bytes registrados y muestra el resumen. No cambia la receta ni requiere Actions, FFmpeg ni vídeos.

## Conclusión limitada y condición de paso

**NO_SELECTIVE_GOP_SAVINGS_IN_CURRENT_FIXTURE**. Está demostrado en la evidencia existente que este fixture concreto no puede mostrar ahorro de payload de vídeo usando el selector previo: el 100 % ya se selecciona.

Para probar el objetivo B selectivo necesitamos un nuevo caso controlado con **material fuente más largo que las ventanas utilizadas**, manteniendo codec, timestamps y GOP, y aplicando todas las dependencias reales (color, seek, audio, 360). No afirmar tamaño ni reducción hasta medirlo. Evitar fabricar artificialmente un éxito con bytes hipotéticos. Antes de un A/B completo, ejecutar preflight de payload/PTS/DTS, ventanas BGR y propiedades de color, verificando que el nuevo paquete descarta realmente grupos. Solo entonces probar el mismo plan bajo aislamiento A/B con control QA.

## Trabajo pendiente

SATURNO-18 supera equivalencia del paquete conservador para el plan y condiciones QA, no el ahorro selectivo. El hito D (transferencia/costes remotos medidos) tampoco está aprobado. No se ha modificado `main`, `engine`, `mixer` ni ejecutado nube de pago.
