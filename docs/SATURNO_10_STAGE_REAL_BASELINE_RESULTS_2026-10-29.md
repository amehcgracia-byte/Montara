# SATURNO-10 — Stage real completado con controles QA

Run [40882186838](https://github.com/amehcgracia-byte/Montara/actions/runs/40882186838),
job 123476329081, commit 9ff6ffb345e3b185dfcedb5bf04f423119c56df3.
Estado científico: **STAGE_COMPLETE_UNDER_QA_CONTROLS; gate_full_stage=true**.

## Medición real
- Journey existente tests/e2e_journey.py completado: passed=true.
- Tres fuentes usadas: Sony 7 planos, fija 5, 360 7; sin clips excluidos.
- 19 segmentos, 18 cortes. 80.033333 s de montaje + intro/outro -> 100.233333 s.
- Export 1920x1080, con audio; decodificación íntegra completada por el journey.
- Vídeo final 203627878 bytes, SHA256:
  c8159e7c785ee1dcd20f79122ae649b0153901131185c97cdb946ffba8b60837.
- Journey 608.2746 s (incluye interfaz/preparación y comprobaciones).
- Etapa export del proyecto: 478.445 s; manifest total_wall_sec=473.285 s.
  Son cronómetros de alcances diferentes, no promediarlos ni confundirlos.
- Las 19 entradas del manifest tienen cached=false y rendered_from=original.
- Hay 7 planos 360 con movimientos en el plan real: reveal, settle,
  planet_to_stage, push_in, pull_out, pan_left y pan_right.

## Controles QA explícitos
Se reutilizó el fallo original ya documentado, sin repetirlo.
El navegador sirvió montara.js con DOS correcciones singulares de selector:
`$('#cameraList .cam').forEach` y `$('[data-camera-type]').forEach` pasan a `$$`.
No se modificó el JS del producto. Se registra hash de original/corregido/servido.
Servidor con control encoder_threads=1 solo en llamadas _run_ffmpeg_progress.
La ruta nativa 360 usa otro lanzador: NO se presume controlada ni repetible por eso.
No hubo cambios en engine, mixer, main ni ramas ajenas.

## Evidencia persistida
- experiments/saturno_10/stage_edit_plan.json: plan EXACTO generado por Stage,
  incluida la sustitución de plano realizada por el journey; no inventado ni recortado.
- experiments/saturno_10/stage_project.json: proyecto/configuración original.
- experiments/saturno_10/stage_results_40882186838.json: reporte, artefactos JSON,
  manifest, link audit, comandos efectivos/de motor, logs y Git blob SHA1 de inputs.
  Los hashes de entrada son IDs Git del checkout fijado; no se presentan como una
  medición adicional SHA256 en runtime. El SHA256 de salida sí se calculó en runtime.

El MP4 de 203 MB y sus PNG no se retuvieron fuera del runner por la cuota conocida
de artefactos. Están su hash, metadatos y receta/plan; un A/B posterior debe generar
su referencia A de nuevo en el mismo ensayo con el MISMO plan, sin rehacer decisiones.
Esto no permite descargar ahora el vídeo desde el repositorio.

## Precaución de metadatos
camera_usage y los paths del plan muestran las tres fuentes físicas. Sin embargo,
camera_distribution/camera_id agrupan las cámaras como much-to-me por su carpeta.
No usar ese 100 % agregado para afirmar que solo se usó una cámara ni para certificar
cuotas físicas. Se conserva sin modificar para revisión del mantenedor; el alcance
es render/transferencia, no corregir unilateralmente la lógica de identificación.

## Gates tras este lote
| Gate | Estado |
|---|---|
| A referencia de proyecto real completo | Render ejecutado, plan/hash/tiempos guardados, con controles QA explícitos |
| B reducido plano con audio propio | Aprobado SAT-09; no extrapolar a tres cámaras |
| B/C completo multicámara y movimiento 360 | Pendiente de cierre de dependencias y A/A/A-B en export nativo |
| D economía remota | Pendiente; solo tiempos de runner/bytes actuales medidos |

Siguiente: auditar GOP/paquetes y ventanas reales del plan (incluidas muestras de color),
antes de gastar tres renders completos en un paquete insuficiente o de tamaño mayor.
No hay decisión de arquitectura ni autorización para cambiar motores de producción.
