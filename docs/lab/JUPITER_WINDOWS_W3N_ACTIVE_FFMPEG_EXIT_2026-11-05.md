# JÚPITER · Windows W3N — cierre con FFmpeg activo

**Fecha:** 2026-11-05 · **Estado:** prueba Windows automatizada en curso; no certificar PASS hasta comprobar GitHub Actions. Rama de código `fernando/companion-windows-w1`, [PR #74](https://github.com/amehcgracia-byte/Montara/pull/74) draft, **sin merge**.

## Motivación

W3M comprobó el cierre del árbol de procesos padre/hijo con un hijo Python ficticio y dejó un lanzador PowerShell de bandeja con terminación `taskkill /PID ... /T /F`. Faltaba contrastar el comportamiento con **FFmpeg real** mientras estuviera trabajando. Esta prueba añade evidencia relevante sin recurrir a Windows local de FER.

## W3N · Prueba creada

- Archivo `tests/windows_companion_active_ffmpeg_exit_smoke.py`, commit `882f7d4`. Arranca proceso padre Python que lanza FFmpeg real con fuente `lavfi testsrc2` de **160×90 px a 10 fps**, limitado a velocidad real y con duración nominal máxima de 90 s. Salida `null` (sin vídeo ni archivos privados); registra PID del FFmpeg hijo en carpeta temporal.
- Antes del cierre, verifica **dos PIDs vivos** y emite `W3N_ACTIVE_FFMPEG_RUNNING`.
- Simula la salida del prototipo de bandeja aplicando `taskkill /PID <parent> /T /F`. Verifica fin del padre y comprueba que FFmpeg **no queda huérfano**: `W3N_ACTIVE_FFMPEG_EXIT_PASS`.
- Limpieza de emergencia para limitar las acciones a procesos de laboratorio. No se toca producto, puertos, servicios JM ni motor Stage.
- Workflow `.github/workflows/companion-windows-smoke.yml` actualizado, commit `0f455ac`. CI Windows [41933549150](https://github.com/amehcgracia-byte/Montara/actions/runs/41933549150).

## Qué demuestra y qué no

**Si la prueba pasa:** un árbol de procesos Windows con un FFmpeg real y activo puede ser terminado por PID usando la misma estrategia de salida que W3M. No prueba interacción del icono de bandeja, terminación graceful del servidor HTTP, ni cierre durante un trabajo disparado por la propia API de Companion. Tampoco prueba eliminación automática de temporales `.part`, cierre ante cortes de energía o interrupciones del proceso que pierda su padre.

**Próximo gate:** validar resultado del CI; luego diseñar política segura y testeable de recuperación de archivos pendientes sin borrar trabajos de otra instancia. La experiencia de usuario definitiva (app sin consola/instalador firmado) sigue pendiente; cualquier prueba visual real se hará como aceptación final y no como paso de depuración repetitivo.

**Regla:** sin releases ni binarios FFmpeg distribuidos; revisar licencias y firma antes de publicar.

## Resultado real (GitHub Actions)

**W3N PASS:** [Windows runner 41933549150](https://github.com/amehcgracia-byte/Montara/actions/runs/41933549150) finalizó **completed/success**. El paso `Stop active synthetic FFmpeg on simulated tray exit` superó el experimento con FFmpeg vivo, y continuaron en verde la prueba del cierre padre/hijo, el parser del lanzador y el circuito HTTP del ejecutable empaquetado. Esto **no demuestra** todavía la parada de un job que se haya iniciado realmente desde `/proxies` con un usuario pulsando el menú de bandeja.
