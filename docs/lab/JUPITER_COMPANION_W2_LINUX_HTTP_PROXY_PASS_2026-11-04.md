# JÚPITER · Companion W2 — integración HTTP, proxy y proyecto en Linux

**Fecha:** 2026-11-04. **Laboratorio:** FER. **Estado:** PASS de integración focalizada en Linux; no valida Windows ni un recorrido web de producto completo. **No** se modificó producción, ni servicios de JM/FER, ni submódulos.

## Objetivo

Comprobar el contrato existente de Companion, al margen de los servicios de Montara: arrancar una instancia temporal en loopback, localizar un original por identidad, generar un proxy mediante FFmpeg, obtenerlo por HTTP y crear/guardar un proyecto. Esta prueba es independiente de la PR de portabilidad Windows [#74](https://github.com/amehcgracia-byte/Montara/pull/74), que sigue siendo una candidata de revisión.

## Entorno y aislamiento

- Referencia exacta del código descargado para las pruebas: Montara `main=4f96af9594d1f747d64d62d24b2d0f4f04103ebd`; `companion.py`, `video_jobs.py`, `video_recipe.py` obtenidos sin sobrescribir el checkout histórico FER.
- Python 3.12.3, FFmpeg y FFprobe del sistema Linux; máquina GCP con 31 GiB RAM y 48 GB de disco libre durante el preflight W2A. Sin FFmpeg en ejecución en el preflight.
- Companion 0.6.2 escuchando temporalmente en **127.0.0.1:47821**, distinto de la configuración normal de 47820 y de los servidores existentes 8101/8102. Datos, originales sintéticos, proyectos y caché en un directorio efímero aislado bajo HOME de FER. El script registró apagado del proceso mediante `trap`; **no hay comprobación posterior independiente de la lista de procesos**.
- **No** se abrió puerto público, no se instaló servicio, no se ejecutó `engine/`, no se descargaron vídeos privados, no se tocaron los directorios de JM. Los scripts de la prueba usan un `Origin: http://localhost:3000` permitido por la política de Companion; el HTTP se realizó en loopback, no en un navegador real.

## W2A — Preflight (PASS)

- Python, FFmpeg, FFprobe, curl y Git disponibles; 47821 libre; 8101 y 8102 ocupados por Gunicorn legítimos.
- Checkout antiguo de FER no incluía `video_jobs.py` ni `video_recipe.py`, por lo que se descargaron los tres archivos actuales desde el commit fijado, directamente a laboratorio privado. No se actualizó el checkout antiguo ni se mezclaron versiones.
- Sin vídeo pequeño adecuado localizado con el filtro de búsqueda; se creó un vídeo sintético de 2 segundos, 640×360, a 30 fps, H.264/AAC.

## W2B — Original, proxy y entrega HTTP (PASS)

| Validación | Resultado observado |
|---|---|
| `GET /health` | Respuesta correcta, versión **0.6.2**, `ffmpeg=true`, `hardware_encoder=false` |
| `POST /locate` | **HTTP 200**, usando nombre, tamaño y SHA-256 de primeros/últimos 64 KiB |
| `POST /proxies` | **HTTP 202**; estado `working → ready` |
| `GET /proxies/{id}/file` | **HTTP 200**, vídeo transferido y guardado |
| Tiempo para fabricar el proxy, informado por Companion | **0.5 s** (solo esta muestra) |
| Fuente sintética | **0.472 MiB** aprox., 2 s, 640×360 |
| Bytes del proxy descargado | **193,466 bytes** |
| FFprobe del proxy | **H.264**, **640×360**, **30/1 fps**, color space/transfer/primaries **bt709** |

**Interpretación:** el proxy resultó aproximadamente 61 % menor que la fuente sintética, pero la muestra ya era 640×360; **no** se ha demostrado ahorro al reducir 4K→720p ni beneficio general de rendimiento. Se usó codificador software; **no** es validación de NVENC/QSV/AMF. El endpoint `/health` solo atestigua FFmpeg disponible, no calidad audiovisual perceptual.

## W2C — Carpetas de proyecto y guardado (PASS)

En una **segunda ejecución temporal**, conservando los artefactos privados W2B:

1. `POST /projects` con nombre de prueba → **HTTP 200**, identificador de proyecto, carpeta dentro de raíz experimental y `montara-project.json` presentes.
2. `POST /projects/{id}/save?name=...` con el proxy recibido → **HTTP 200**.
3. Archivo guardado dentro de la carpeta del proyecto, **bytes exactamente iguales** a los enviados y ruta de respuesta coincidente.

Resultado final confirmado por la consola: `W2C_PASS` y `W2C_COMPLETADO`.

## Límites y decisión

**W2 se cierra para el contrato Linux básico HTTP/proxies/proyectos.** No certifica una sesión completa de Montara en navegador, un flujo remoto entre dispositivos, exportación Stage local, persistencia tras reinicio ni Windows nativo. No se hicieron medidas de ancho de banda WAN ni de usuarios concurrentes.

Próxima etapa: terminar la validación de [Companion Windows W1, PR #74](https://github.com/amehcgracia-byte/Montara/pull/74), revisar su CI y ensayar búsqueda/selector de carpetas en Windows real **sin instalar todavía el motor audiovisual completo**. A continuación desarrollar instalación ligera y codificación NVENC/QSV/AMF con fallback. URANO (web/host/arquitectura y costes) puede diseñarse en paralelo, sin bloquear esta validación.

**No hay solicitud de merge ni despliegue; se presenta como evidencia focalizada.**
