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
