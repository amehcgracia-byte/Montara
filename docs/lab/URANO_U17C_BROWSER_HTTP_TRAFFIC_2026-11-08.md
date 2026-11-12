# URANO U17C · Huella de tráfico browser → servidor / Companion (08-11-2026)

**Estado:** instrumentación experimental sobre la PR #131. No desplegada; no implica pruebas WAN ni GCP.

## Pregunta que responde esta prueba

En arquitectura híbrida Montara hay que separar **el envío de previews/proxies a Montara (servidor)** de **la descarga del vídeo final desde Companion (CPU y disco del usuario)**. Una prueba con dos procesos en el mismo runner valida protocolo y volúmenes HTTP observables por navegador, pero **no proporciona aún el consumo real de red entre ordenadores diferentes**.

## Contador implementado

`tests/urano_browser_transfer.py` conecta un observador **pasivo** a eventos `requestfinished` / `requestfailed` de Playwright. Obtiene los campos `request.sizes()` de intercambio HTTP: tamaños de cuerpo y cabeceras de solicitud y respuesta. Agrupa por **origen explícito** (`server` vs `local_companion`), método y **familia de endpoint predefinida**. Solo cuenta tráfico originado por el navegador bajo pruebas.

**No** registra body, URL, query, rutas, archivos, correos, cabeceras, tokens, claves, nombres de usuarios ni los bytes del vídeo. No es un proxy HTTP ni requiere modificar Companion o servidor. Los originales permanecen en el directorio local generado para el E2E.

`tests/e2e_native_stage.py` reutiliza la prueba real de Stage→Companion→MP4 ya aprobada (#121/#130) y emite `browser-transfer.json` junto a `summary.json`; `tests/urano_hybrid_benchmark.py` lo integra en `hybrid-report.json` para dos recorridos simultáneos. Cada uno conserva sus puertos, carpetas y procesos aislados. La CI `.github/workflows/urano-u17c-browser-transfer.yml` exige que existan intercambios con ambas partes y que se haya transferido realmente el MP4 local. Tests negativos garantizan que la salida no contenga URLs ni identificadores secretos.

## Semántica de resultados

- `server_upload_browser_body_bytes_observed`: **suma de cuerpos de solicitudes del navegador a rutas de transferencia** del servidor. No todos los posibles usos de red; no incluye peticiones server-to-server ni lo que se mida a nivel TCP/TLS.
- `companion_final_video_download_body_bytes_observed`: respuestas HTTP del Companion en el endpoint de vídeo final **al navegador**, no flujo WAN ni demanda de ancho de banda GCP.
- `request_body_bytes`/ `response_body_bytes`: tamaños que reporta la API de Playwright; si un request no se puede medir, se contabiliza como `unmeasured` y no se inventa 0.
- `python_http_local_final_download_body_bytes_observed`: cuenta real de bytes leídos del cuerpo de la respuesta HTTP por el cliente Python `urllib` al guardar `render.mp4`. **NO** aparece en el registro de solicitudes del navegador porque `e2e_native_stage.py` usa un segundo cliente HTTP para descargar el fichero final. El informe agregado conserva por separado el campo del navegador y el del cliente Python; ambos son loopback.
- La primera ejecución U17C completó ambos MP4 pero falló en una **aserción errónea del test de medición**: exigía ver la descarga Python en el observador Playwright. No fue un fallo de render. La comprobación se ha corregido contando el flujo HTTP donde efectivamente se recibe.
- `originals_total_bytes_local`: total de las tres fuentes sintéticas **solo como tamaño agregado**; no justifica comprobar el contenido de las transferencias por sí solo.
- `original_upload_proven_absent=false`: una lectura de tamaños no prueba que jamás se haya enviado un original completo. La política de fallback del Companion **sí permite** subir originales si el helper falla, y hay que instrumentar y limitar ese caso en la arquitectura SaaS.
- `network_topology=loopback-shared-runner-not-WAN`, `remote_server_bytes_measured=false`, y `network_bytes_to_server=null` en el informe agregado: valores obligatorios **hasta** que se pruebe servidor remoto + clientes físicos separados.

### Límites y riesgo detectado

`web/companion.js` dice explícitamente que, si Companion no está disponible o no puede preparar un fichero, el frontend conserva un **fallback de subida del original**. Esto fue una decisión provisional en U3, no una garantía de original siempre local. El E2E actual verifica que el render usa los originales locales y no el export antiguo; el tráfico medido de esta ejecución será evidencia adicional de qué se transfiere en el escenario que ha funcionado, no validación global contra fallbacks. Para beta híbrida por defecto debe bloquearse la transferencia de vídeos originales completos (salvo un modo excepcional expresamente autorizado), tanto en frontend como backend.

## Siguiente prueba distribuida relevante

En un **servidor de test remoto autorizado** con dos clientes físicos distintos: HTTPS, Google/owner→worker seguro, telemetría CPU/RSS del proceso Companion y del servidor (U17B), peticiones/bytes de subida de proxies a servidor y descarga de recetas, latencias, ingest/Stage, MP4 finales en cada cliente, reanudación y cancelación. Sólo entonces escalar 2→4→8→10 y evaluar 25, sin atribuir la CPU local al servidor.

Todos los cambios son tests, instrumentación y documentación, sin desplegar ni tocar `main`, `8101/8102/8103`, Engine/Mixer, Companion ni el trabajo de cámaras/cortes de Chema. La CI debe quedar **PASS sobre el commit final** antes de considerar validado el incremento.
