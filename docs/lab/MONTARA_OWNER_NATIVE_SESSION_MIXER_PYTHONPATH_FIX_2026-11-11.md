# MONTARA — Reparación de NumPy en sesiones Chema / limpieza VM

**Fecha:** 2026-11-11 · **Rama:** `fernando/integracion` · **Estado real:** nueva sesión Stage `ready`; MP4 final pendiente.

## Incidencia reproducida

El usuario confirmó que la transferencia de vídeos y audios a Stage funcionaba y que la restauración de archivos aparecía. En el paso nativo de Chema **Your session, song by song**, el backend devolvió `No module named 'numpy'`.

El worker privado usa `/opt/montara-engine/python/bin/python3.11`, un Python fijado en el bundle de Engine. El broker inyecta los paquetes del bundle en `sys.path` **solo en el proceso padre**. El código de Chema `full_session.py` inicia el analizador mediante `subprocess.Popen([sys.executable, '-m', 'mixer_adapter.session', ...])`, que **no hereda las modificaciones de `sys.path`**, aunque sí hereda `os.environ`. El proceso hijo no encontraba `numpy`, `scipy` ni otras dependencias.

No faltaban paquetes ni era necesario instalar nada: estaban en el directorio **inmutable y root-pinned** `/opt/montara/bundles/engine-b5e48317ef85225f901adc69af8cc17aa8146880/site` (referenciado por el bundle activo). Se importaron correctamente con el Python fijado: NumPy 1.26.4, SciPy 1.17.1, Librosa 0.11.0, soundfile, pyloudnorm y matchering.

## Corrección de arquitectura

Se modificó un solo archivo **nuestro**, `urano/full_jm_worker.py`: antes de importar la aplicación JM de Chema, el adaptador define `os.environ["PYTHONPATH"]` con el único directorio `engine_root/site` validado, para que los hijos nativos compartan exactamente los paquetes versionados del Engine. Se obliga a que estén los componentes esenciales y se acepta tanto paquete-directorio como módulo `.py` (por ejemplo `soundfile.py`). No se toca `web/`, el Mixer original ni sus scripts de Chema.

**No hubo `pip install`, venv nueva, paquetes globales, duplicación de ruedas, cambios en Cloudflare ni cambios en la rama `main`.**

## Incidente de despliegue y recuperación

La primera validación exigía directorios para todas las librerías; `soundfile` es un módulo `.py`. El worker reiniciado no superó ese control, terminó y su unidad systemd transitoria desapareció. Se comprobó el error exacto en journal. Se corrigió la validación en GitHub, se probó contra el paquete real, y se instaló la corrección en `/opt/montara/broker-smart-candidate/urano/full_jm_worker.py`.

La reserva del antiguo worker (generación 3) permanecía `running` en el ledger; se verificó de forma independiente que la unidad estaba `not-found`, `MainPID=0`, `ActiveState=inactive`, sin cgroup ni `ready.json`. También se confirmó que el proyecto persistente y sus archivos seguían presentes. **Solo entonces** se creó una copia SQLite root-only (`jobs.before-native-session-reclaim-20261111.sqlite3`) y se utilizó `JobRecoveryLedger.request_stop` seguido de `confirm_stopped(..., verified_cgroup_empty=True)`. No se apagó un proceso activo ni se modificó contenido multimedia.

La siguiente activación normal de la beta creó **generación 4** para el mismo proyecto. Comprobación real posterior: broker y servicio activos, PID y cgroup presentes, ready-marker válido con identidad del mismo proyecto. El directorio Owner conserva una sesión antigua `failed` y una nueva `ready` con **3 pistas y 2 canciones detectadas, sin error**.

## Calidad y mantenimiento

- **Prueba de subprocess real en GCP** con el Python, JM y el site versionado: `PINNED_JM_CHILD_IMPORTS_PASS`.
- **25 pruebas Python y 80 subpruebas PASS; 2 pruebas de adaptador JavaScript PASS**, incluyendo los nuevos tests que simulan un módulo `soundfile.py` de un solo archivo.
- HTTPS público `/healthz` 200; portal, túnel y broker activos.
- El staging temporal de este cambio y los cuatro archivos temporales de staging de la integración previa se eliminaron **solo tras comparar contra el contenido desplegado**. Se conservaron únicamente los respaldos necesarios en los directorios de rollback y en el ledger, y el código versionado en GitHub.
- No se reinició el broker, ni se modificó su fichero de servicio, la configuración del autoapagado ni el paquete fuente de Chema.

## Próximo gate

Confirmación humana de que las dos canciones detectadas aparecen en el editor, seguido de la selección de canción, sincronización con las cámaras, edición y exportación final. El estatus `ready` verifica **análisis completado**, no una exportación MP4. La representación final del indicador Engine por proyecto sigue pendiente y debe integrarse separadamente con broker seguro y tests de navegador.
