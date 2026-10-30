# FOCUS A/C — Primer render de plan creado desde proxies (2026-10-30)

## Resultado observado
Operador ejecutó bajo `montara-bench FER-FOCUS-AC-EXPORT-01` el script `experiments/media_optimization/focus_ac_export_from_originals.py`, proyecto aislado `/home/fer/montara-focus-ac-true-edit-01`. El plan de seis segmentos fue generado antes por **EditStage real** trabajando con **dos proxies físicos 360p** de cámaras **sintéticas originales 1280x720**.

- Estado: `PASS_EXPORT_CREATED_PROVENANCE_REVIEW_PENDING`.
- ExportStage real terminó en **45.325 segundos**; preflight CPU 0 %.
- MP4 generado: `E2E stage-youtube-20261030-173913-618461453.mp4`, **50,838,395 bytes**.
- Segmentos: **6/6**, todos `rendered_from=original` y `cached=false` según manifest de ExportStage.
- Tiempos ffmpeg segmentos (s): 11.693, 11.527, 17.567, 9.052, 5.142, 7.092. Son tiempos de cada segmento, no sumables como tiempo total concurrente de fase.
- Se mantuvo Git limpio.

## Alcance y limitaciones
**Confirmada viabilidad del traspaso proxy-edit → original-export para este caso sintético de 20 s.** No prueba comportamiento sobre las cámaras iPhone 4K con rotación, Sony ni HEVC 360; no se ha medido calidad visual ni audio del MP4 en este ensayo. Falta inspeccionar export final (ffprobe, duración, streams) y muestras A/B para una certificación completa. No presentar 45.325 s frente a 195.097 s del E2E previo como speed-up causal: cargas, modos, cachés y entorno diferentes.

## Datos que solicita Chema, separados de este laboratorio
Chema solicita ejecutar **`montara-runs` en el Mac donde se hizo su ejecución**, adjuntar **`~/montara-runs.jsonl`**, y aportar tiempo aproximado de subida por vídeo y uso de Companion. El reporte del laboratorio de fer NO sustituye esos registros de máquina ni contiene métricas del navegador. El comparador informado por Chema, 4101 s en 4 vCPU, corresponde a otra ejecución y no debe equipararse directamente al ensayo FOCUS.
