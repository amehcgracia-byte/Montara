# JÚPITER · W3O — recuperación de proxies parciales

Fecha: 2026-11-05. Entorno: rama experimental `fernando/companion-windows-w1`, [PR #74](https://github.com/amehcgracia-byte/Montara/pull/74) en borrador. Sin producción, sin releases, sin PC de FER.

## Comportamiento encontrado

- `companion.make_proxy` construye primero un archivo temporal con nombre `<source-id>.part.mp4` (o extensión de audio, según formato). Tras FFmpeg exit0 se publica por `pending.replace(target)`; un archivo parcial no debería entregarse desde `GET /proxies/<id>/file` porque se exige estado `ready` y presencia del destino final.
- Los trabajos están en memoria. Reiniciar Companion no restaura la cola, lo que es aceptable para el proxy reconstruible de un vídeo original conservado; sí pueden quedar archivos `.part` tras apagado forzoso.
- El POST `/proxies` crea trabajo nuevo para clave ausente o fallida. El nombre del parcial se deriva de una clave validada por la API, no de una ruta proporcionada por el cliente.

## Cambios realizados

- `companion/companion.py` commit `3f32210`: antes de comenzar la conversión, eliminar **solamente el .part del mismo trabajo** si existe, para evitar mezclar restos. En fallo ordinario eliminar ese parcial con manejo de error de limpieza sin enmascarar la causa principal. No borrar originales, caché final ni parciales de otras claves. Si el proceso muere violentamente no corre cleanup en ese momento; **se recupera al reintentar**.
- `tests/windows_companion_packaged_smoke.py` commit `321be9e`: tras localizar vídeo sintético escribe un archivo .part deliberadamente corrupto en la caché de laboratorio, ordena generar proxy real desde EXE empaquetado, verifica salida HTTP, ausencia del parcial antiguo y equivalencia byte a byte entre descarga y proxy final. Señal de aprobación `W3O_STALE_PARTIAL_RECOVERED_PASS`.
- CI automático [Windows 41934150697](https://github.com/amehcgracia-byte/Montara/actions/runs/41934150697). **En curso al redactar el informe**; no declarar PASS antes de ver resultados.

## Alcance y precauciones

Este experimento simula de forma controlada el residuo de un proceso interrumpido; **no** prueba recuperación de un corte de energía real ni transacciones de edición complejas. No limpiar a ciegas todo `*.part` al arrancar: otras instancias/trabajos podrían necesitarlos. La caché se recupera por clave al recibir de nuevo la solicitud de proxy.

Para W3P: comprobar entrega de paquete Windows/UI final, licencia FFmpeg y control de instancias simultáneas. Mantener la PR en draft hasta revisión y acuerdo de merge.
