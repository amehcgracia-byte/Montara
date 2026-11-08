# URANO U13E2C — Ensayo Stage con media real derivada · 2026-11-08

**Estado:** progreso real hasta Edit y sincronización acreditada; exportación interrumpida deliberadamente para no competir con una tarea pesada de JM. **No** se declara Stage→Companion→MP4→recuperación aceptado.

## Contexto / aislamiento

- VM GCP de pruebas mediante Gateway `montara-test-gcp-static`, SSH; disco ~69 GiB libres durante el ensayo.
- Checkout experimental nuevo `/home/fgardel00/urano-u13e2c-acceptance-20261108/montara` desde PR #112, commit `16a87a78` con submódulo **Engine `841f4ed55e70c8478f1f9413ac77e548e99f7097`**, Mixer `f15ff91`. No se modificaron `main`, `/home/fer/montara` (con cuatro ajustes locales) ni `/home/jm/montara`.
- Carpeta privada de trabajo `/home/fgardel00/urano-u13e2c-acceptance-20261108/`, con `fixtures`, `outputs` y `outputs/engine-data`. No se publicaron originales en GitHub/Actions.
- Se utilizaron **fragmentos derivados reales** de `/home/fer/lab-clips/originales/C0188.MP4` (Sony H.264 1080p25, PCM), no dos cámaras físicas independientes. Se extrajeron el mismo intervalo [10 s, 30 s] en `camera-A.mp4` y `camera-B.mp4` (segunda variante visual con brillo +0.03) y `master.wav` del audio del mismo archivo. Entradas finales de 20 s, aprox. 4.31 MB, 4.30 MB y 3.84 MB. El original no se movió ni modificó.
- Python del venv FER existente; sin instalaciones. Ejecución limitada a afinidad CPUs 0–3 y prioridad `nice 10`, bloqueo local `/tmp/montara-urano-benchmark-preflight.lock`. El lock global `/var/lock/montara/bench.lock` figura en GitHub pero no está instalado en la VM.

## Resultados comprobados

1. **SyncStage real**, `SYNC_ALGORITHM_VERSION=5`, master de mismo origen: `camera-A.mp4` y `camera-B.mp4` con offsets **0.0 s** y confianza **17.32818**, umbral configurado **6.0**; ~21.104 s para esta invocación directa. Esto NO prueba sincronía iPhone/360 con master de concierto.
2. **PipelineEngine.run_sync(project, 'edit')** ejecutado realmente en proyecto nuevo `outputs/pipeline-sony.zuckervid`: **ingest DONE (12.267 s), sync DONE (1.431 s), cut DONE (0.023 s), edit DONE (18.602 s)**. Tiempo total de esta ejecución **32.37 s**; `export` estaba pending al terminar. Artefactos persistidos `sync_map.json`, `beats.json`, `coverage.json`, `edit_plan.json`. Son tiempos de una muestra pequeña; no benchmark de capacidad.
3. **ExportStage** lanzado en ese proyecto aislado; llegó a generar varios segmentos MP4 en la carpeta temporal, pero durante el trabajo se observó FFmpeg de usuario `jm` al **~560–573 % CPU** (PID 28792 en esa observación), carga alta. Se envió señal TERM **solo al grupo de procesos de nuestro ensayo** (PGID 30142). Posterior comprobación: nuestros procesos ya no figuraban; el FFmpeg de JM seguía vivo. **No hay exportación final verificada**; estado persistido `export=running` puede haber quedado sin cerrar tras interrupción externa. Mantener como ensayo incompleto, no reanudar sin reconciliar estado. No borrar ni declarar fallo de Engine.
4. Chromium instalado en VM desde caché Playwright no reporta H.264 en `canPlayType('video/mp4;codecs="avc1.42E01E"')`. La aceptación `tests/e2e_native_stage.py` exige H.264 y en esta máquina no puede declararse superada sin navegador compatible. No se instaló software adicional.
5. El checkout experimental de #112 lleva Engine `841f4ed`, mientras `main` del 08-11 (`beb11d8ea`) fija Engine `98bce06`; **no confundir ejecución en PR #112 con validación del main actual**. La suite Linux de la PR está verde en GitHub, pero usa material sintético.

## Próximos pasos concretos (sin dar por realizados)

- Esperar a que el servidor esté disponible; **no reiniciar servicios ni interferir con JM**. Examinar el estado incompleto del proyecto aislado y reiniciar un ensayo nuevo o controlar la recuperación sin borrar artefactos ajenos.
- Ejecutar export con `branding=none` y la receta validada para acortar el render (el primer intento exportaba logos/intro y mucho más de la duración de media); validar salida con ffprobe, decodificación completa y hash. En el pipeline usado, la duración de render prevista puede sobrepasar los 20 s del clip por branding y composición.
- Validar E2E de navegador Companion en un entorno con H.264 confirmado, luego restauración de proyecto/receta y originales.
- Reconciliar selectivamente #112 sobre el actual main y Engine sin pisar cambios de Chema. No cambiar `main`, servicios activos, medios ni permisos.

**Interpretación:** hubo un avance real y reproducible hasta **Edit** con medios de cámara reales y sync confirmado. Aún no hay MP4 final ni aceptación Companion con navegador, y menos aislamiento multiusuario del Engine.
