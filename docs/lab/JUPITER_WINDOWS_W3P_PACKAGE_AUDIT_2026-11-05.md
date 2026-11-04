# JÚPITER · W3P · Auditoría del paquete portátil de laboratorio

Fecha: 2026-11-05. Alcance: rama `fernando/companion-windows-w1`, [PR #74](https://github.com/amehcgracia-byte/Montara/pull/74) draft. No publicar paquetes ni modificar producción.

## Meta

Convertir los componentes W3L–W3O en **una carpeta portable verificable**, que pueda examinarse antes de entregar un paquete de aceptación al usuario. Esta etapa **no** pretende superar por sí sola las obligaciones de redistribución de FFmpeg ni garantizar compatibilidad con cualquier PC.

## Implementado

- `tests/windows_companion_package_audit.py` (`03e9490`): valida archivos críticos `MontaraCompanion.exe`, `windows_tray.ps1`, `bin/ffmpeg.exe` y `bin/ffprobe.exe`, además de las librerías `_internal` de PyInstaller. Rechaza logs y vídeos MP4 en la carpeta de distribución. Genera `W3P-package-audit.json` **fuera** de la carpeta final, con inventario, número de archivos, bytes y SHA-256 para cada fichero.
- Workflow Windows (`0c2fde3`): copia el lanzador de bandeja versionado junto al EXE y ejecuta la auditoría **antes** de los smoke tests existentes de procesos, FFmpeg y API/proxy.
- El manifiesto marca `redistribution_authorized: false` y `requires_license_review: true`. El workflow no contiene `upload-artifact`, publish, release o merge.

## Riesgos pendientes

1. **Licencias:** determinar configuración/licencia de los FFmpeg/FFprobe a incluir, textos legales, fuente correspondiente y permisos de distribución. Los binarios de Gyan usados en pruebas no deben ser republicados automáticamente.
2. **Aceptación Windows:** probar el menú real de bandeja y la salida del EXE empaquetado con una sola prueba local guiada, después de superar CI.
3. **Seguridad/distribución:** firma, SmartScreen, antivirus, procedencia de binarios, actualizaciones y posibles conflictos de puertos/instancias.
4. **Cierre de ciclo:** revisión con JM, decidir qué queda para URANO y qué pasa a backlog del producto; PR #74 sin merge no entra en el producto principal.

## Estado

CI [41934811721](https://github.com/amehcgracia-byte/Montara/actions/runs/41934811721) **pendiente** en la primera consulta. No declarar W3P PASS antes de comprobar `W3P_PACKAGE_AUDIT_PASS` y que la ejecución completa termina en verde.

## Resultado del CI

**W3P AUDIT PASS**: [run 41934811721](https://github.com/amehcgracia-byte/Montara/actions/runs/41934811721) se completó con conclusión **success** para el commit `0c2fde3a4d06e89489b0fc10376966e610c999f8`. Los pasos de preparación/auditoría del paquete, parser del lanzador, terminación de árboles con FFmpeg activo y API/proxy empaquetado terminaron correctamente. **No** se publicó ningún artefacto ni binario. El resultado cubre los contenidos de la carpeta temporal de GitHub, no una entrega instalada por un usuario.
