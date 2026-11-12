# SMART — Sincronización de main y recuperación Stage privada (11-11-2026)

## Base nueva de trabajo

- Chema actualizó `main` a `5d65ec3538723b154cdac3efb6942def8c389200` (+83 commits desde `765a34c`).
- Merge de `main` **hacia `fernando/integracion`** en PR #210, commit `0a07bb2d114f1f2f8970c6e988f845e0b3ec80e2`. Confirmación posterior: `behind main = 0`, `ahead main = 305` en ese momento, sin modificar `main`.
- La fusión temporal fue limpia (44 archivos, 0 conflictos); antes de publicar se probaron 17 tests Node y 12 Python (+29 subpruebas). Un intento Python inicial falló por resolución de import `companion` al cargar toda la suite; la corrida focal corregida con `--import-mode=importlib` sí pasó.
- **Compatibilidad de runtime no inferida de la fusión:** gitlink Engine nuevo `92c7bc33f59baae92a8d61e5dd4bf0ce9685d79e`; la beta/Companion Windows probados siguen fijados al Engine `b867b3c...` y editor JM `14cce126...`. Mixer sigue `f15ff91...`. Requiere un bundle manifest revisado y pruebas originales Stage/Companion antes de sustituir el runtime. No actualizar `main` en sentido inverso ni desplegar Engine nuevo sin revisión.

## Problema observado por Fernando

Tras login Google, la entrada Stage y Footage funcionan; al seleccionar un proyecto Stage existente, el editor original podía volver a Home/Mode. El código de Chema soporta `?resume=footage` y consulta el proyecto persistido mediante `status()` y `project()`, pero la entrada Owner abría sin hint; la petición inicial carecía del token de generación de un worker privado que aún no estaba activo.

## Corrección mínima reutilizando la recuperación nativa

1. `urano/owner_mode_entry.py`: Stage existente se abre con `?resume=footage`, mientras Stage recién creado conserva `?start=stage`. Sin segunda pantalla ni catálogo nuevo.
2. `urano/owner_browser_bridge.js`: **únicamente** si la página tiene `resume=footage`, la primera lectura `GET wizard/status` hace `ensure()` idempotente por Owner UUID. Reenvía al gateway privado, sustituyendo el path legado por `project_id=owner-worker`. No se inicia Engine al visitar la portada ni para GET ordinarios.
3. La ruta final depende todavía de la recuperación genuina en `web/montara.js` y del estado efectivo del proyecto: no afirmar que una sesión sin multimedia recupere una fase inexistente.

## Pruebas y publicación

- `tests/test_owner_stage_resume.cjs`: PASS: recuperación activa worker una sola vez; navegación normal y Stage nuevo no lo hacen; las rutas se quedan ligadas al Owner y no revelan rutas físicas.
- Regresiones existentes `test_owner_browser_bridge.cjs`, `test_owner_review_bridge.cjs`: PASS (3/3 Node combinadas).
- `test_owner_mode_entry.py` + `test_urano_editor_project_bridge.py`: **9 PASS y 14 subpruebas**.
- Beta GCP reiniciada con copia de ambos archivos en `~/.config/montara-owner-beta/rollback-stage-resume-20261111`: health 200, entry sin sesión 401, inicio OAuth 302; túnel/broker active. Bases privadas, originales Windows, servicios JM globales y paquetes inmutables sin modificar.
- **Pendiente PASS humano:** abrir desde Mis proyectos un Stage anterior con progreso y comprobar si regresa a Footage/Review. No hay aún render Owner+Companion+MP4 en Windows probado.

## A continuación, sin duplicar URANO

Verificar físicamente recuperación con un Stage existente; luego comprobar proxy real del Companion Windows y completar exportación local. Por separado, reconstruir bundle inmutable del nuevo `main` con Engine `92c7bc3`/Mixer adecuado, contrastar nuevas rutas de Stage y versión/receta Companion; migrar beta de forma reversible solo cuando esté probado. El menú contextual `Mis proyectos` por Stage/Push/Show se integrará dentro de los assets originales y sin nuevas pantallas intermedias.
