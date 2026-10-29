# SATURNO-03D: preflight real de Zucker (2026-10-29)

**Estado: BLOQUEADO — export E2E de Zucker desde paquete parcial NO ejecutado ni demostrado.**

Se verificó el motor ZuckerVideos en commit `60a7b7e9a39077b36f45057811abd6a833a168ef`. `core/stages/export.py::_segment_source_info` resuelve fuentes en `project.inputs.videos` y `normalized`. `_spherical_uses_original_motion` puede utilizar el original para movimiento 360 final; `ExportStage.run` aplica landmarks y normalización; `_copy_trim_video` documenta dependencias GOP y límites de búsqueda.

**Resultado de esta sesión:** herramienta QA `saturno03d/readiness.py` (entregada como archivo de conversación, no versionada todavía) y **7/7 pruebas locales**; incluyen JSON sin segmentos, fuentes ausentes, validación temporal, lookup de proxy, 360 en movimiento y CLI fail-closed. Todo caso se etiqueta `BLOCKED` por la ausencia de un adaptador de rutas/tiempos aprobado. La herramienta **no ejecuta FFmpeg ni Zucker**, ni calcula un paquete mínimo.

**Impedimento de ejecución actual:** GitHub accesible mediante conector de lectura/escritura, pero no hay checkout completo, deps y submódulos ejecutables montados en el laboratorio; el acceso Git directo desde el contenedor no resuelve github.com. Es incorrecto afirmar E2E completado.

**Aceptación pendiente:**
1. Crear dos proyectos QA independientes con los mismos medios y motor fijado, cachés de segmento vacías.
2. Export normal A mediante `ExportStage.run` y registrar SHA, timestamps, frames decodificados, audio PCM y costes.
3. Generar paquete parcial B, más manifiesto de offsets/GOP/PTS y adaptador QA aprobado por mantenedor, **sin editar submódulos**.
4. Export B bajo aislamiento de originales completos/cachés A y probar acceso denegado.
5. Comparar A/B frame por frame, audio y sincronía; medir bytes y rendimiento end-to-end.
6. Repetir para HEVC, B-frames, VFR, 360 motion y audio real.

**No se ha usado RunPod, no se han cambiado main ni motores.**

Archivos de conversación: `saturno03d/readiness.py`, `saturno03d/test_readiness.py`, `saturno03d/REPORT.md` (pendientes de versionar individualmente).
