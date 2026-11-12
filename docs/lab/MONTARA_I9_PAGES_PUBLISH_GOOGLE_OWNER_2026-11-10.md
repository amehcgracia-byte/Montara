# I9 — Publicar la portada integrada sin exponer el editor anterior

**Fecha:** 2026-11-10. **Base:** `fernando/integracion@1c44845`. **Objetivo:** que `montara-beta-preview.pages.dev` envíe a testers al Owner privado real, sin activar email/password ni el Engine global.

## Fuente, build y despliegue

Cloudflare Pages `montara-beta-preview` ya está conectado a GitHub `amehcgracia-byte/Montara`, pero su rama de producción inicial era `fernando/c8-public-beta-landing-pages-20261110`. La portada actualizada se integró en I7 sobre `fernando/integracion`. El script histórico de build exigía el botón Google `disabled`, por lo que **no se debe cambiar Pages a la rama de integración sin actualizar primero su script**.

`tools/cloudflare-beta/build.py` en esta PR solo copia `index.html` y `_headers` a `dist/`, exige al menos dos enlaces HTTPS exactos al Owner público, bloquea destinos externos distintos del Owner, formulario público y enlaces al editor clásico, y exige Content Security Policy. No hay acceso a secretos ni uploads. Los dos tests adicionales comprueban build y protección de sobrescritura; no prueban Google interactivo.

**Operación de Cloudflare posterior a CI:** configurar producción Pages desde `fernando/integracion` (o publicar este artefacto auditado en proyecto dedicado) y verificar que el build `python3 tools/cloudflare-beta/build.py` produce `dist`; comprobar estado y URL HTTPS real. No borrar ramas históricas.

## Recorrido esperado de esta primera integración

1. `https://montara-beta-preview.pages.dev/` (público estático) → botón Google.
2. `https://montara-owner.memoriainvalida001.workers.dev/` (portal privado) → redirect `/urano/v1/google/start` → Google real.
3. Con sesión Google válida, `/urano/v1/dashboard`: crear, listar y recuperar proyectos; sin sesión 401 en dashboard/API.
4. **Pendiente:** email/password verificado y propietario canónico I8, selector/futura UX, workspace Engine aislado I5B, Companion descargable desde release firmada y primer E2E físico. NO forzar acceso al editor viejo 8101–8103/8114 para fingir un recorrido completo.

**No publicar de forma engañosa un botón Companion si no existe instalador verificado por plataforma.** El enlace de Google sí debe funcionar para las cuentas de beta autorizadas.

## Seguridad

La build no incluye scripts dinámicos ni endpoints Cloudflare API. VPC Service/Tunnel, OAuth callback, datos de propietarios, códigos de Chema y `main` quedan intactos. El cambio de producción Pages será una operación de configuración del proyecto FER; verificarla por separado y no confundir el test de página con un login real.
