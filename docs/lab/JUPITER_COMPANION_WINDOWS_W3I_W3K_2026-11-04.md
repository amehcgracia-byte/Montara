# JÚPITER · Windows Companion W3I–W3K — selector y arranque discreto

Fecha: 2026-11-04. Responsable de pruebas: FER. Rama de documentación `fernando/continuacion-montara`. **Resultados locales comunicados por el usuario; no es evidencia de instalador distribuible**.

## W3I — selector de carpetas: PASS

Sobre Windows 10 AMD64 con Python 3.11.9 y código de Companion tomado del commit `cca1bce`:
- Raíces de búsqueda propuestas: **10**; existentes: **5**.
- Unidades detectadas: **1** (solo C: disponible en el reconocimiento previo).
- Selector nativo `choose_folder`: **Aceptada** una carpeta; resultado `SELECTOR: OK`, `CARPETA_EXISTENTE: SI`, `W3I_WINDOWS_PASS`.
- Laboratorio temporal limpiado. **No se han evaluado discos externos.**

## W3J — arranque portátil mediante CMD: PASS

Se creó un directorio de laboratorio local con `companion.py`, `windows_support.py`, `video_jobs.py` y `video_recipe.py`, más acceso `Iniciar-Montara.cmd`. Ejecutado con Python 3.11 y FFmpeg ya presentes en PATH. El navegador accedió a `http://127.0.0.1:47820/health` y devolvió:

- `app: montara-companion`, `version: 0.6.2`, `ffmpeg: true`.
- `hardware_encoder: false`, `tonemap: true`, `lossless_audio: true`, `audio_preview: true`; `local_mix: null`, `local_video: null`.

**No** se interpretan los valores `null` como disponibilidad de render Stage local ni de mezclador. W3J exige mantener una consola abierta, por lo que es solo un medio de prueba.

## W3K — prototipo de bandeja Windows: PASS observado

Se construyó un **script PowerShell de laboratorio** `Montara-Bandeja.ps1` y un acceso directo `Iniciar-Montara-Sin-Consola.lnk` que arranca el mismo Companion en segundo plano, muestra un icono de bandeja de sistema con menú de **estado**, **comprobar conexión** y **salir**. El usuario confirmó que **todo funcionó conforme a lo descrito**: arranque sin consola visible, icono/menú operativo y salida controlada.

Precauciones:
- El lanzador se ejecuta en PowerShell 5.1 (Windows Forms), usando `py -3.11` y FFmpeg **ya instalados**; no es aplicación independiente ni instalador.
- No se ha probado la cancelación de un job FFmpeg activo ni la eliminación del árbol de procesos.
- No se ha evaluado reinicio automático, actualizaciones, permisos empresariales, certificados de firma ni distribución de binarios.
- Script y acceso directo de W3K se generaron localmente durante la prueba; **todavía no se han añadido como archivos versionados a la PR**.

## Estado de producto y próximos pasos

1. **W3I/W3J/W3K se cierran como prototipos locales nativos Windows.** W3F/H ya validaron el recorrido HTTP+proxy real y metadatos SDR BT.709.
2. Antes de distribuir nada, versionar un lanzador mantenible con cierre y logs adecuados, revisar la gestión de subprocess/FFmpeg y pasar pruebas de empaquetado en una máquina sin Python.
3. Evaluar empaquetado tipo one-folder de PyInstaller o equivalente, con FFmpeg/FFprobe redistribuibles, licencia y tamaño; no mezclar aún con render local de Stage.
4. Mantener la PR [#74](https://github.com/amehcgracia-byte/Montara/pull/74) **draft** y no fusionar sin revisión del responsable JM y CI. Los componentes W3K se han probado **solo en la máquina de FER**.

Este informe registra evidencia real sin extrapolarla a software listo para distribuir.
