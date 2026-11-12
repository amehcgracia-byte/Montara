# SMART — Gate funcional tras fallo humano de cargas (11-11-2026)

## Decisión
Detener el avance hacia exportación/MP4 hasta resolver la primera transferencia real desde Companion; no repetir laboratorios de pasos posteriores ni cambiar Engine por el nuevo pin para intentar ocultar el fallo.

## Evidencia humana
- Todos los vídeos/audios probaron errores de transferencia; la etiqueta de vídeo decía únicamente `Transfer failed`, sin contexto. El indicador Engine quedaba ámbar y el botón off indicaba busy.
- No está verificado que Companion fallara: el procesamiento local y creación de derivados ya se observaron. El rechazo anterior `invalid_media_name` viene del gate de Owner, pero el nombre visible del archivo satisface las reglas y su causa exacta no se conoce.

## Auditoría read-only real
- Portal, túnel y root broker activos.
- Ledger del broker tenía dos unidades worker en estado `running`, ambas systemd `active`, y un job previo `orphaned`. `running` del ledger significa worker residente, **no demuestra** render en curso; no se han cerrado ni alterado.
- El botón Off consultaba el `wizard/status` de Chema y trataba todo valor distinto de `idle` como Engine `busy`. Ese estado corresponde al flujo de edición, no necesariamente al sistema de procesos. Parada manual mediante broker no es atómica frente a nuevos trabajos; no hacer stops ciegos.
- El CSS Owner había añadido un pseudotexto fijo `Transfer failed` que tapaba deliberadamente `f.error` y ocultaba diagnósticos del editor.

## Corrección focalizada desplegada
- `urano/original_jm_owner_assets.py`: en el piloto Owner sirve una variante en memoria del archivo inmutable de Chema `montara.js` que antepone `f.kind==='error'` a `f.small` y muestra `escapeHtml(f.error)`. El original en disco permanece intacto.
- `urano/owner_project_picker.css`: elimina el pseudotexto que tapaba el error real; el texto rojo ya no oculta el motivo.
- `urano/owner_project_picker.js`: conserva LED verde después de admisión verificada aunque el editor esté ocupado; amarillo solo cuando el worker no se pudo verificar o tras intento de parada de resultado incierto. Describe la restricción del editor sin afirmar que el Engine entero renderiza.
- 33 pruebas Python PASS, 35 subtests PASS, 2 JS PASS; beta health 200, entrada anónima 401, OAuth start 302, broker sigue activo. Rollback `~/.config/montara-owner-beta/rollback-real-errors-engine-state-20261111/`.

## Bloqueos pendientes
1. Obtener causa auténtica de rechazo de vídeo/audio en el entorno autenticado; el error original de Chema vuelve a estar visible. Sin subidas adicionales innecesarias.
2. Verificar el contrato real de `X-Zucker-Filename`, bytes de proxy y CSRF/generación en un caso reproducible (sin registrar nombres ni datos personales).
3. El bundle audio lossless actualizado con cuota 2 GiB está preparado, probado y **NO activado**. No sustituir root broker con workers residentes activos.
4. Arbitraje de estado del Engine debe ser atómico en el broker, no depender de `wizard/status` del editor. No pulsar OFF para intentar destrabar cargas.
5. Solo después de una transferencia aceptada: Stage sync, revisión, receta Companion y MP4 local.

## Regla de desarrollo
No continuar con nuevos hitos visuales o render tests aislados hasta cerrar el gate de carga end-to-end en la beta real.