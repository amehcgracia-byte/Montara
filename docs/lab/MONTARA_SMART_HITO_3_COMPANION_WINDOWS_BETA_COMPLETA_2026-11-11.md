## CIERRE FUNCIONAL: MP4 nativo real en Windows — PASS

**Prueba de aceptación del hito 3 completada:** GitHub Actions Windows runner, workflow `fer-smart-companion-package.yml`, [run #43038849790](https://github.com/amehcgracia-byte/Montara/actions/runs/43038849790), step **Render an actual 1080p MP4 on Windows from local originals — SUCCESS**.

Se instaló el ZIP final desde una carpeta temporal, se crearon clips sintéticos con FFmpeg y se llamó al **`VideoJobs` ORIGINAL de Chema** con la adaptación Windows y el Engine `b867b3c`. Resultado concreto del log:

```json
{"SMART_WINDOWS_NATIVE_REAL_MP4_PASS":true,"engine":"b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b","mp4_bytes":4218608,"originals_uploaded":false,"rendered_resolution":"1920x1080","saved_inside_selected_project":true,"source_untouched":true}
```

También PASS en el mismo Windows runner: instalación del Engine Python 3.11, import de `ExportStage`, Companion local en puerto 47820, estado `/health` con `local_video.engine` exacto, FFmpeg presente, origen Cloudflare autorizado y origen externo rechazado. Comprobación de PowerShell AST para instalador y bandeja.

**Distribución final verificable:** `Montara-SMART-Beta-Windows-COMPLETO.zip`, 160 archivos; SHA256 del ZIP interior descargado del run **`384db08a6dc36cb54ea5069103dd771e5c6351a9772e5b2ba18c5d7d29af6c18`**. Manifiesto SHA-256 de 159 archivos verificado, sin credenciales.

Esto permite declarar **HITO 3/5 COMPLETADO TÉCNICAMENTE**. No confundir con haber instalado aún el paquete en el equipo personal de Fernando ni con haber realizado el E2E Google → Owner → Companion → MP4: eso corresponde a los hitos 4 y 5.

---
# MONTARA SMART — Hito 3/5: Companion Windows beta y renderizador local

Fecha: 11 de noviembre de 2026. Rama: `fernando/integracion`. **No fusionar a `main` antes de la validación humana de Fernando.**

## Integración terminada en código y paquete

Se ha convertido la integración previa Stage → Companion en una distribución Windows **completa (código del renderizador incluido)**, reutilizando y preservando los componentes originales de Chema y el lanzador de bandeja de Fernando. No se ha tocado el código ni las instalaciones existentes del usuario:

- `C:\Users\lakme\AppData\Local\Montara-Companion`.
- `C:\Users\lakme\AppData\Local\Montara-Companion-Lab` (fuente 0.6.2).
- `C:\Users\lakme\AppData\Local\Montara-W3L-Build` (PyInstaller y Windows tray).

El inventario ZIP del usuario `Montara-Companion-Inventario-SMART.zip` contiene los prototipos reales `Montara-Bandeja.ps1` y `windows_tray.ps1`, además de fuentes. El nuevo `companion/windows_tray_smart.ps1` hereda su diseño WinForms, monitorización de salud, icono de notificación, apertura de página y detención solo del proceso que arrancó. **Si `/health.busy` es verdadero no se permite salir ni interrumpir el MP4.** No se detiene nada por nombre de proceso ni se sustituye ninguna instalación.

Archivos de la entrega:
- `companion/windows_tray_smart.ps1`: icono y estado local, abre origen Cloudflare, cierre que respeta trabajos.
- `companion/smart_beta_launcher.py`: ejecuta el Companion original JM 0.6.10 solo en localhost 47820, acepta exclusivamente el origen `https://montara-owner.memoriainvalida001.workers.dev`, almacena sus datos en `%LOCALAPPDATA%\MontaraSMARTBeta`.
- `companion/windows_video_jobs_compat.py`: parche mínimo, solo en la copia empaquetada, para `venv\Scripts\python.exe` y `taskkill /T /F`; preserva fuente original.
- `companion/INSTALAR-RENDER-SMART.ps1`: instalador explícito del render nativo, Python **3.11**, FFmpeg/ffprobe requeridos, venv con dependencias acotadas, revisión SHA, prueba `from core.stages.export import ExportStage`, rollback de código en error, instalación exclusivamente dentro del nuevo HOME.
- `companion/build_smart_beta.py`: empaqueta fuentes Chema `14cce126`, Engine `b867b3c` (todos los archivos versionados `core/`), marcas de versión, logos originales y scripts Windows. Incluye 160 archivos, sin incluir originales privados, cachés ni instaladores antiguos.
- `.github/workflows/fer-smart-companion-package.yml`: compila el ZIP en **Windows GitHub Actions** y comprueba sintaxis PowerShell, integridad ZIP y versión exacta del Engine. Extendida con instalación real de dependencias, import del Engine y arranque de Companion con `/health` + origin CORS. Workflow run final: `43037916181` (verificar conclusión PASS).

## Pruebas funcionales respaldadas

1. En GCP, Stage real con nuevo Engine pasó por sincronización y revisión y devolvió **cuatro segmentos** para la receta; audio máster WAV **1.152.078 bytes** recibido con HTTP 200 mediante el gateway privado, `edit/native-source` ajeno rechazado. El broker propietario y el portal Cloudflare permanecen activos.
2. Test HTTP/Unix real de máster de ~4,6 MiB transmitido sin buffering total y protegido por propietario/CSRF (3/3 PASS).
3. En GCP, empaquetado reproducible de ZIP de fuentes verificadas (160 archivos), sin modificar fuentes de Chema.
4. En Windows GitHub Actions, un runner real instala dependencias, importa `core.stages.export.ExportStage`, arranca Companion y consulta su `/health` confirmando el Engine `b867b3c`, FFmpeg disponible y sin trabajos en curso; prueba adicional de origen HTTPS permitido y origen ajeno denegado. **No equivale a una prueba de render MP4 final en el PC físico del usuario.**

## Entrega y prueba física pendiente

Archivo entregable del workflow: `Montara-SMART-Beta-Windows-COMPLETO.zip`, descargado del run Windows Actions y disponible para Fernando. En el ZIP:
- `INSTALAR-RENDER-SMART.cmd` prepara **solo** el renderizador nuevo (requiere `py -3.11` y FFmpeg en PATH; no se instalará nada si el puerto 47820 está ocupado).
- `INICIAR-SMART-BETA.cmd` abre el icono de bandeja sin consola visible.
- `LEEME-SMART-BETA.txt` explica configuración, modo aislado y pasos.

**Todavía pendiente:** ejecutar en el Windows personal de Fernando y verificar icono, carpeta elegida, proxies y MP4 local real. Esto formará parte de la validación integrada (hito 4/5) y humana (hito 5/5). No afirmar instalado ni probado en su PC.

**Importante:** cuenta personal Windows usa Python por defecto 3.14.3; antes de instalar el Engine debe existir Python **3.11** accesible mediante `py -3.11`. El CMD de su antigua versión 0.6.2 invoca esa revisión, pero NO se ha confirmado que aún esté instalada.

## Seguridad, límites y regresión

El nuevo paquete no modifica `main`, `engine/` ni `mixer/` del repo. No contiene credenciales ni originales de usuario. Mantiene Companion local escuchando `127.0.0.1:47820` con origen exacto sin wildcard. La carpeta aislada de programa/datos permite volver a las tres versiones previas. La exportación local produce el MP4 donde se elija; originales nunca se suben al servidor durante el flujo normal.

El hito 3 se considera **integrado y compilado en Windows**, pendiente la validación humana con equipo real, sin nuevas etapas de infraestructura. **Siguiente: hito 4 — ensayo integrado hasta MP4 con Owner + navegador + Companion**. Después hito 5 — Fernando valida la experiencia en Windows antes de la integración escalonada a `main`.
