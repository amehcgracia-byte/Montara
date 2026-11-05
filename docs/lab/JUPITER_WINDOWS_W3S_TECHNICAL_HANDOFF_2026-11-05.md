# JÚPITER — W3S · cierre técnico y traspaso a URANO

**Fecha:** 2026-11-05  
**Proyecto:** MONTARA / JÚPITER · Companion local Windows  
**Rama de código:** `fernando/companion-windows-w1`  
**Revisión:** [PR #74](https://github.com/amehcgracia-byte/Montara/pull/74), **draft / no fusionar automáticamente**  
**Documentación:** rama `fernando/continuacion-montara`  
**Destino:** revisión técnica por JM / Chema y continuidad del diseño URANO.

## Decisión de alcance

El usuario indica que **la parte jurídica de licencias se resolverá más adelante**. Esto no autoriza publicación ni redistribución comercial. Se conserva el diseño actual y el uso de FFmpeg como motor externo: **no se modifica la arquitectura ni se sustituye libx264 por ahora**. Se finaliza el informe de la fase experimental mientras las licencias siguen siendo una puerta de salida pendiente.

## Estado verificado del último commit Windows

Commit técnico `265dfe407463ae4c1fcfd9ba3cc5558d2c85fb82`.

- [Windows packaged smoke 41935447237](https://github.com/amehcgracia-byte/Montara/actions/runs/41935447237): **completed / success**. El workflow construye PyInstaller one-folder en Windows, prepara FFmpeg y FFprobe dentro de `bin/` para las pruebas, audita paquete SHA-256, ejecuta bandeja WinForms con arranque y apagado controlados, comprueba árbol de procesos con FFmpeg activo y genera/entrega proxy HTTP H.264 con BT.709.
- Montara end-to-end (Linux) asociado al mismo commit: **completed / success**, según consulta GitHub al cerrar W3S.
- Aceptación visual en PC Windows del usuario: **PASS 5/5 reportado por el usuario**, con el EXE **W3L previamente compilado** y el lanzador corregido `windows_tray.ps1`. Se confirma: sin consola, icono de bandeja, menú, estado/health y opción Salir con cierre real. La aceptación **no** se hizo sobre el paquete final con FFmpeg integrado.

## Qué se ha conseguido

| Bloque | Evidencia | Resultado |
|---|---|---|
| W3L | EXE Python congelado + FFmpeg y FFprobe con PATH aislado | PASS runner Windows |
| W3M | `stop_process_tree()` Windows, padre + hijo | PASS runner Windows |
| W3N | Terminar árbol con un FFmpeg real activo | PASS runner Windows |
| W3O | `.part` incompleto/corrupto, reintentar, entregar proxy válido | PASS runner Windows |
| W3P | Carpeta de prueba con EXE, binarios, bandeja e inventario SHA-256 | PASS runner Windows |
| W3Q | Lanzador WinForms real automatizado + aceptación visual usuario | PASS automatizado y PASS visual en EXE anterior |

## Advertencias: lo que **NO** equivale a un producto terminado

1. **Licencias:** los binarios de Gyan `essentials` usados en CI son GPLv3. Revisar obligaciones de redistribución, textos, fuentes y relación jurídica Companion/FFmpeg antes de publicar. La licencia comercial de Montara no está resuelta. [Análisis W3R](JUPITER_WINDOWS_W3R_DISTRIBUTION_LICENSE_GATE_2026-11-05.md).
2. **Sin instalador público:** no se han publicado releases, ZIP de distribución ni binarios de terceros como artefactos para descargar. El `--onedir` de CI es temporal.
3. **Compatibilidad no exhaustiva:** falta aceptación local del paquete definitivo, firma de código/SmartScreen, Windows limpio, antivirus, otros perfiles y auditoría de actualizaciones.
4. **Vídeo avanzado no cubierto por estos smoke tests:** HDR real, hardware/GPU, USB/discos externos, Stage/YouTube end-to-end, varias instancias y sesiones de larga duración. Las pruebas cubren principalmente vídeo sintético corto SDR/proxy y cierre de procesos.
5. **Cierre forzado:** `taskkill /T /F` protege de procesos huérfanos en escenarios comprobados, pero no constituye parada elegante ni garantía ante fallos de sistema. La recuperación por clave reconstituye proxies `.part`; no implica recuperación automática de proyectos o renders complejos.
6. **Revisión de JM obligatoria:** no se debe confundir el cierre del laboratorio de FER con aprobación para merge/producción.

## Traspaso propuesto: URANO

- Definir el reparto definitivo entre **web**, **Companion local** y **procesamiento cloud**; quién almacena originales, proxies y proyectos.
- Diseñar autenticación y autorización entre navegador y Companion, conexión local segura, colas, límites de recursos, y separación entre trabajo local y remoto.
- Aclarar el flujo por modos (archivos locales, YouTube, reels, Stage), incluyendo cómo selecciona el usuario la fuente, permisos, privacidad y coste de infraestructura.
- Mantener el laboratorio Windows estable en PR #74 mientras URANO decide la integración; no iniciar migraciones ni cambios destructivos de arquitectura sin revisión de JM.

## Próxima intervención necesaria del usuario

**Ninguna ahora.** Para avanzar en diseño técnico URANO se puede seguir con repositorio y CI. El usuario/organización deberán participar más adelante en: (a) decisión jurídica/comercial de distribución; (b) aceptación del paquete final autorizado; (c) validación de propuesta de arquitectura y costes.

## Criterio de finalización

**W3S, documentación técnica: cerrado** al registrar este informe.  
**JÚPITER, laboratorio de Windows: PASS técnico acotado**; pendientes explícitos del producto permanecen en backlog.  
**Publicación comercial: BLOQUEADA**, no autorizada por estas pruebas.

Referencias adicionales: [W3L](JUPITER_WINDOWS_W3L_PACKAGING_2026-11-05.md) · [W3M](JUPITER_WINDOWS_W3M_PROCESS_LIFECYCLE_2026-11-05.md) · [W3N](JUPITER_WINDOWS_W3N_ACTIVE_FFMPEG_EXIT_2026-11-05.md) · [W3O](JUPITER_WINDOWS_W3O_PARTIAL_RECOVERY_2026-11-05.md) · [W3P](JUPITER_WINDOWS_W3P_PACKAGE_AUDIT_2026-11-05.md) · [W3Q](JUPITER_WINDOWS_W3Q_TRAY_ACCEPTANCE_2026-11-05.md).
