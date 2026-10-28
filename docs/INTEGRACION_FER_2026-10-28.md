# Integración selectiva de la rama de Fer — 28 de octubre de 2026

Origen revisado: `fernando/continuacion-montara`, commit `65adc5b`.
Base: `main`, commit `df44ebe`. Integración autorizada por el propietario.

## Incorporado

- `local_media/proxies.py`: reutilización de caché antes de ejecutar ffprobe, validación de manifiesto y firma muestreada (cabecera/cola, no checksum completo), temporales únicos y generación única por fuente mediante bloqueo POSIX y segunda comprobación de caché.
- Adaptación durante la revisión: conservar generación fría sin bloqueo POSIX en otras plataformas. No se certifica Windows; sólo se prueba la selección alternativa. En esas plataformas pueden duplicarse transcodificaciones concurrentes, con temporales independientes.
- `local_media/session_proxies.py`: herramienta local opcional para preparar metadatos públicos de varias fuentes, sin exponer rutas originales. No es una integración de navegador ni API pública.
- Ocho herramientas CPU de medición B01/B02/B03/B05/B06/B07/B08/B10 y sus regresiones. Trabajan con muestras sintéticas o carpetas indicadas explícitamente; no se ejecutan automáticamente en el producto.

No se cambian `app.py`, la interfaz, los endpoints de subida/exportación, los submódulos ni el despliegue. Estas mejoras fortalecen el prototipo local existente; no anuncian un editor local terminado ni aceleración del render público.

## Validación nueva en macOS

- Suite Python completa: 140 pruebas aprobadas tras la adaptación de compatibilidad.
- B03, muestra sintética 12 s 1280×720: preparación fría 1,1463 s; reutilización 0,0009 s; original 10.595.784 bytes, proxy 771.688 bytes. Una ejecución: la reutilización no decodifica vídeo ni representa mejora de render de esa magnitud.
- B06, vídeo CFR y audio sintéticos de 4 s: offsets iniciales/finales y deriva entre extremos 0 ms. No prueba sincronización de conciertos reales.
- B07, dos cortes de un segundo: resolución de receta hacia el original y exportación de 2,000 s, error de duración 0 frames en esta muestra. No es E2E del editor.
- Las regresiones comprueban caché obsoleta/dañada, firma, concurrencia, CFR/VFR y mapeo explícito de inicio PTS desplazado 3 s.
- La firma muestreada puede omitir corrupción en el centro. Manifiestos antiguos sin firma conservan compatibilidad y no reciben garantía de integridad adicional.

Los resultados de CI Linux y comprobaciones JavaScript se enlazan en el PR de integración. No se presentan pruebas históricas de Fer como ejecuciones nuevas.

## Pendientes antes de habilitar nuevos flujos

### Se pueden resolver sin contratar servidor

1. Integrar carpetas locales y recetas con el esquema actual del editor; conservar identificadores, cámara, audio y transformaciones de tiempo. Jupiter es un laboratorio independiente, no otro editor de producción.
2. Completar selección automática de proxies en la línea de tiempo, seeking y exportación desde originales; validar recorrido real de navegador con dos cámaras y máster. Los endpoints y botón experimentales de Fer no se incorporan aún.
3. Adaptar `mixer_adapter/source_access.py`: el control propuesto acepta `Uploads/<id>/upload.json`, pero el flujo actual de subidas pequeñas usa `WizardUploads` sin ese manifiesto. Aplicarlo literalmente rompería pistas legítimas. Registrar y resolver ambos tipos de fuente y probar el endpoint antes de activarlo; también manejar manifiestos no objeto y rutas inválidas con error controlado.
4. Completar permisos por usuario/proyecto, propiedad de jobs y persistencia del mixer antes de multiusuario; la validación de ruta sola no proporciona aislamiento entre cuentas.
5. Probar Windows real, fuentes largas/360, offsets y deriva, uso de RAM/disco y exactitud de cortes. El bloqueo single-flight sólo está disponible en POSIX.

### Requieren infraestructura objetivo para medir y decidir

6. Comparar local frente a nube: subida + cola + proceso + descarga; tamaños reales 20–30 GB, retención/borrado, cuotas por cuenta, tráfico y coste por proyecto.
7. Medir concurrencia, RAM de árbol/cgroup, CPU y disco temporal en servidor Linux objetivo, antes de prometer capacidad o elegir GPU.
8. Diseñar transferencia explícita del material necesario para render remoto (original o segmentos), recuperación y limpieza; no asumir que seleccionar carpeta en navegador concede acceso a FFmpeg remoto.

La hipótesis híbrida de Fer conserva originales locales por defecto y transfiere medios sólo cuando lo requiere el ejecutor. No se adopta subida obligatoria de todos los originales ni almacenamiento permanente por cliente.

## Trazabilidad

Se trasladan los archivos seleccionados desde el commit de Fer y se documenta la adaptación POSIX, conservando atribución en el commit de integración. El resto de los 67 commits no se fusiona en bloque. La rama de Fer no tenía PR asociado al iniciar esta revisión; el informe se publica en el PR de integración y se enlaza desde PR #6 para evitar atribuir a ese PR documental los cambios funcionales.
