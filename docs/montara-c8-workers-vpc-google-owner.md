# C8.4–C8.5 — Entrada Google estable sin dominio de pago

**Estado 2026-11-10:** portada pública operativa, pasarela Worker operativa pero bloqueada a propósito, túnel y VPC Service creados en Cloudflare **sin conector activo**. La beta Google real **no** está disponible todavía. No se ha modificado la VM ni el editor en 8114.

## Arquitectura adoptada

- Portada: `https://montara-beta-preview.pages.dev` — Cloudflare Pages, sin subida ni login habilitado.
- Portal privado: `https://montara-owner.memoriainvalida001.workers.dev` — Cloudflare Worker `montara-owner`, sin dominio comprado.
- Cloudflare Workers VPC Service `montara-owner-private-8115` (service_id `01a1c2d5-533f-74e2-aef7-e9d846cd9db8`), **limitado a `127.0.0.1:8115`**.
- Cloudflare Tunnel remoto `montara-owner-fg` (tunnel_id `4a65ebdb-268e-4879-9d99-db1ec05c4041`), **registrado pero sin conexiones**. Nada de puertos entrantes públicos.
- Futuro backend WSGI `create_loopback_owner_application()` en la cuenta independiente `fgardel00`, escuchando únicamente en `127.0.0.1:8115`. El portal usa el código original C1–C5 (Google OIDC + propietario + catálogo), **no** el editor global.
- El Worker únicamente permite `/`, `/healthz`, `/urano/v1/*`; filtra headers, impone HTTPS/hostname fijo, no deja navegar a URLs arbitrarias ni monta `/api/v1`. Conserva cookies y redirecciones del OAuth real.
- El WSGI boundary rechaza headers X-Forwarded/Forwarded/IP incluso si los provee el cliente, y solo confía en conexiones de loopback y Host fijo. Los clientes Cloudflare en la red externa no llegan directamente a WSGI.
- La antigua beta de editor clásico `127.0.0.1:8114` sigue aislada y **no** es el destino del Worker.

## Comprobaciones realizadas

- `C8 pinned HTTPS reverse-proxy and real Google owner entry`: pruebas de WSGI HTTPS del propio Flask, anónimo denegado y redirecciones reales de Google; CI exitoso.
- `C8 private Google owner gateway via Cloudflare Workers VPC`: rutas bloqueadas, headers falsificados descartados, cookies preservadas, 503 sin backend; CI exitoso.
- Cloudflare confirmó que el Worker `montara-owner` tiene binding `OWNER_PRIVATE_API` a ese servicio VPC.
- `https://montara-owner.memoriainvalida001.workers.dev/` devuelve **HTTP 503** con `Private beta not provisioned`, como debe ocurrir sin túnel/backend.
- Portada Pages independiente, HTTP 200; `main` y servicios 8101–8103 sin modificaciones.

## Puertas para habilitar Google y Companion

1. En Google Cloud OAuth **Web application** (proyecto elegido y autorizado): añadir el callback exacto
   `https://montara-owner.memoriainvalida001.workers.dev/urano/v1/google/callback`.
   Origen autorizado de JS opcional si lo exige UI: `https://montara-owner.memoriainvalida001.workers.dev`.
   Configurar únicamente correos de testers autorizados. No publicar Client Secret en GitHub, chat ni Worker.
2. Provisionar secreto OAuth como fichero 0600 **solo en `fgardel00`** y carpeta owner 0700 separada de la beta clásica. El portal no puede arrancar sin este fichero.
3. Instalar `cloudflared` versión compatible **solo en HOME de `fgardel00`**, obtener token del túnel por canal privado, conexión QUIC salida UDP 7844. Sin sudo, sin systemd de Chema ni nuevos puertos públicos. No incluir token en scripts, commits o logs.
4. Levantar backend WSGI privado en `127.0.0.1:8115`, verificar 401/403 anónimo y 303 Google, Google ID token real, cookie Secure HttpOnly y dashboard.
5. Probar dos identidades: propietario de la beta puede listar únicamente sus propios proyectos; otros correos rechazados. Las pruebas sin Engine deberán mostrar Engine no provisionado.
6. Para Stage/Companion se requerirá además aprovisionamiento de worker aislado, HMAC de Companion en fichero privado y certificado de procedencia de cada proxy. No conectar al Engine global ni habilitar subida accidental de originales.
7. Solo después de la prueba completa, sustituir el CTA desactivado de la landing pública por enlace seguro al `workers.dev`.

**Puntos operativos:** Cloudflare Workers VPC está en beta y puede cambiar; actualmente indicado gratuito por Cloudflare durante ese período. Puede quedar inactivo si la VM se apaga automáticamente (issue #155 en revisión con Chema). No se instaló cloudflared aún. Los recursos recién creados son explícitos y se pueden revocar de forma independiente.

## Desmontaje limpio si no continuamos

1. Desactivar primero el subdominio de `montara-owner` (fail-closed); no tocar `montara-cloudflare-lab` ni `montara-beta-preview`.
2. Eliminar el binding del Worker y revisar que no hay usuarios reales activos.
3. Retirar VPC Service `montara-owner-private-8115` y Tunnel `montara-owner-fg` únicamente si están exclusivamente asociados a esta beta.
4. Detener únicamente proceso privado `fgardel00` y retirar sus archivos explícitos después de hacer inventario; nada de limpieza general `docker prune` o carpetas de Chema.

## Gobernanza

Código solo en `fernando/c8-public-beta-landing-pages-20261110` (PR #158); ni `main` ni despliegue de Chema fueron modificados. La consola Google y las credenciales reales serán tarea del propietario del proyecto, con intervención del usuario cuando corresponda.
