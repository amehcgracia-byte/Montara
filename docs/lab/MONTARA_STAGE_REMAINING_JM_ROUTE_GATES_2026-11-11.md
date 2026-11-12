# MONTARA — Rutas originales JM que faltan tras I54–I56

**Fecha:** 2026-11-11 · **Rama:** `fernando/integracion`. **Inventario parcial de llamadas literales de `web/montara.js` y `web/cut-editor.js`** en la rama JM `fix/jm-native-video-save-project-recovery-20261110` (`14cce126...`). NO constituye un inventario exhaustivo de rutas generadas dinámicamente ni una autorización para exponerlas.

## Gate A — Stage ingest: cubierto parcialmente

Ya revisados en `owner_original_jm_rpc.py`: `POST /api/v1/wizard/upload`, `POST /api/v1/wizard/projects/new`, `POST /api/v1/wizard/draft`, `GET /api/v1/wizard/status`, `GET /api/v1/project`, `POST /montara/branding`, `GET/POST/PUT/DELETE /montara/uploads[/*]`. El adaptador de navegador es opt-in, bloquea por defecto lo demás. La subida normal es Companion proxy, original solo fallback voluntario.

**Todavía faltan:** respuestas/recuperación de estados completos por Owner, guardar rutas/recetas y política de generación por pestaña. La prueba original de JM no equivale a Google OAuth browser E2E.

## Gate B — Navegación, Companion y vista previa

Rutas originales observadas: `GET /montara/version`, `GET /montara/companion/version`, `GET /montara/branding`, `GET/POST /montara/logo`, `GET /montara/samples?platform=...&variant=...`, `GET /montara/audio?path=...`, `GET /api/v1/wizard/review/preview/<index>?...`, `GET /api/v1/wizard/spherical-source-frame?source=...`, `GET /api/v1/wizard/spherical-preview?...`, `GET /api/v1/wizard/compose-base?... `.

**Riesgo específico:** peticiones `path`/`source`/índices/URLs no pueden enviarse sin revalidar que el medio pertenece al Owner y al mismo proyecto; no basta con regex de endpoint. Las respuestas grandes requieren streaming acotado; manejar Range/HEAD/Content-Range de forma revisada. `/montara/version` podría servirse desde manifiesto **sin arrancar Engine**, pero no afirmar que ya está construido.

## Gate C — Audio, edición y render

Rutas observadas: `/montara/master`, `/montara/master/<job>`, `/montara/master/<job>/result`, `/montara/mix`, `/montara/mix/<job>`, `/montara/mix/<job>/track/<file>`, `/montara/mix/<job>/fx/<fx>/<file>`, `/montara/mix/<job>/reference[/link]`, `/montara/mix/<job>/render`, `/montara/mix/<job>/result`, `/api/v1/edit/native-source/<key>?revision=...&project_id=...`, `/api/v1/edit/native-master?...`, `/api/v1/wizard/result`.

**No abrir un proxy genérico**: cada operación debe verificar HTTP método, sesión + CSRF + Owner UUID, generación activa y permisos por recurso, y preservar la posibilidad de que Companion haga el render final local. Los jobs Master/Mix tienen IDs distintos del UUID Owner y deben mapearse de forma autoritativa.

## Gate D — Push / Show

Observadas `/api/v1/show/source?path=...`, `/montara/show/sample`, `/montara/show/direction`, `/montara/show/editor`, `/montara/show/cuts`, `/montara/show/examples`. No reutilizar sin revisión los permisos Stage. Son contratos independientes y podrán conectarse después de Stage E2E.

## Orden propuesto para salir de la etapa 5

1. Crear y verificar bundle JM nuevo con **Engine `b867b3c...`** y Mixer `f15ff91...` de la misma rama JM; el Engine antiguo `b5e4831...` tiene 19 commits menos, incluido export/recovery.
2. Activar rutas read-only de assets/version y previsualización Stage con parámetros validados y pruebas de recursos ajenos; preservar Editor JM original.
3. Añadir operaciones Stage sincronización/edición y la receta de exportación que consume Companion, reutilizando el E2E `tests/e2e_native_stage.py`; evitar protocolos multimedia nuevos.
4. Verificar `systemd DynamicUser`, cuotas agregadas y retención, recuperación con dos propietarios y Google OAuth real en beta privada.
5. Fernando prueba un proyecto **Stage** con su Companion Windows y MP4 final. Luego ampliar Push y Show. No pedir prueba humana por otro laboratorio de apertura de Engine.

**Situación de infraestructura al redactar:** GCP SSH no respondía; Oracle y GitHub estaban accesibles; se utilizaron copias temporales, sin despliegue ni reinicio de servicios.
