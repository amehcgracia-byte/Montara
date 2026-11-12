# I7 — Portada pública conectada al Owner privado: límite real del recorrido

**Fecha:** 2026-11-10. **Estado:** cambio de código probado en rama aislada, no desplegado en Cloudflare Pages. Fuente selectiva: rama C8 #158, HTML y `_headers` originales. Destino: `fernando/integracion` (no `main`).

## Rutas auditadas en los dos orígenes HTTPS activos

- **Portada** `https://montara-beta-preview.pages.dev/` responde 200, pero la versión publicada aún tiene el botón Google `disabled`, CTA a `#beta`, no es enlace a OAuth. Pages obtiene el contenido de `fernando/c8-public-beta-landing-pages-20261110`, **no de** `fernando/integracion`.
- **Owner** `https://montara-owner.memoriainvalida001.workers.dev/`: GET `/` 303 a `/urano/v1/google/start`; `/healthz` 200. El panel y proyectos devuelven 401 sin sesión. Después de autenticación Google válida, el backend del Owner presenta `/urano/v1/dashboard`, catálogo y creación/recuperación de proyectos. **No se probó login real con un navegador autenticado en esta revisión**.
- **El editor** del `main` de Chema y sus servicios de revisión `8101–8103` es otro runtime. `deploy/entry.py` usa HTTP Basic Auth con credenciales del entorno de revisión, **no** un registro personal por email y contraseña. `urano/http_auth.py` sí ofrece registro/login email y password, pero está **expresamente limitado al laboratorio** (sin verificación de correo y no montado en la beta pública). No enlazar estos mecanismos con Google ni añadir un segundo login comercial sin identidad unificada y seguridad real.
- En `fernando/integracion`, `urano/minimal_owner_api.py` contiene sesión Google y catálogo, pero **no** está vinculado al Engine ni al editor: el dashboard integrado es una página de proyectos y no ofrece un enlace funcional de edición. La rama C8 histórica contiene un `WORKSPACE_PAGE` de laboratorio más amplio que no es la integración aprobada. No incorporar ese workspace ni rutas de Engine sin I5B / E2E.

## Solución acotada de I7

Recuperar el HTML público con las cabeceras CSP originales en `fernando/integracion`, sustituir los dos accesos principales a la beta por enlaces HTTPS absolutos al **único Owner real** y actualizar los textos: Google disponible solamente para cuentas autorizadas; el registro por email y contraseña y el editor/Companion **siguen sin estar habilitados desde esta portada**. No prometer que crear proyecto abre editor ni registrar usuarios públicamente.

La app Owner y su seguridad quedan sin cambios. Esta PR no incluye cambios de Cloudflare Pages, Worker, VPC, Tunnel, OAuth, `app.py`, Companion ni Engine, y **NO hace deploy**. La publicación real de la portada requiere coordinar control de ramas en Pages: hoy Pages observa la histórica C8. **No cambiar en producción el branch a `fernando/integracion` a ciegas** sin revisar la salida Pages completa.

## Siguientes bloques

1. Verificar manualmente OAuth con cuenta tester (sin compartir tokens, contraseñas ni capturas sensibles) y retorno a dashboard. Acceso denegado a cuentas no invitadas.
2. Elegir producto de identidad: Google inicial; futuro email/password deberá usar un propietario canónico, vinculación segura de cuentas y verificación de email; **no** reutilizar Basic Auth de una VM como autenticación pública.
3. I5B: activar un worker aislado por propietario y vínculo con proyecto, con verificación de acceso cruzado y límites.
4. Integrar editor + Companion y preparar la primera medición de una persona de I6; después actualizar textos de portada para reflejar funciones realmente disponibles.

**Puerta de aceptación visual:** click desde Pages → Owner → Google → panel; creación/proyecto, cierre de sesión y sesión recuperada con UX coherente; editor solo cuando exista worker autorizado. La prueba unitaria de HTML no sustituye ese E2E.
