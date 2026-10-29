# SATURNO-03D — Puerta de integración real con Zucker, sin cambiar motor
**2026-10-29. Estado: diseño de validación; NO PASADO E2E.**

## Hallazgos confirmados en motor fijado
Repositorio `amehcgracia-byte/zucker_videos` commit `60a7b7e9a39077b36f45057811abd6a833a168ef`, `core/stages/export.py`:
- `_copy_trim_video` ~1493 ya advierte explícitamente del GOP previo y de que `-ss` antes de `-i` con `-t` puede terminar antes de lo deseado. **No reutilizar como prueba de equivalencia exacta automáticamente**.
- `_segment_source_info` ~4132 resuelve archivos de origen **desde registros del proyecto**, no solo desde la receta `clip_path`. Cambiar a un nombre de fragmento es más que modificar una ruta JSON; puede cambiar identidad, caché y origen de pixeles.
- `_spherical_uses_original_motion` ~2140: en movimientos 360 nativos, el render final lee **el original**, mientras que el draft puede leer proxy. Preparar solamente proxies no valida un render final equivalente.
- `_spherical_export_source_info` ~2157 necesita que `source_path.is_file()` y prepara caché esférica en ciertos escenarios. La fragmentación puede afectar offset temporal, firmas, duración y movimiento.
- `ExportStage.run` ~396 carga plan, aplica landmarks y normalización; `_render_plan` ~730 prepara fuentes y segmentación adicional. **Un inventario de JSON sin pasar por esa lógica no es prueba de inputs efectivos**.

## Ensayo de aceptación que falta
**No ejecutar sobre main ni medios de usuario.** José Manuel conserva autoridad sobre engine. Preparar dos copias QA del mismo fixture autorizado e inmóvil:
1. Baseline A: proyecto íntegro aislado, caché vacía, export completo `ExportStage.run`; guardar manifest, output SHA, ffprobe (video/audio pts/dts), hashes decodificados y recursos.
2. Input selector B: productor genera subconjunto de medios, sidecar con offsets y SHA; evitar copiar cachés previamente renderizadas. Conservar mismos parámetros de color, motion, audio, overlays y versión.
3. Confinamiento B: entorno/container con originales completos **no montados**; test negativo de apertura sobre cada ruta origen y sobre cachés globales; usar configuración aprobada por mantenedor.
4. Adapter QA: proporcionar mapping explícito de `source_path` → paquete/offset y resolver en modo de laboratorio, **fuera del motor fijado**. Si no existe forma de adaptar sin alterar motor, reportar **BLOCKED / requiere aprobación**; jamás forzar edición de submódulos.
5. Export real B: ejecutar mismo plan respetando timestamps de fuente, stream/gop, audio y motions; fallar si usa caches o rutas A.
6. Comparar resultado: (i) conteo de frames, valores PTS y hashes de píxeles decodificados, (ii) audio muestras/timing, (iii) duración/marcas de tiempo, (iv) MP4 SHA solo cuando reproducibilidad binaria sea objetivo explícito, (v) bytes de paquete + overhead/tiempos/CPU/RAM.
7. Ejecutar variedad: H264/HEVC, GOP abierto, B, VFR real, 360 native motion y audio; empezar con el fixture `tests/fixtures/much-to-me`.

## Criterio de no aprobación
Hasta que el export real B pase, `SATURNO-03` debe seguir rotulado **reconstrucción independiente de FFmpeg validada; portabilidad de Zucker NO DEMOSTRADA**.

## Evidencia archivada
`docs/SATURNO_02_03_CONSOLIDACION_AUDITORIA_2026-10-29.md` y ZIP SHA256 `7de2e1b27117aab61f9304b528e354209c1bb8b6ab4bbe95f1f20ca9d8eab5e7` adjunto en conversación (no en GitHub).
