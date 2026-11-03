# Montara 0.60 — cancelación, progreso y descargas

## Cambios

- Cancel invalida las continuaciones de preparación/render/composición pendientes, para la consulta de progreso inmediatamente y espera a que el servidor confirme que el trabajo se ha detenido antes de volver a la pantalla anterior. Si no se puede confirmar, ofrece reintentar en lugar de presentar una cancelación ficticia.
- El render local contempla Cancel antes de tener identificador de trabajo: espera la respuesta de arranque y cancela ese identificador. No inicia más pasos tras cancelar una preparación local.
- Companion 0.6.1: cancela una mezcla local y sus procesos descendientes; una mezcla cancelada en cola o antes de registrarse no llega a arrancar. La página no sube el resultado ni reintenta en el servidor después de cancelar.
- El render Stage desde originales conserva las tareas medidas por plano y vuelve a alimentar los cuadrados de progreso de la interfaz. La ruta nueva de 0.59 solo publicaba porcentaje/mensaje: esta omisión era nuestra, no una incorporación visual de Fernando.
- Descarga y guardado usan el nombre del proyecto + extensión, sin hash ni sufijo de marca. Se conservan puntos internos (`Montara.Notetaker.mp4`). En el companion se conserva la protección contra sobrescritura del archivo local; la cabecera de descarga mantiene el nombre del proyecto.
- Editor `724d62decb442a6558fb7a88cae0f1be0e74c6f5` evita intentar VideoToolbox fuera de macOS, manteniendo fallback real en Mac y propagación de cancelación. Cambio separado de la PR experimental #51, que permanece sin integrar. Mixer sin cambios.

## Evidencia y límites

- Editor: 7 pruebas dirigidas de selección Linux/Mac, fallback y cancelación pasan. El fallo más amplio de la fixture spherical-proxy se reproduce también en el commit base `92a8a6f6`; no se presenta como regresión nueva ni como CI totalmente verde.
- Montara: pruebas Chromium retienen las respuestas de arranque hasta después de Cancel, verifican el identificador local tardío y el nombre de descarga; pruebas HTTP con procesos reales comprueban cancelación activa/en cola, descendientes y aislamiento de otro proceso.
- Pruebas de mezcla local, exportación original, cabeceras/rangos y reproducción completa: 16 aprobadas en el Mac antes de añadir las dos últimas regresiones de cancelación (estas se verifican además por separado).
- La aceptación Linux completa y las capturas se comprueban en la PR antes de instalar. No se atribuye una mejora global de render al cambio de encoder: EX14G02 de Fernando midió solo ~70,6 ms por intento fallido en una fixture pequeña.
- No se han incorporado los experimentos EX06/07/13, zooms automáticos nuevos, modelos de IA ni cambios al entorno de Fernando.
