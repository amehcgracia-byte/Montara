# Montara 0.60 — cancelación, progreso y descargas

## Cambios

- Cancel invalida las continuaciones de preparación/render/composición pendientes, para la consulta de progreso inmediatamente y espera a que el servidor confirme que el trabajo se ha detenido antes de volver a la pantalla anterior. Si no se puede confirmar, ofrece reintentar en lugar de presentar una cancelación ficticia.
- El render local contempla Cancel antes de tener identificador de trabajo: espera la respuesta de arranque y cancela ese identificador. No inicia más pasos tras cancelar una preparación local.
- Companion 0.6.1: cancela una mezcla local y sus procesos descendientes; una mezcla cancelada en cola o antes de registrarse no llega a arrancar. La página no sube el resultado ni reintenta en el servidor después de cancelar.
- El render Stage desde originales conserva las tareas medidas por plano y vuelve a alimentar los cuadrados de progreso de la interfaz. La ruta nueva de 0.59 solo publicaba porcentaje/mensaje: esta omisión era nuestra, no una incorporación visual de Fernando.
- Descarga y guardado usan el nombre del proyecto + extensión, sin hash ni sufijo de marca. Se conservan puntos internos (`Montara.Notetaker.mp4`). En el companion se conserva la protección contra sobrescritura del archivo local; la cabecera de descarga mantiene el nombre del proyecto.
- Editor `affe97a4f2ab2bdf435c3b8d52a85713e94b87ac` evita intentar VideoToolbox fuera de macOS, manteniendo fallback real en Mac y propagación de cancelación. Cambio separado de la PR experimental #51, que permanece sin integrar. Mixer sin cambios.

## Evidencia y límites

- Editor: 11 pruebas dirigidas de selección Linux/Mac, fallback, watchdog y cancelación pasan. El fallo más amplio de la fixture spherical-proxy se reproduce también en el commit base `92a8a6f6`; no se presenta como regresión nueva ni como CI totalmente verde.
- Montara: pruebas Chromium retienen las respuestas de arranque hasta después de Cancel, verifican el identificador local tardío y el nombre de descarga; pruebas HTTP con procesos reales comprueban cancelación activa/en cola, descendientes y aislamiento de otro proceso.
- Pruebas de mezcla local, exportación original, cabeceras/rangos y reproducción completa: 16 aprobadas en el Mac antes de añadir las dos últimas regresiones de cancelación (estas se verifican además por separado).
- Aceptación Linux completa: cinco trabajos aprobados en [41620201927](https://github.com/amehcgracia-byte/Montara/actions/runs/41620201927) para el código de #70; capturas revisadas. Incluye Stage, Push, mix, sesión servidor/local, navegación, cancelación, nombres de descarga, render original 1080p y contenedor privado con persistencia tras reinicio. La reproducción nativa se comprueba con Chrome oficial y un seek real: Playwright documenta diferencias de codecs entre su Chromium y los canales oficiales (https://playwright.dev/python/docs/browsers#media-codecs). No se atribuye una mejora global de render al cambio de encoder: EX14G02 de Fernando midió solo ~70,6 ms por intento fallido en una fixture pequeña.
- No se han incorporado los experimentos EX06/07/13, zooms automáticos nuevos, modelos de IA ni cambios al entorno de Fernando.

## Instalación comprobada (03-11)

- PR Montara #70 y Editor #52 integradas. JM instalado en `5a65f509a7b7c2ac628fd8fcb455df119d38f3c2`; engine `affe97a4f2ab2bdf435c3b8d52a85713e94b87ac`, mixer `f15ff91c1b80fc5f157099dcd9451d958d553ae6`.
- Companion 0.6.1 verificado en el Mac con ese engine y mixer; copia previa del código en `~/.montara-companion/code-backups/060-*`. Instalación obtenida del commit inmutable, no de una referencia de caché flotante.
- Servicio y scripts verificados por HTTP autenticado; túnel existente conservado y página abierta en `http://127.0.0.1:8101/`. Es el túnel del Mac, no un despliegue público.
- Antes del reinicio: árbol JM limpio, sin FFmpeg ni mezclas/renders locales en marcha, sin locks de sesión y wizard `waiting_review`. Ninguna exportación cancelada para instalar; FER sin cambios.
- Editor global Fast: 22 fallos/1304 aprobadas en Linux. Los 22 nombres fallidos también aparecen en el commit base sin modificar `92a8a6f6`; en el Mac ese base tiene tres fallos adicionales de entorno (25 en total). Esta entrega no declara verde la suite global del Editor.
