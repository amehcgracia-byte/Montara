# SATURNO-17 — Resultado real de reproyección 360 A/A/B

Fecha: 2026-10-29. Rama: `fernando/continuacion-montara`.

Fuente primaria: [Workflow 40911644727](https://github.com/amehcgracia-byte/Montara/actions/runs/40911644727), job [123580888515](https://github.com/amehcgracia-byte/Montara/actions/runs/40911644727/job/123580888515), completado con conclusión operacional `success`.

Script: `experiments/saturno_17/reprojection_gate.py`. Engine intacto en `60a7b7e9a39077b36f45057811abd6a833a168ef`. FFmpeg 6.1.1-3ubuntu5.

## Pregunta

¿Se mantiene la igualdad de fotogramas A/B tras procesar el segmento 360 0003 con el reproyector real Zucker y el control QA de decodificación `-fps_mode passthrough`?

## Resultados del resumen SATURNO17_SUMMARY

- Estado: `REAL_REPROJECTION_AB_EXACT`.
- A: 278 cuadros, 20532363 bytes MP4, una intervención de decodificador.
- A_repeat: 278 cuadros, 20532363 bytes MP4, una intervención.
- B: 278 cuadros, 20532363 bytes MP4, una intervención.
- Hashes de cuadros de salida: A/A_repeat 278/278 idénticos; A/B 278/278 idénticos.

## Interpretación y límites

En este único segmento y configuración QA, un original y el paquete conservador produjeron 278 cuadros idénticos después de pasar por el reproyector real. El control `-fps_mode passthrough` se inyectó en memoria en el proceso de decodificación, sin editar el motor. El script reutilizó el comando exitoso de codificación del segmento 0003 registrado por SATURNO-12, con `-threads:v 1`.

No se realizó el montaje completo, prueba B aislada mediante montajes inaccesibles, validación de sincronización audiovisual ni transferencia cloud. El paquete aún conserva todos los GOP; no demuestra ahorro selectivo. No atribuir a este test la aprobación del gate C.

## Próximo gate

Integrar el control QA del decodificador en el harness completo de SATURNO-12, restringiendo el parche al worker y registrando intervenciones por etiqueta; validar los siete segmentos 360 y repetir A/A/B con originales y cachés ocultos en B, si se conserva el diseño de aislamiento. Comparar fotogramas finales, PCM, PTS y hashes de MP4. En caso de error operacional, documentarlo por separado del resultado científico.

## Uso de herramientas

Un acceso a metadatos de jobs y una lectura de logs (68911 caracteres recibidos; solo resumen filtrado expuesto). Tokens reales no disponibles. Sin RunPod, Oracle, navegador ni modificaciones de motor.
