# JÚPITER · Windows W3M — cierre seguro del árbol de procesos y lanzador de bandeja

Fecha: 2026-11-05. Rama código: `fernando/companion-windows-w1`, PR [#74](https://github.com/amehcgracia-byte/Montara/pull/74), **draft sin merge**. Evidencia de pruebas anteriores: W3K local (bandeja PowerShell) PASS reportado, W3L frozen EXE+FFmpeg embebido PASS en GitHub Actions [41932220683](https://github.com/amehcgracia-byte/Montara/actions/runs/41932220683).

## Motivo y riesgos

El prototipo W3K detenía el proceso Python principal mediante Stop-Process, sin cobertura automática de FFmpeg activo. Además, la implementación previa de `video_jobs.stop_process_tree()` dependía de `ps` y señales POSIX; no podía ejecutarse en Windows para cancelar un render/mix local. No se ha probado Stage local instalado en Windows.

## Cambios de código aislados

- `companion/video_jobs.py`: rama explícita para Windows de `stop_process_tree(process)` con `taskkill /PID <PID> /T /F`. Se limita a un PID concreto de trabajo; no usa nombres de imagen o terminación indiscriminada por puerto. En POSIX se conserva comportamiento previo. Commit `4a71faa`.
- `tests/windows_companion_process_tree_smoke.py`: crea un proceso Python padre y un hijo que permanecen vivos, solicita cancelación por la función real y comprueba que ambos han terminado. Limpieza de emergencia scoped solo a los PIDs de esa prueba. Commit `b42f497`.
- `companion/windows_tray.ps1`: prototipo versionado de icono de bandeja WinForms/PowerShell para iniciar `MontaraCompanion.exe` congelado junto al script; HOME local, puerto loopback 47820, estado /health y opción Salir. Al cerrar utiliza `taskkill /PID ... /T /F` en el proceso concreto que lanzó. Es una opción de laboratorio: **requiere Windows PowerShell, no está firmada, ni se incluye todavía en un instalador**. Commit `a57672b`.
- Workflow `.github/workflows/companion-windows-smoke.yml`: incorpora parser de PowerShell y prueba de árbol de procesos además del smoke anterior de proxy. Commits `4f95d9c` y `86cf678`.

## Estado de pruebas

CI Windows [41932982496](https://github.com/amehcgracia-byte/Montara/actions/runs/41932982496) se encontraba **en ejecución** al iniciar la documentación. No declarar W3M PASS global hasta confirmar que los pasos `Parse hidden Windows tray launcher`, `Stop Windows video worker and descendants safely` y `Exercise frozen EXE and proxy via localhost` resultan todos exitosos.

## Limitaciones y siguiente gate

- El script de bandeja está validado solo sintácticamente por Actions hasta prueba de uso real; no se ha probado su interfaz desde GitHub Actions.
- `taskkill /T /F` fuerza el cierre en vez de solicitar una terminación elegante; una conversión activa puede quedar con archivo temporal `.part`, y no se garantiza limpieza de todos los casos de procesos ya huérfanos.
- La distribución externa sigue pendiente de licencias FFmpeg, firma, tamaño y validación en máquina limpia. No se genera release ni artifact distribuible.
- Siguiente: revisar resultado CI; si verde, inspección visual/funcional de bandeja con EXE en Windows, y evaluar una parada elegante del servidor con limpieza de trabajos para producción.

**Seguridad:** no tocar servicios JM, engine, mixer ni producción. No merge automático.

## Validación CI completada

El workflow [41932982496](https://github.com/amehcgracia-byte/Montara/actions/runs/41932982496) terminó **SUCCESS**, commit de código `86cf6783b5fc14b4e43f4f462dfda5c0867fc1b9`: build one-folder, preparación de FFmpeg, parser `WINDOWS_TRAY_SYNTAX_PASS`, proceso padre+hijo cancelados y circuito EXE HTTP/proxy superados. **Se ha probado el cierre de árboles en Windows runner; la interacción del icono y los casos de cierre durante un trabajo real aún no.**
