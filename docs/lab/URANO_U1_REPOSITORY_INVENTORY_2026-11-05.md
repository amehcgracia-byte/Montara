# URANO U1 — primer inventario contrastado del repositorio

**Fecha:** 2026-11-05 · **Estado:** lectura inicial, sin cambios de código ni infraestructura.

## Fuentes consultadas

Rama experimental `fernando/companion-windows-w1` de `amehcgracia-byte/Montara`: `README.md`, `CONTRIBUTING.md`, `app.py`, `web/index.html`, `companion/companion.py`, `deployment/vercel/package.json`, `docs/ANTES_DEL_SERVIDOR.md`, `deploy/README.md`, `requirements.txt` y `docs/HANDOFF_FERNANDO_038.md`. **No** se ha revisado todavía íntegramente el frontend JS ni los submódulos Engine/Mixer; la documentación de traspaso contiene información histórica y no reemplaza las comprobaciones de código.

## Mapa inicial (hechos observados)

| Pieza | Existe en repositorio | Observación relevante |
|---|---|---|
| Web | `web/index.html` y assets | Interfaz de Stage/Push/Show con navegación por pantallas. No asumir todavía que sea un SPA moderno ni que todos los modos estén completos |
| Backend Montara | `app.py` | Servidor Flask, endpoints `/montara/*` para muestras, marca/logo, mezcla, referencias y render; acopla interfaz web y `engine/` mediante submódulo sin modificar directamente su API |
| Motor de edición | `engine/` submódulo | El repositorio fija una revisión; **no modificar** desde Montara |
| Mezcla | `mixer/` submódulo | Depende de código y revisión externa; `app.py` contiene rutas de mezclas |
| Companion local | `companion/companion.py` | API localhost, localizar originales, generar proxies, entregar medios y algunos renders; W3L–W3Q auditados en [W3S](JUPITER_WINDOWS_W3S_TECHNICAL_HANDOFF_2026-11-05.md) |
| Vercel | `deployment/vercel/package.json`, `README.md` | Vercel Sandbox `@vercel/sandbox`; prototipo público documentado, **no** es equivalente al servidor privado de producción |
| Servidor Linux | `deploy/README.md`, `docs/ANTES_DEL_SERVIDOR.md` | Despliegue Docker de prueba con una instancia/un usuario, contraseña privada, volume persistente, FFmpeg, Whisper; no prueba un SaaS público multiusuario |
| Dependencias | `requirements.txt` | Flask, OpenCV, FFmpeg externo, Mix, Whisper/Audio, `yt-dlp` y Playwright, entre otros; versión real de runtime se congela en lock del despliegue |

## Hallazgos para evitar decisiones prematuras

1. **No es simplemente «web + microservicio en nube»:** ya existen una aplicación Flask que delega al Engine y Mixer, un prototipo Vercel Sandbox, una instalación Linux privada y Companion. URANO debe **decidir el perímetro**, no crear una segunda arquitectura paralela por defecto.
2. **Stage, Push y Show se nombran en el README**; que estén en la UI no implica que estén probados extremo a extremo con cuentas reales, latencias realistas y archivos de clientes.
3. **YouTube no está completamente validado**: `docs/HANDOFF_FERNANDO_038.md` advierte que el modo se había aplazado; `requirements.txt` contiene `yt-dlp`. Es necesario inspeccionar el código efectivo y las pruebas antes de afirmar funcionalidad.
4. **Servidor privado Linux ≠ servicio de suscripción:** `deploy/README.md` describe una instancia y un editor simultáneo, no aislamiento de clientes ni escalado horizontal.
5. **Companion permite proxies de originales locales** sin subirlos completos en determinados flujos; se requiere mapa de datos y permisos por modo antes de decidir qué va al cloud.
6. El cumplimiento de licencia FFmpeg, la firma y la redistribución se mantienen pendientes fuera de esta investigación; no publicar paquetes.

## URANO U2 — próximas inspecciones concretas

- Seguir desde `web/index.html` a JS reales que llaman a Companion y `/api/v1/`; mapear estado de proyecto, persistencia, render y fallbacks.
- Describir endpoints críticos del `app.py`, validaciones y tránsito de ficheros hacia `engine/` y `mixer/`.
- Evaluar componentes de `deployment/vercel` y `deploy`: ciclo de vida de Sandbox, persistencia, límites de sesión, aislamiento de usuario y costes, sin contratar servicios.
- Contrastar documentación histórica sobre Stage, Push, Show, YouTube y exportación con pruebas CI existentes.
- Preparar un primer diagrama de flujo técnico **basado en código**, con casos de fallo y decisiones abiertas para JM.

## Seguridad y control

Todo este paso es **lectura**. Sin modificaciones del servidor, sin merge de PR #74 y sin pruebas con datos personales o medios privados. Mantener documentación en `fernando/continuacion-montara`.
