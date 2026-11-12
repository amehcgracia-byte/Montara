# I9 — Cambio operativo de producción Pages al branch de integración

**Fecha:** 2026-11-10. **Operación:** configuración del proyecto Cloudflare Pages **exclusivo de FER**, `montara-beta-preview`, conservando GitHub `amehcgracia-byte/Montara`, builder `python3 tools/cloudflare-beta/build.py`, salida `dist`, URL `https://montara-beta-preview.pages.dev`.

## Antes
- Rama de producción: `fernando/c8-public-beta-landing-pages-20261110`.
- Portada real con botón «Acceso con Google próximamente» deshabilitado.
- Backend Owner público y Google funcionando, pero visitantes de Pages sin enlace activo.

## Cambio
- Rama de producción (Cloudflare API): `fernando/integracion`.
- Builder I9 recuperado y probado: dos recursos estáticos `index.html` y `_headers`, enlaces Google exactos a `https://montara-owner.memoriainvalida001.workers.dev/`, sin formularios ni carga de medios.
- Este commit documental adicional crea un push posterior al cambio de rama para disparar un build de producción conforme a la integración GitHub existente.
- No modificar Worker, VPC Service, túnel, callback OIDC, datos de propietario, GitHub `main`, servicios de Chema ni frontend de Vercel.

## Comprobación exigida
- Cloudflare Pages debe informar de **deployment production success** desde `fernando/integracion`; si no, no afirmar publicación.
- Comprobar HTML público: enlace a Owner y ausencia del antiguo botón deshabilitado.
- Comprobar Owner `/healthz` 200, `/` 303, `/urano/v1/dashboard` 401 sin sesión.
- E2E manual Google con tester autorizado sigue pendiente. Email/password verificado y editor siguen pendientes.

**Rollback:** la rama anterior y su despliegue histórico permanecen; puede restablecerse la rama y recuperar su deployment canónico si se detecta regresión. No borrar recursos de Cloudflare.
