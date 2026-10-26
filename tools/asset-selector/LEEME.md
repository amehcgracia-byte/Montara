# Mesa de selección

Abrir: http://127.0.0.1:8097/ (solo en este ordenador).
Si está cerrado, abre `Abrir-selector.command`.

- Buscar: candidatos de YouTube; los resultados no están aprobados automáticamente.
- Revisar: reproducir el vídeo, marcar desde/hasta, elegir nombre y carpeta.
- Sí: guarda la elección y descarga el fragmento en segundo plano.
- Varios recortes: cambia nombre y tiempos y vuelve a guardar sin cerrar el vídeo.
- No: lo pasa a Descartados; Recuperar revierte la decisión.
- Aprobados: muestra el estado de descarga y permite reintentar o sacar otro recorte.

Datos persistentes: `data/selection.json`.
Fragmentos: `data/biblioteca/<tipo>/<subtipo>/<nombre>-<id>.mp4`.
Cada fragmento lleva un JSON con origen, segundos y nombre. Las fuentes descargadas se reutilizan en `data/fuentes`.

No modifica ni publica la biblioteca de Montara. Las selecciones se incorporarán allí cuando decidamos cuáles conservar. La reproducción integrada depende de que el autor permita incrustar su vídeo. Las descargas pueden fallar por restricciones de YouTube; se conserva la elección y se ofrece reintento, sin eludir verificaciones.

Prueba realizada: `../montara/.venv/bin/python check_selector.py`, dos recortes reales en almacenamiento temporal, duración comprobada y carpetas separadas. Búsqueda de six seven verificada con 12 candidatos nuevos. Total inicial: 130 candidatos sin aprobar.

## Selección rápida (segunda versión)

Cada tarjeta tiene Sí / No / Revisar. Al pasar el ratón (o enfocar la imagen con el teclado), se reproduce sin sonido. Solo una vista previa a la vez. YouTube puede impedir incrustar un vídeo concreto; Revisar conserva el enlace directo.

Dos pasadas separadas: Green screens y overlays / Vídeos con fondo. Las búsquedas incluyen o excluyen green screen según la pasada. La clasificación inicial por título es provisional: en Aprobados puedes mover un vídeo a la otra biblioteca. Las carpetas físicas están separadas en `data/biblioteca/green-screens` y `data/biblioteca/videos-con-fondo`.

Sí guarda el vídeo completo hasta 120 segundos. Para vídeos más largos abre el recorte. Guardar dos veces el mismo fragmento no crea una copia nueva. Las selecciones anteriores se han conservado; respaldo previo a la migración en `data/selection-before-v2.json`.

Dibujos animados se agrupa por serie. Los candidatos se alternan por carpeta para evitar que una sola búsqueda ocupe toda la mesa. No se ha encontrado candidato verde pertinente de Thundercats en esta pasada; sí hay candidatos con fondo. Las series poco representadas pueden ampliarse con enlaces propios.
