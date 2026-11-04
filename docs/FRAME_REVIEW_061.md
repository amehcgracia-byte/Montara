# Montara 0.61 — revisión de frames y recuperación

## Causa comprobada en código

`review_items()` calculaba cada URL de preview llamando `resolved_profile()`: recorría el plan completo y entraba en el bloqueo de color por tarjeta y petición. La interfaz disparaba nuevas peticiones cada 1,5 s sin esperar. Los logs aportados por Chema muestran varias peticiones de revisión solapadas de 283–289 s; no constituyen un benchmark controlado.

Ahora la identidad de preview no mide vídeo. La medición de luz se comparte para un plan y revisiones de fuentes sin cambios; cambiar el plan, iluminación o archivo invalida la reutilización. Edit guarda las imágenes por fuente, tiempo y corrección para no decodificar otra vez al reabrir.

La preparación termina grupos de tres fotos y previews antes del siguiente grupo. La página espera al primer grupo y añade los siguientes sin reconstruir las tarjetas anteriores. Una sola consulta de estado en vuelo. Las previews son pequeñas y mudas, hasta tres segundos; el render final conserva su resolución y duración.

## Recuperación e inactividad

Eliminado el modal de 30 minutos y su recarga. La actividad real del ratón/teclado y las tareas en marcha mantienen el laboratorio despierto; una pestaña abandonada no. El watchdog existente sigue apagando la VM sin trabajo. Los renders del wizard y workers de sesiones actualizan el latido aunque el navegador no esté abierto.

La sesión se recupera mediante cronología del servidor, no un identificador antiguo de localStorage. La pestaña recuerda la edición/proyecto al refrescar y vuelve a su estado guardado sin relanzar el procesamiento. No convierte los resultados del companion en archivos del servidor: estos deben seguir disponibles donde se guardaron.

## Retención del laboratorio

`MONTARA_RETENTION_USED_GB=60` se activa en el servicio instalado por `deploy/vm/user_install.sh`. Fuera de ese servicio está desactivada por defecto. Se comprueba al arrancar y cada minuto; el umbral es ocupación del volumen (GB decimales), pero únicamente se eliminan carpetas gestionadas por este usuario en Sessions/Projects y sus uploads exclusivos.

Se conserva el proyecto abierto, el proyecto más reciente, la sesión más reciente, trabajos activos, carpetas `.keep` y trabajo modificado en la última hora. Los ejemplos del repositorio, la carpeta compartida y los datos de FER no son destinos de limpieza. Metadatos ilegibles o un worker ocupado cancelan la limpieza. Auditoría en `retention.jsonl`. Si los elementos protegidos impiden bajar de 60 GB, se conservan: el umbral no garantiza espacio si solo queda trabajo protegido. La caché global no se borra a ciegas porque contiene proxies referenciados.

## Validación

En curso. No instalada hasta comprobar el recorrido Linux y revisar capturas. Motor: `9d4abf75126e64e84f89d8310fb146709c0a73e7`, descendiente de `affe97a4`; mixer conservado `f15ff91`.
