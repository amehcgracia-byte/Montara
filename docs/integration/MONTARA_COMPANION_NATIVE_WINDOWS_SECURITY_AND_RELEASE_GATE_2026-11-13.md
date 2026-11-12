# MONTARA — Companion Windows: distribución nativa y actualización segura

**Fecha:** 2026-11-13 · **Rama:** `fernando/chema-native-owner` · **Estado:** implementación preliminar, **NO instalable/distribuible aún**.

## Decisión

La distribución anterior `companion/beta_windows/*.ps1` queda **retirada**. Windows Defender bloqueó `bootstrap (1).zip` como `Trojan:Script/Wacatac.B!ml` el 13/11/2026. No se ha demostrado si era una detección falsa; **no** aconsejar al usuario restaurarlo, forzar la descarga, deshabilitar Defender ni añadir exclusiones.

El endpoint H4 `/urano/v1/companion-updates/*` permanece desactivado: `bootstrap.zip` público responde **404**. Sus antiguos ZIP siguen conservados únicamente para auditoría técnica interna de los desarrolladores. No redistribuirlos. Los scripts de prueba de esa carpeta quedan excluidos de cualquier release.

Se adopta la dirección **controlador nativo Windows**, sin Powershell, con **instalador firmado y actualización explícita bajo demanda del usuario**:

- **Aplicación:** .NET 8 WinForms, icono de bandeja, estado del servicio, configuración de la instancia local existente, inicio manual y cierre del controlador sin matar render activo.
- **Engine:** mantener originales, proyectos, carpetas, cachés y motor locales; no copiar ni reinstalar FFmpeg/Engine en una simple actualización del controlador. Más adelante, generar paquetes de runtime compatibles, con migración y pruebas independientes.
- **Actualización:** canal dedicado HTTPS estático, manifiesto/release versionado, **paquete firmado con identidad de editor confiable** y verificación por el instalador del sistema operativo. La descarga del instalador y el cierre/reinicio deben esperar al final del render; ninguna actualización periódica ni silenciosa.
- **Distribución:** preferencia inicial MSIX/App Installer si la identidad y el acceso a recursos locales del proceso full-trust son compatibles en Windows 10 22H2. De no serlo, MSI firmado y un updater que verifique la cadena Authenticode y el editor antes de ejecutar. **No** inventar un descargador propio que ejecuta bytes del servidor.

## Trabajo realizado

Archivos nuevos:
- `companion/windows_native/Montara.Companion.csproj`: programa Windows nativo, no script.
- `companion/windows_native/app.manifest`: privilegios `asInvoker`; no exige elevación.
- `companion/windows_native/Program.cs`: menú de bandeja, consulta local `127.0.0.1:47820/health`, configuración por selectores de archivos, ejecución de la instancia seleccionada, no mata procesos al cerrar la bandeja.
- `.github/workflows/companion-native-windows-ci.yml`: compilación Windows en rama FER. **No** publica archivos compilados ni realiza distribución sin firma.

La opción `Buscar actualizaciones...` está **bloqueada de manera segura** hasta disponer de un release firmado. El controlador es un **prototipo técnico**, no una nueva instalación para el usuario.

## Condiciones de seguridad para abrir el canal

1. Definir identidad del editor (persona/empresa) y disponer de firma válida de distribución; comprobar elegibilidad y coste de Microsoft Artifact Signing o alternativa CA/Store. Nunca subir claves privadas al repositorio.
2. Compilar en Windows desde commit inmutable y dependencias fijadas. Conservar SBOM, provenance y SHA-256 por artefacto; no permitir sobreescritura del paquete por un JSON público.
3. Firmar instalador y binarios según el mecanismo elegido, incluido timestamp. Comprobar firma y origen real en un Windows limpio.
4. Ensayar instalación sobre el Companion actual: conservar carpetas, originales, engine, jobs y configuración; restauración de versión anterior y ausencia de elevación innecesaria.
5. Ensayar actualización manual mientras (a) no hay render, (b) hay render activo: en (b) bloquear actualización; reinicio de controlador y servicio al finalizar únicamente cuando se solicite.
6. Validar Windows Defender/SmartScreen de forma legítima. Si hay detección, analizar y presentar muestra al proveedor; **no** modificar el código con objetivo de evadir detección.
7. Solo entonces abrir un canal estable de versión firmada y habilitar `Buscar actualizaciones` funcional. No reutilizar el ZIP de PowerShell.

## Compatibilidad

- Windows 10 22H2 del usuario, arquitectura x64, PC Intel i5/8GB, restricciones de CPU/RAM.
- Companion actual y el runtime local de Engine se encuentran fuera del instalador nuevo. Los nuevos ejecutables **no deben** eliminar ni mover estos directorios.
- Antes de instalar una app empacada mediante MSIX, verificar compatibilidad de acceso a ficheros y loopback localhost al interactuar con el Companion Python existente.
- La calidad final sigue dependiendo de `engine`, los originales y la receta, **no** del tipo de instalador.

## Render actualmente bloqueado

La incidencia humana real del primer MP4 (`WinError 5` al sustituir `progress.json`) se corrigió con una política de reintentos específicos en `companion/local_video.py`, protegida por `tests/test_companion_windows_render_progress.py` (4 pruebas PASS). **Ese parche sigue solo en la rama de desarrollo**, no está instalado en el Windows del usuario. No pedirle que reintente el render en la versión antigua como si estuviera corregida.

## Próximas entregas acotadas

- **Gate A:** compilar el tray en runner Windows y corregir errores de build. No distribuir unsigned.
- **Gate B:** elegir y montar paquete firmado (MSIX o MSI), versión y rollback; necesita identidad real de publicación.
- **Gate C:** empaquetar y verificar patch del render `WinError 5` con el Companion instalado en Windows, respetando los originales y dependencia del Engine.
- **Gate D:** primera validación humana: estado, actualización manual, relanzamiento, render Stage y MP4 final.

## Fuentes

- Microsoft, *Packaging overview*: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/packaging/
- Microsoft, *Sign an MSIX package*: https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview
- Microsoft, *Troubleshoot App Installer*: https://learn.microsoft.com/en-us/windows/msix/app-installer/troubleshoot-appinstaller-issues
- Microsoft, *App Installer file overview*: https://github.com/microsoftdocs/msix-docs/blob/main/msix-src/app-installer/app-installer-file-overview.md

El prototipo todavía no tiene firma, ni instalador distribuible, ni verificación ejecutada en el Windows del usuario. No confundir compilación sintáctica con validación humana real.
