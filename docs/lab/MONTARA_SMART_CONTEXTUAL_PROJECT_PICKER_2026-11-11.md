# SMART — Selector contextual de proyectos en la beta Owner (11/11/2026)

## Decisión de producto validada con Fernando y Chema
No crear una pantalla independiente obligatoria para proyectos. Usar el header del editor original, con selector contextual en diálogo: All projects (inicio), Video projects (Video), Music projects (Music), Stage projects (Stage), y posteriormente Push/Show. Destacar último proyecto y permitir búsqueda y creación donde corresponda.

## Implementación
- `urano/owner_project_picker.js` y `.css`: componente externo compartido, sin reescribir JS/HTML original de Chema, sin catálogo duplicado. Solo APIs `GET /urano/v1/projects`, `POST /urano/v1/editor/projects` y `POST /urano/v1/session/refresh`. Todos operan con la sesión Google y las comprobaciones CSRF existentes.
- `urano/owner_mode_entry.py`: Stage abre el diálogo en la misma pantalla en lugar de mostrar el catálogo provisional separado. El diálogo contextual usa la cabecera original; CSS/JS privados se sirven solo a sesiones autenticadas.
- `urano/original_jm_owner_assets.py`: inyección separable del mismo JS/CSS desde el pilot Owner dentro del editor original. No se altera `web/index.html` de Chema ni sus subfases, Engine/Mixer.
- Stage existente se abre con `?resume=footage` y nuevo con `?start=stage`. No se genera proyecto ni arranca Engine al mostrar el popup. No se expone ningún archivo original.
- Las modalidades Music / Push / Show solo disponen por ahora de selector contextual y filtrado; abrir/crear fuera de Stage avisa que no está integrado. Los proyectos legados sin modo están etiquetados como Legacy. No se inventa clasificación de Music inexistente en el catálogo actual.
- Al cambiar entre proyectos se respeta la protección de un worker activo por propietario: **no se detiene ningún worker automáticamente**. El bloqueador BusyOwner está verificado en la beta actual, pendiente de solución con comprobación explícita de inactividad y autorización de cierre seguro.

## Validación
- `node --check urano/owner_project_picker.js` PASS, Python compile de las dos rutas PASS.
- `pytest tests/test_owner_mode_entry.py tests/test_urano_editor_project_bridge.py --import-mode=importlib`: **11 PASS, 14 subpruebas**.
- `node --test tests/test_owner_browser_bridge.cjs tests/test_owner_stage_resume.cjs`: **2 PASS**.
- Tras despliegue SMART en GCP: `/healthz=200`, `/urano/v1/entry` anónimo `401`, `/urano/v1/entry/picker.js` anónimo `401`, inicio Google `302`. Rollback: `~/.config/montara-owner-beta/rollback-contextual-picker-20261111/`. No se modificó main, la VM de Chema, Engine/Mixer, bases SQLite ni Companion Windows.
- **Pendiente validación humana**: comprobar visualmente popup en entrada Video/Music y dentro de Stage; no afirmar PASS visual ni cambio seguro de proyecto.

## Próxima prioridad
1. Validación humana del panel flotante.
2. Resolver BusyOwner: inspección segura del estado del worker previo, cierre solo si realmente inactivo y sin render pendiente, y con ruta de rechazo visible/persistente si está ocupado. No detener trabajos existentes como una migración tácita.
3. Completar Companion Windows → Stage → MP4 local con la base `main` sincronizada y preparar PRs pequeños para Chema.
