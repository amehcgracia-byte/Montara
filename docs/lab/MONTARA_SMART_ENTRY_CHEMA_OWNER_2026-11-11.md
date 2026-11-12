# MONTARA SMART — Entrada auténtica de Chema y regreso al flujo Stage

**11 noviembre 2026 · rama `fernando/integracion` · beta privada GCP activa; `main` y rama JM de Chema intactas.**

## Motivo y decisión anterior recuperada

`docs/lab/MONTARA_PRODUCT_DECISIONS_AND_HANDOFF_2026-11-10.md` y
`docs/lab/MONTARA_EDITOR_PRODUCT_UX_AND_LOCAL_STORAGE_DECISIONS_2026-11-11.md`
ya decidían que el dashboard I27/I28 es provisional; tras Google debe verse la selección original de Chema, sin botón de Engine, y que el selector de proyectos debe ser contextual.

El portal SMART anterior aún redirigía desde `/` y el callback Google a `/urano/v1/dashboard`, aunque ya tenía el editor JM privado. Esta entrega corrige **solo esa divergencia de entrada**; no repite I30–I59 ni reconstruye Companion.

## Cambios publicados en la beta

- `urano/owner_mode_entry.py`: adapta en lectura **la cabecera y el bloque de selección de modos del propio `web/index.html` pinneado de Chema**; CSS/logo originales, autorización por sesión Owner, assets exactos, sin otro editor ni rutas globales de Engine. Si cambian los anclajes originales, falla explícitamente.
- `urano/minimal_owner_api.py`: en piloto JM autenticado, callback OAuth hacia `/urano/v1/entry`; modo no piloto conserva su destino previo.
- `urano/owner_beta_wsgi.py`: raíz y acceso de sesión existente hacia entry **solo** si `MONTARA_JM_EDITOR_PILOT=private`. El dashboard anterior permanece accesible para reversión.
- Entrada: selector original Music/Video → Stage/Push/Show. Stage muestra solo proyectos propios existentes mediante `GET /urano/v1/editor/projects?mode=stage`; crear uno requiere acción explícita, título y `POST /urano/v1/editor/projects` autorizado con CSRF. No se crea proyecto ni arranca Engine al entrar. Push/Show/audio aparecen, pero se informa que el recorrido Owner de esos modos aún no está integrado; no inventar compatibilidad.
- `urano/owner_browser_bridge.js`: en **nuevos Stage** abiertos con `?start=stage`, tras cargar los scripts originales se activa una vez el itinerario original de Chema hasta Footage. La apertura de proyectos existentes **no** añade ese parámetro, para preservar la recuperación nativa sin resetear su estado.

## Verificaciones realizadas

- VM: módulo Python compilado y JavaScript `node --check` PASS.
- Test real Flask con base HTTPS, sesión aislada y bundle original JM inmutable: `/entry` sin sesión 401, con sesión 200, bloque original de tres modos presente, CSS/logo 200, asset no autorizado 404, origen extranjero 403.
- `tests/test_owner_mode_entry.py`: **3 PASS** (login, assets protegidos, incompatibilidad del HTML fail-closed).
- `tests/test_owner_browser_bridge.cjs` y `tests/test_owner_review_bridge.cjs`: **2 PASS**.
- Tras desplegar únicamente tres archivos iniciales más dos ajustes puntuales en el portal SMART y reiniciarlo: Cloudflare `/healthz` **200**, `/urano/v1/entry` sin sesión **401**, inicio Google OAuth **302**.
- Se conservan copias reversibles en `~/.config/montara-owner-beta/rollback-entry-20261111-1630` y `~/.config/montara-owner-beta/rollback-entry-stage-20261111`; root broker, túnel, bundles, bases SQLite, originales Windows y servicios de Chema **no modificados**.

## Alcance NO validado todavía

No hay todavía PASS humano de `Google → entry → crear/reabrir Stage → Footage` en Windows. El disparador `?start=stage` tiene pruebas de sintaxis/regresión del puente pero aún no una prueba visual en el navegador humano. Tampoco se ha completado el E2E Owner Stage con proxies de Companion y MP4 final.

El encabezado y selector contextual de proyectos **dentro del editor** siguen siendo una integración de UX pendiente; la entrada inicial reutiliza el HTML real pero todavía es una cubierta mínima. No atribuirla a Chema como cambio suyo.

## Siguiente comprobación SMART

Fernando abre `https://montara-owner.memoriainvalida001.workers.dev/` con su sesión Google existente; debería ver el selector original de modalidades, elegir **Video → Stage**, ver sus proyectos privados y crear o recuperar uno. En un Stage nuevo debería abrir **Footage** del editor original. Si pasa, comprobar detección de Companion `127.0.0.1:47820`, archivo proxy corto y autorización de subida; reparar **solo** el error observado hasta MP4 local. Tras PASS humano integral, preparar PRs pequeños hacia `main`, no fusionar la rama histórica íntegra.
