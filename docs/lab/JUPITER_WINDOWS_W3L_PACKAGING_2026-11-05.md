# JÚPITER · Windows one-folder W3L / FFmpeg embebido — investigación de portabilidad

**Fecha:** 2026-11-05 · **Responsable:** FER · **Alcance:** laboratorio, PR [#74](https://github.com/amehcgracia-byte/Montara/pull/74) draft sin merge. **No se genera ni distribuye un instalador comercial.**

## W3L-B · Build del usuario: PASS

El usuario generó por primera vez `MontaraCompanion.exe` desde Python 3.11.9 mediante PyInstaller 6.22.3, en venv aislado; empaquetado `--onedir` correcto. Carpeta de salida de **24,4 MiB** aprox. en su Windows 10. **No** ejecutó este EXE local tras la compilación, por lo que se validó únicamente el build.

## Primera prueba GitHub Actions Windows

- Nuevo workflow `.github/workflows/companion-windows-smoke.yml`, runner `windows-latest`, Python 3.11, PyInstaller, FFmpeg disponible. Construye one-folder y arranca EXE en loopback contra un vídeo sintético 640×360 de 2 s.
- La primera ejecución [41930828228](https://github.com/amehcgracia-byte/Montara/actions/runs/41930828228) marcó **failure** pese a imprimir `PACKAGED_HEALTH_PASS`, `PACKAGED_LOCATE_PASS`, `PACKAGED_PROXY_PASS` y `WINDOWS_PACKAGED_SMOKE_PASS`. Causa real del fallo global: `UnicodeEncodeError` del script de diagnóstico al mostrar caracteres no representables en `cp1252` tras concluir las pruebas funcionales.
- Corrección diagnóstica `f0a7ba8`: escape seguro ASCII al imprimir registros. Reejecución [41931185508](https://github.com/amehcgracia-byte/Montara/actions/runs/41931185508) **SUCCESS**, valida el EXE congelado y la API hasta descargar proxy de 159.816 bytes y confirmar H.264 / 640×360 / 30 fps / BT.709.
- En el runner el paquete `onedir` pesaba **26,6 MiB**, diferente de los 24,4 MiB obtenidos localmente; no comparar como benchmark uniforme.

## Dependencia de FFmpeg: investigación siguiente

La primera prueba utilizaba FFmpeg del PATH del runner; el EXE empaquetado no necesitaba Python instalado para **ejecutarse**, pero sí FFmpeg y FFprobe. Se están probando cambios **solo en PR draft**:

- `companion.tool()` da prioridad a `bin/ffmpeg.exe` y `bin/ffprobe.exe` situados al lado del EXE congelado; mantiene búsqueda previa en PATH para ejecución no congelada o instalación sin binarios embebidos. Commit `2e19d27`.
- El workflow prepara binarios FFmpeg/FFprobe *únicamente en la carpeta de prueba* (sin publicar artefactos), commit `f9ee167`.
- El smoke limpia el PATH del proceso Companion de directorios que pudieran contener FFmpeg instalado; obliga a usar herramientas del paquete. Commit `f59d531`.

**Resultado de esta segunda fase:** pendiente de comprobar el CI del commit `f59d531b70bd13a56f556fa7bc6e6f530d3a36d5`. No extrapolar un éxito antes de ver ese resultado.

## Decisiones pendientes antes de entregar al usuario

1. Comprobar de forma reproducible que el EXE encuentra realmente las dos herramientas embebidas, sin FFmpeg instalado en el PC destinatario.
2. Definir procedencia y obligaciones de licencia de binarios FFmpeg/FFprobe — el build local reporta FFmpeg 9.0.1 essentials de gyan.dev. No redistribuir automáticamente binarios ajenos sin revisión de su licencia/configuración y sus avisos.
3. Convertir el prototipo PowerShell W3K a un lanzador mantenible, con procesos hijos cerrados correctamente y sin consola; validación de antivirus/SmartScreen y firma de código después.
4. Probar en máquina Windows limpia y con usuario final; PR requiere revisión JM, CI y acuerdo explícito para merge.

**Política:** no producción, no servicios JM, no publicar paquetes como releases.


## Seguimiento de CI de FFmpeg embebido (05-11)

- Commit `f59d531`: intento de copiar el ejecutable FFmpeg resuelto en PATH. **FAIL** del CI porque la ruta apuntaba a un *shim* de Chocolatey, cuya ruta relativa deja de ser válida al copiarlo.
- Commit `955f0a2`: localizar el ejecutable verdadero dentro del paquete Chocolatey. El primer parche produjo un YAML truncado; se reemplazó por un YAML completo y verificado en `ad14ae0`. La prueba de empaquetado llegó a copiar y ejecutar FFmpeg 9.0.2, pero falló la verificación del código de salida al canalizar `-version` a `Select-Object -First 1`.
- Commit `b956b56`: recoge primero toda la salida de `-version` y solo después muestra la primera línea. CI Windows [41932220683](https://github.com/amehcgracia-byte/Montara/actions/runs/41932220683) **aún en ejecución en última consulta**. No afirmar PASS de FFmpeg empaquetado sin `WINDOWS_PACKAGED_SMOKE_PASS`.

**Licencia pendiente:** el mantenedor de los binarios Gyan declara todos los builds estáticos de su web **GPLv3**; FFmpeg diferencia licencia LGPL por defecto de componentes GPL opcionales. Antes de redistribuir el ZIP/instalador deberá evaluarse el conjunto concreto de componentes, obligaciones de código fuente, créditos y avisos legales con revisión jurídica. Fuentes: https://www.gyan.dev/ffmpeg/builds/ y https://ffmpeg.org/legal.html. El CI copia binarios solo para prueba, **no los publica**.
