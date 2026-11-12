# Montara Companion Windows — actualizador manual H4 (0.6.11-h4.1)

Fecha: 2026-11-12. Rama `fernando/chema-native-owner`. Estado: desplegado el canal HTTPS de H4; **pendiente de validación humana en Windows 10**.

## Alcance exacto

El usuario pidió no comprobar actualizaciones cada hora: el modo H4 es **solo manual**, mediante icono de la bandeja de Windows → `Buscar e instalar actualización...`. No se instala servicio, tarea programada ni supervisor remoto; no hay avisos automáticos sin consulta del usuario. En nuevas versiones se puede introducir badge/notificación si se decide posteriormente.

La primera instalación (`bootstrap.zip`) añade los scripts del controlador de bandeja, un acceso directo al escritorio y el parche de `local_video.py` que tolera `WinError 5` **solo al escribir el JSON de progreso**. Conservar íntegros `video/engine/`, `video/venv/`, los originales, los vídeos finales, los proyectos y la configuración.

`Companion` núcleo continúa identificándose como `0.6.10` en `/health`; `0.6.11-h4.1` es la **versión del parche/actualizador de beta**, visible junto a la versión núcleo en el menú Estado.

## Instalar una única vez

1. Cerrar Companion; nunca durante un render.
2. Descargar y extraer [bootstrap.zip](https://montara-owner-h4.memoriainvalida001.workers.dev/urano/v1/companion-updates/bootstrap.zip).
3. Desde PowerShell en la carpeta extraída: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Instalar-Montara-Actualizador.ps1"`.
4. Si no encuentra el `companion.py` que ya usaba, el instalador pide seleccionarlo **una sola vez**. Si no encuentra Python 3.11, pide elegir su `python.exe`. No modifica ninguna instalación de Python.
5. Instala el acceso directo `Montara Companion` en Escritorio. Desde la bandeja junto al reloj: Estado, Buscar e instalar actualización, Salir.

El instalador exige que exista la ruta de Engine `%LOCALAPPDATA%\MontaraSMARTBeta\video\engine\core\stages\export.py` y que el puerto Companion no esté ocupado. Guarda reversión previa del `local_video.py` en `%LOCALAPPDATA%\MontaraSMARTBeta\Updater\local_video.anterior.py`. El controlador establece `MONTARA_COMPANION_HOME=%LOCALAPPDATA%\MontaraSMARTBeta` al arrancar el Companion localizado.

## Las actualizaciones posteriores

- El icono consulta manualmente `GET /urano/v1/companion-updates/manifest.json`, ofrecido por **la beta H4 de Cloudflare**. No necesita credenciales GitHub ni expone tokens OAuth.
- Comprueba versión y pide confirmación; no detiene trabajos activos ni procesos que el icono no haya iniciado.
- Descarga el ZIP versionado sobre HTTPS, comprueba tamaño máximo de 1 MB y SHA-256 del manifiesto.
- Extrae y verifica una lista cerrada de destinos autorizados. La primera actualización contiene 3 archivos (`local_video.py`, `Montara-Bandeja.ps1`, `Montara-Actualizar.ps1`); el actualizador también puede recibir, en futuras versiones revisadas, `companion.py`, `video_jobs.py`, `video_recipe.py`, `windows_support.py` y `spherical_proxy.py`. No acepta otros nombres ni directorios, y crea rollback `.rollback` antes de sustituirlos.
- Cierra su Companion local controlado, instala la versión y reabre el icono/Companion. Si falla, intenta restaurar el backup y reabrir el icono.
- No se efectúan cambios en motor ni datos del usuario. Las futuras actualizaciones del Engine o de dependencias siguen requiriendo un instalador de runtime explícito; no se permite que este actualizador sobrescriba el Engine.

## Servicio H4

- Blueprint: `urano/native_owner_companion_updates.py`, con 3 rutas exactas y sin exploración de directorios.
- Composición: `urano/native_owner_app.py`, registro solo al detectar directorio de release fijado por el operador.
- Almacenamiento privado en VM: `~/.config/montara-h4-native/companion-updates/`, tres archivos `manifest.json`, `package.zip`, `bootstrap.zip`.
- El servicio verifica sha256 y longitud de los dos paquetes al iniciar. Responde solo al Host/origen H4 previsto.
- **Limitación beta:** este feed público sirve código de Companion sin secretos y depende de la VM H4 encendida. En la versión distribuida del producto habrá que trasladarlo a almacenamiento estático disponible permanentemente y con firma independiente del manifiesto (SHA-256 + TLS no sustituyen firma de publicación).
- Como el repositorio es privado, no utilizar GitHub raw ni almacenar PAT en el ordenador del usuario. Una comprobación manual que detecta la versión actual no cierra ni reinicia Companion.

## Verificaciones ya realizadas

- Python: 4 pruebas del fallo WinError 5 superadas (`tests/test_companion_windows_render_progress.py`).
- Comparación de `companion/local_video.py` contra el bundle de Chema: únicamente se añaden los reintentos del progreso.
- Blueprint Flask en VM: manifest, paquete y bootstrap HTTP 200; Host ajeno 403.
- Público Cloudflare: los 3 recursos HTTPS HTTP 200 y MIME correcto; H4 y beta previa health 200.
- **Aún no** se ha probado el propio script PowerShell ni el ciclo de arranque/actualización/reinicio en Windows 10. Ese es el siguiente gate de validación humana, sin hacer otro render hasta confirmar Companion conectado.

## Reversión

Para una incidencia con el parche, cerrar Companion y copiar `Updater\local_video.anterior.py` sobre `video\local_video.py`, sin borrar `engine` ni `projects.json`. Los scripts del controlador de bandeja pueden desactivarse sin eliminar el servicio de vídeo o los originales.

## Riesgos pendientes

- Windows Defender/SmartScreen y ejecución de scripts no firmados en beta: el usuario puede requerir lanzar el instalador desde PowerShell. No ocultar ese hecho.
- Una sesión Companion ya levantada fuera de la bandeja no se cierra a la fuerza. El usuario debe terminarla primero.
- El control de conexión HTTP local y el icono deben validarse en Windows 10; icono usa `SystemIcons.Application` (provisional), no icono Montara definitivo.
- Se necesita un mecanismo de actualización firmado, licencia/distribución revisadas y un instalador nativo antes de abrir la beta comercial.
