# JÚPITER · Windows W3Q — prueba del lanzador real de bandeja

Fecha: 2026-11-05. Alcance: laboratorio aislado de `fernando/companion-windows-w1`, [PR #74](https://github.com/amehcgracia-byte/Montara/pull/74), sin merge, release, artefacto distribuido ni servicios JM modificados.

## Contexto

W3P cerró como PASS el empaquetado `onedir` temporal de Companion con `MontaraCompanion.exe`, `bin/ffmpeg.exe`, `bin/ffprobe.exe` y `windows_tray.ps1`. W3M solo comprobaba sintaxis de PowerShell y gestión de procesos aislados. **Faltaba comprobar que el propio lanzador de bandeja llega a arrancar y a detener su EXE**.

## Nuevas comprobaciones W3Q

- `companion/windows_tray.ps1`, commit `a8ff62c`: pequeño mecanismo **opt-in exclusivo de prueba**, `MONTARA_TRAY_SMOKE_MARKER`. Una vez que la bandeja haya arrancado su ejecutable y haya obtenido `/health` con `app=montara-companion`, escribe `W3Q_TRAY_HEALTH_PASS` a la ruta temporal indicada y solicita salida normal del bucle WinForms. Sin esa variable, el comportamiento habitual del menú es idéntico.
- `tests/windows_companion_tray_lifecycle_smoke.py`, commit `fce0468`: valida ausencia de Companion previo en localhost 47820; ejecuta el **PowerShell real** de bandeja desde la carpeta empaquetada en Windows runner; proporciona HOME temporal; espera el indicador de salud y el cierre del lanzador; comprueba después que no queda un servidor en 47820. Cancela únicamente el proceso de prueba si alcanza el límite. No usa vídeos de usuario ni depende de instalaciones Python externas para el proceso congelado.
- `.github/workflows/companion-windows-smoke.yml`, commit `fbc1164`: añade el nuevo paso al pipeline que ya valida paquete, parser, árboles de procesos y proxy real sintético.

## Limitaciones

GitHub Actions no sustituye una sesión interactiva del usuario. Aunque el test de bucle WinForms pasase, **no certifica aparición visual del icono, clic derecho ni menús reales, accesibilidad ni confianza de Windows SmartScreen**. Esa aceptación visual final exige una prueba local guiada, con la PR aún sin integrar.

## Estado

Prueba CI [41935284051](https://github.com/amehcgracia-byte/Montara/actions/runs/41935284051) **pendiente de resultado** al crear este informe. No declarar W3Q PASS final hasta la revisión del estado CI y la aceptación visual local.

## Resultado automático W3Q

La primera ejecución CI [41935284051](https://github.com/amehcgracia-byte/Montara/actions/runs/41935284051) detectó un fallo de PowerShell que la prueba puramente sintáctica no había encontrado: la variable `$home` entra en conflicto con la variable automática de PowerShell `$HOME` (nombres insensibles a mayúsculas). Se corrigieron sus cinco usos a `$dataDir` en commit `265dfe4`.

**W3Q-LIFECYCLE PASS:** el runner Windows [41935447237](https://github.com/amehcgracia-byte/Montara/actions/runs/41935447237), commit `265dfe407463ae4c1fcfd9ba3cc5558d2c85fb82`, finalizó **completed/success**. El paso `Exercise actual tray event loop with packaged EXE` quedó verde: WinForms ejecutó su event loop, lanzó el binario empaquetado, detectó `/health`, realizó salida normal y dejó libre el puerto local. Volvieron a pasar las pruebas de FFmpeg y proxy. **Queda pendiente la aceptación visual por una persona en Windows 10 y las obligaciones de distribución/licencia.**

## Aceptación visual del usuario — PASS

El usuario confirma explícitamente: **«W3Q aceptación visual: PASS. He verificado los cinco puntos, incluido el cierre del Companion.»** Verificó en su Windows 10: (1) arranque sin consola visible, (2) icono de bandeja junto al reloj o área oculta, (3) menú contextual accesible por clic derecho, (4) estado «funcionando» y comprobación de conexión en navegador mediante `/health`, y (5) salida mediante «Salir de Montara», desaparición del icono y cese de conexión. **W3Q aceptación visual: PASS reportado por el usuario; no comprobación remota independiente.**

La prueba local empleó el **EXE W3L construido previamente por el usuario** y el **lanzador corregido del commit `265dfe407463ae4c1fcfd9ba3cc5558d2c85fb82`**, preparado en su carpeta de W3L. **No certifica** la ejecución local de la última versión con FFmpeg embebido, ni instalador, ni condiciones de redistribución/licencia; esas quedan pendientes de W3R. Ninguna modificación a producción, PR #74 continúa draft.
