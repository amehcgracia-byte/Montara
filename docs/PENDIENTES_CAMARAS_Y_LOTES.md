# Vídeos de una jam y varias cámaras — revisión 2026-11-02

Pendientes de producto; **no implementados por el PR #66**, que limpia metadatos de MP3.

## Varias canciones ya mezcladas + todos los vídeos de la noche

Petición: seis audios de seis canciones distintas y todos los vídeos de la jam deben producir seis vídeos revisables. Hoy los audios juntos se tratan como pistas de una mezcla; la sesión completa detecta canciones y exporta audio, sin completar automáticamente el lote de vídeos. Para la prueba actual: una canción y sus vídeos por proyecto.

Implementar una entrada explícita de canciones terminadas, asociación de cada audio con las tomas que coinciden por sincronización, revisión por canción y cola de exportación con resultados separados. No confundir canciones independientes con stems simultáneos. Probar tomas compartidas, cobertura parcial, silencios y canciones sin vídeo coincidente; no asignarlas a ciegas. Reutilizar sincronización y editor, sin asumir que ya existe un flujo de lote.

## Dos cámaras en movimiento, incluso dos Sony iguales

- La interfaz permite asignar `Moving camera` por archivo (`web/montara.js`) y editar el recorte y zoom por plano (`web/flat-camera.js`, `web/cut-editor.js`).
- Hallazgo reproducido en el motor fijado `ff9baf4`: `core/stages/edit.py::_camera_id` devuelve `sony` para dos fuentes con `camera_model='Sony A7'` si no traen `camera_id` explícito, aunque sus rutas difieran. Con identificadores explícitos devuelve dos cámaras. La familia de fabricante no es una identidad física suficiente.
- Corrección pendiente: identidad explícita por cámara, agrupando los clips de cada dispositivo sin mezclar dos aparatos iguales. Debe respetar las asignaciones al crear proxies, sincronizar y editar. El cambio del motor va en Zucker Editor, después se mueve el submódulo conforme a CLAUDE.md.
- `core/shot_quality.py` evalúa movimiento/nitidez/exposición con heurísticas ligeras; `face_like_score` es una aproximación por color, no comprensión fiable del encuadre. El zoom automático genérico de cámaras móviles no queda resuelto por esto.
- Política deseada: medir sujeto y resolución útil por tramo, conservar primeros planos, recortar suavemente planos abiertos solo con detección fiable y seguimiento estable; no inventar zooms ante incertidumbre. Visión por ordenador puede cubrir esa medición sin exigir un LLM; calidad y tiempos aún por probar.
- Aceptación pendiente: dos cámaras iguales con clips consecutivos, una abierta y otra cerrada, sujetos en movimiento, toma ya ampliada, ausencia de sujeto y correcciones manuales preservadas. No se han hecho renders reales de dos Sony en esta revisión.
