# Montara — portada beta pública de coste cero

**Dominio elegido y proyecto Pages creado:** subdominio estable `montara-beta-preview.pages.dev` (pendiente de verificar primer despliegue). Alojamiento estático Cloudflare Pages **separado** de `montara-cloudflare-lab.pages.dev`. El laboratorio anterior no debe cambiar.

## Qué se publica

Solo una portada comercial responsive en español, con información del producto, modalidades de vídeo, Companion y estado de la beta privada. No incluye JavaScript, formularios, subida de vídeo ni acceso Google habilitado. El botón de acceso está deliberadamente desactivado. No promete que los proyectos o el editor estén operativos en ese hostname.

**No confundir:** Cloudflare Pages aloja la landing, **no** el Engine Flask de la VM, la autenticación OAuth ni la edición. El preview real single-user continúa exclusivamente por SSH en `127.0.0.1:8114`, aislado. La futura beta multiowner requerirá HTTPS bajo **un mismo origen fiable** para la sesión y APIs, así como un acceso seguro al backend privado; no se puede inferir que Pages resuelve el problema de origen/proxy por sí solo.

## Build y CI

- Fuentes: `deployment/cloudflare-beta/public/index.html` y `_headers`.
- `python3 tools/cloudflare-beta/build.py` genera `dist` únicamente con los archivos públicos conocidos.
- En Pages, usar raíz `/`, comando anterior, salida `dist`, rama `fernando/c8-public-beta-landing-pages-20261110`.
- Tests GitHub: `C8 static Cloudflare beta landing acceptance`.

## Condiciones para habilitar login

1. Dominio HTTPS fijo, host y ruta de callback OAuth registrados en Google Cloud.
2. API privada WSGI de `urano/owner_beta_wsgi.py` accesible detrás de una frontera HTTPS confiable, sin bypass de cabeceras Host ni X-Forwarded.
3. Usuario beta explícitamente autorizado, sesión cookie Secure y pruebas de sesión y proyecto ajeno denegados.
4. Proxy/Companion emparejado con origen idéntico y clave HMAC fuera del navegador.
5. Engine por propietario provisionado e Ingest/certificación/MP4 físico probados.
6. **Solo entonces** sustituir el botón desactivado por un enlace al acceso real. Evitar redirecciones a Google desde la landing si no existe backend seguro.

## Costes y limpieza

Pages para esta landing estática no requiere compra de dominio. No se ha activado carga de vídeos, Workers de pago, R2 ni servidor adicional. Si se abandona la beta, conservar el código Git y retirar únicamente el proyecto Pages que se haya creado de forma inequívoca, sin tocar el laboratorio Pages anterior ni `main`.
