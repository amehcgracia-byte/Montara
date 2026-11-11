# SMART — Navegación contextual tras feedback humano (11/11/2026)

Fernando confirmó que la entrada autenticada y selector All/Video/Music funcionan, pero detectó: (1) Back desde Video/Music conservaba el ámbito antiguo; (2) hacer clic en Stage abría obligatoriamente el panel de proyectos en lugar de Stage; (3) el diálogo salía arriba a la izquierda.

## Corrección
- `urano/owner_mode_entry.py`: `choices('root')` restaura `All projects`. Stage consulta proyectos propios `GET /urano/v1/editor/projects?mode=stage` y abre directamente el Stage más reciente (catálogo ordenado por `updated_at DESC`) mediante el editor auténtico de Chema. **Si no hay proyectos Stage**, abre el diálogo contextual para crear el primero, sin crear borradores silenciosos ni duplicados. La apertura de uno existente conserva `?resume=footage`.
- `urano/owner_project_picker.css`: modal nativo `dialog` centrado con `position:fixed;inset:0;margin:auto` para evitar posicionamiento heredado del CSS Chema.
- Prueba en `tests/test_owner_mode_entry.py` verifica ámbitos y ruta Stage sin abrir popup forzado. Total: **12 PASS Python +14 subpruebas**, JS parse PASS.
- Beta GCP desplegada con respaldo `~/.config/montara-owner-beta/rollback-stage-entry-dialog-20261111`. Gate pública: health 200, entry visitante 401, Google start 302.
- No se ha modificado `main`, Engine, broker, Companion, proyectos ni originales.

## Límite explícito
**La recuperación de proyectos distintos del que tiene el worker activo sigue bloqueada por BusyOwner.** El acceso directo al último proyecto no equivale a cierre seguro ni a reparación de la recuperación. No detener automáticamente un render/trabajo hasta disponer de una comprobación confiable de inactividad. Falta validación visual del diálogo centrado y del nuevo Stage directo.
