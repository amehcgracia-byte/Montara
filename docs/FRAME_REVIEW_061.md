# Montara 0.61 — revisión de frames y recuperación

## Causa comprobada en código

`review_items()` calculaba cada URL de preview llamando `resolved_profile()`: recorría el plan completo y entraba en el bloqueo de color por tarjeta y petición. La interfaz disparaba nuevas peticiones cada 1,5 s sin esperar. Los logs aportados por Chema muestran varias peticiones de revisión solapadas de 283–289 s; no constituyen un benchmark controlado.

Ahora la identidad de preview no mide vídeo. La medición de luz se comparte para un plan y revisiones de fuentes sin cambios; cambiar el plan, iluminación o archivo invalida la reutilización. Edit guarda las imágenes por fuente, tiempo y corrección para no decodificar otra vez al reabrir.

La preparación termina grupos de tres fotos y previews antes del siguiente grupo. La página espera al primer grupo y añade los siguientes sin reconstruir las tarjetas anteriores. Una sola consulta de estado en vuelo. Las previews son pequeñas y mudas, hasta tres segundos; el render final conserva su resolución y duración.

## Recuperación e inactividad

Eliminado el modal de 30 minutos y su recarga. La actividad real del ratón/teclado y las tareas en marcha mantienen el laboratorio despierto; una pestaña abandonada no. El watchdog existente sigue apagando la VM sin trabajo. Los renders del wizard y workers de sesiones actualizan el latido aunque el navegador no esté abierto.

La sesión se recupera mediante cronología del servidor, no un identificador antiguo de localStorage. La pestaña recuerda la edición/proyecto al refrescar y vuelve a su estado guardado sin relanzar el procesamiento. Los vídeos nativos conservan el identificador del trabajo, las referencias a originales y la carpeta elegida. Los terminados se indexan también en Companion para recuperarlos tras reiniciarlo; no se sube el vídeo final al servidor. Los archivos deben seguir disponibles en su carpeta.

## Retención del laboratorio

`MONTARA_RETENTION_USED_GB=60` se activa en el servicio instalado por `deploy/vm/user_install.sh`. Fuera de ese servicio está desactivada por defecto. Se comprueba al arrancar y cada minuto; el umbral es ocupación del volumen (GB decimales), pero únicamente se eliminan carpetas gestionadas por este usuario en Sessions/Projects y sus uploads exclusivos.

Se conserva el proyecto abierto, el proyecto más reciente, la sesión más reciente, trabajos activos, carpetas `.keep` y trabajo modificado en la última hora. Los ejemplos del repositorio, la carpeta compartida y los datos de FER no son destinos de limpieza. Metadatos ilegibles o un worker ocupado cancelan la limpieza. Auditoría en `retention.jsonl`. Si los elementos protegidos impiden bajar de 60 GB, se conservan: el umbral no garantiza espacio si solo queda trabajo protegido. La caché global no se borra a ciegas porque contiene proxies referenciados.

## Push y edición por fuente

Selector de audio antes de editar, con Start/End aplicados a la petición de reel. La configuración de cámaras se oculta en Push; se conserva el control 360 cuando corresponde. Fotos y previews usan el lienzo vertical y la geometría del exportador, incluida la variante con imagen completa y las mezclas. El cuadro de encuadre muestra una miniatura vertical en vivo. Luz disponible también en Push; los clips no reciben igualado de color entre cámaras por defecto.

`Apply to whole source video` copia el encuadre y la luz a tomas del mismo archivo, identificado por su ruta resuelta, no por nombre ni cámara. Conserva los tiempos y las otras fuentes. Enter/Save sigue guardando una toma; aplicar a toda la fuente requiere su botón específico.

## Marca dentro de la duración

Los assets de Montara se regeneran desde el símbolo SVG existente, sin palabra. Apertura/cierre dentro del contenido seleccionado (1,4 s en cada extremo), con audio continuo y watermark de símbolo. No se añaden los anteriores 20,2 segundos. Una imagen personal opaca conserva todo su fondo; un logo con alfa real se superpone al vídeo. Blanco/negro no se tratan como transparencia. Se aplica en la ruta ExportStage Stage/Push y en el Companion Stage (0.6.2, incluido logo personal validado como PNG de hasta 1600×1600); las aperturas editoriales propias de Show siguen siendo otra herramienta, sin sustituirlas silenciosamente.

## Validación

En curso. No instalada hasta comprobar el recorrido Linux y revisar capturas. Motor: `3ff470eeac992e29e8cdd98ef41a631f72369d2b`, descendiente de `affe97a4`; mixer conservado `f15ff91`.
