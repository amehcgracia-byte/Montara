# URANO U13E2D — Stage → Companion real-derived E2E on current main (2026-11-08)

**Estado:** **PASS** del recorrido integral aislado con fuentes derivadas de una grabación Sony real y master de audio correlacionado, sobre `main` de 2026-11-08. **NO es aprobación de despliegue ni prueba multiusuario**.

## Código acreditado

- Base Montara `main` `beb11d8ea49fdb99a535f036a158baf8de51610e`, Engine submódulo `98bce068bfdf931cc153c41aa9b440f9d3c183af` y Mixer `f15ff91c1b80fc5f157099dcd9451d958d553ae6`.
- Rama de aceptación `fernando/urano-u13e2d-main-companion-real-e2e`: solo cambios en harness de tests, validación de fuentes reales y CI liviana; **sin modificar** aplicación, Engine, Mixer, Companion, scripts de producción ni `main`.
- Port selectivo de #112: `tests/native_real_media_input.py` (fuentes existentes, no symlinks ni duplicados, scratch fuera de raíz de originales, SHA-256 por bloques), `tests/test_native_real_media_input.py`, `tests/e2e_native_stage.py`. El test acepta opcionalmente `MONTARA_TEST_BROWSER_BINARY` para ejecutar una Chrome for Testing local compatible H.264 sin instalar Chrome en el sistema.
- `python -m unittest test_native_real_media_input -v`: **5/5 PASS** en la VM GCP; compilación sintáctica `py_compile`: **PASS**.

## Laboratorio y origen

- Gateway server estático GCP `35.242.225.127`, directorio experimental nuevo `/home/fgardel00/urano-u13e2d-20261108` (código y salidas), con materiales de entrada provenientes de `/home/fgardel00/urano-u13e2c-acceptance-20261108/fixtures`. Ningún original subido al repositorio/CI.
- Material **real derivado**: dos vídeos de 20 segundos `camera-A.mp4`, `camera-B.mp4` (distinto brillo), ambos derivados del mismo fragmento [10, 30] de `/home/fer/lab-clips/originales/C0188.MP4`; `master.wav` extraído del audio de esa misma grabación. **No** son dos cámaras físicas independientes. En test Engine Sync v5 previo, las dos fuentes dieron offset `0.000 s`, confianza `17.328` frente a umbral `6`.
- Chrome for Testing **157.0.8103.38**, descarga oficial Google Chrome Labs, extraída solo en `/home/fgardel00/urano-u13e2c-acceptance-20261108/browser`; bibliotecas locales Ubuntu extraídas en ese directorio, sin instalar globalmente. API navegador `canPlayType(...H264)` = `probably`. La Chromium estándar de Playwright no tenía soporte H.264 en esta VM.
- E2E con `taskset -c 0-3`, `nice -n 10`, bloqueo de laboratorio **local** `/tmp/montara-urano-benchmark-preflight.lock`; no se detuvo ni alteró servicio JM/FER, y se comprobó ausencia de FFmpeg JM pesado al arrancar.
- Python venv existente bajo FER, sin instalar dependencias globales.

## Resultado experimental

`tests/e2e_native_stage.py --output ... --real-camera .../camera-A.mp4 --real-camera .../camera-B.mp4 --real-master .../master.wav` terminó con **exit code 0**, `summary.json`:

```json
{
  "passed": true,
  "size": "1920x1080",
  "original_sources": 2,
  "native_render": true,
  "server_export_skipped": true,
  "real_footage": true,
  "architecture": "Companion local original render, Engine remote recipe in isolated local test"
}
```

- Ejecutado realmente: carga por navegador en loopback, Stage (selector y plano), previsualización audible, edición de encuadre (zoom 3.4) y guardado, petición de render a Companion, MP4 original nativo, decodificación completa con FFmpeg, recarga de resultados y recuperación desde otra vista móvil.
- `render.mp4` **45,621,510 bytes**, además de `chosen-folder/Native acceptance.mp4` y screenshots. Logs locales en `/home/fgardel00/urano-u13e2d-20261108/outputs/native-real-derived.log`.
- El navegador registró un recurso 404 no identificado (`BROWSER_ERROR Failed to load resource`); todas las aserciones funcionales pasaron y `summary.json` fue escrito. No interpretar ese 404 como cero errores de red ni ignorarlo en una futura auditoría.
- Resultado previo de #112 con Engine `841f4ed`: E2E sintético **PASS** y E2E real derivado **PASS** con Chrome H.264. El actual Engine `98bce06` demostró la continuidad del recorrido real derivado.
- **Atención arquitectura**: en estas pruebas aisladas, servidor de recetas Engine y Companion residen ambos en el loopback de la misma VM. No se ha validado un Companion instalado en un Mac de usuario frente a una web remota, ni los límites de confianza de un servicio multiusuario.

## Límites y siguientes decisiones

1. Aceptación con **dos cámaras físicas independientes realmente sincronizadas** y máster verificable; iPhone, Sony y 360 históricos no estaban acreditados como la misma sesión. No desactivar el selector del #107 para pasar el test.
2. 360 con movimiento y exportación en escenario separado; no confundir funcionalidad extra/calidad con benchmark de velocidad.
3. Companion real en macOS y relink de originales tras cerrar/reabrir sesión; el test comprueba la recuperación local de estado y resultado, no un catálogo multiusuario.
4. Owner→Engine, autorización de proyectos, aislamiento de datos de usuario, autenticación Google y beta privada: **pendientes**.
5. Legal FFmpeg/redistribución y auditoría mínima de seguridad de infraestructura: pendientes de su fase; GCP actual es laboratorio, no decisión de proveedor.
6. Esta rama debe ser revisada por Chema; **no fusionar automáticamente**. #112 es histórica/supersedida por esta adaptación a `main` más reciente para el adaptador de pruebas, pero ambas pueden coexistir mientras se auditan.

La prueba demuestra que las mejoras actuales de Chema no han roto el flujo Stage→Companion en este caso de referencia; **no** se extrapola a todos los vídeos ni a usuarios concurrentes.
