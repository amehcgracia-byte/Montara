# MONTARA SMART — Stage directo, sin recuperación innecesaria (11/11/2026)

## Incidencia humana
Fernando confirmó Back/All projects y modal centrado. Al pulsar Stage, la beta mostraba brevemente «Opening your edit…» y volvía a la pantalla de inicio original de Chema, sin el selector Owner visible.

## Hallazgo verificado
- La entrada de Stage usaba `?resume=footage` para el último proyecto, aun cuando el proyecto estaba vacío.
- Lectura estrictamente read-only del `project.json` persistente, mediante VM autorizada: **cero vídeos, sin master/songs, sin configuración wizard**. Se comprobó que el worker privado estaba activo y que `GET /api/v1/wizard/status` directamente por socket privado devolvía HTTP 200, `status=idle` y `project_path` presente. No se reprodujo mediante navegador la causa completa del retorno al inicio; no atribuir el fallo a una caída de red.
- El código original `web/montara.js` muestra «Opening your edit…» para `?resume=footage`; ante una recuperación que no forma `savedEdit`, cae a `show('home')`. El mensaje no es necesario para iniciar un Stage vacío.
- Chema guarda `montara-open-edit` en `sessionStorage` por pestaña, no por UUID de Owner: el estado temporal de otro proyecto puede interferir en la recuperación o entrada.

## Cambio mínimo en nuestra rama
1. `urano/owner_mode_entry.py`: pulsar la tarjeta Stage abre el último Stage autorizado con `?start=stage`, sin intentar una recuperación de edición en este **flujo de inicio**. El adaptador ya existente usa los clics del editor original para entrar a Footage después del logo de Montara. Se elimina el aviso intermedio `Opening Stage…`. **El selector contextual sigue abriendo un proyecto guardado con `?resume=footage`**, para no descartar trabajo persistente.
2. `urano/owner_browser_bridge.js`: antes de arrancar Chema, traslada `montara-open-edit` a una clave `montara-owner-edit:<uuid>` cuando su proyecto corresponde a un UUID Owner. Al entrar con `?start=stage` limpia solo la copia activa de la pestaña (conservando el snapshot identificado). Al recuperar desde el panel `?resume=footage`, restaura únicamente la copia de ese UUID y nunca la de otro. Sin cambios en bases SQLite ni archivos originales.
3. **Alcance deliberado:** entrar en Stage mediante la tarjeta es entrar en Footage, no necesariamente reabrir la última fase guardada. Para recuperar una edición se selecciona explícitamente desde el panel. Este criterio se podrá revisar después de integrar metadatos duraderos de la última fase en Owner. No se modifica `web/` de Chema.

## Verificaciones
- `node --test`: 5 PASS entre `test_owner_stage_tab_isolation.cjs`, browser bridge, resume, recovery errors y review bridge.
- `pytest`: 12 PASS y 14 subpruebas en entrada y catálogo contextual.
- `node --check`, `py_compile` PASS.
- Despliegue SMART aislado GCP: health 200, visitante entry 401, inicio OAuth 302, broker/túnel activos. Backup `~/.config/montara-owner-beta/rollback-stage-entry-native-footage-20261111`.
- **Pendiente PASS humano** Stage directo hasta Footage y comprobar que persiste la cabecera Owner. No se ha probado exportación ni cambiado Engine/Mixer/Companion. No se ha modificado `main`.

## Siguiente hito
Validar visualmente la tarjeta Stage sin «Opening your edit…» ni vuelta a inicio. Si no funciona, capturar error exacto del bootstrap del editor (sin repetir OAuth/URANO) y resolverlo antes de retomar BusyOwner y MP4 local.
