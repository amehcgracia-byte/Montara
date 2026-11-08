# URANO U15B — Authorization Code + PKCE y callback aislado (08-11-2026)

**Estado: implementado y CI unitaria/HTTP simulada PASS. No desplegado. No login real Google operativo.**

## Base y alcance

- Requiere la rama/PR **#124 (U15A)** de verificación JWT RS256 y asignación estable de `Google sub → owner UUID`. La nueva rama `fernando/urano-u15b-oidc-authorization-flow` está apilada sobre el HEAD `3277aeec` de #124. No fusionar U15B directamente a main antes de incorporar/rebasar U15A.
- Nuevo módulo `urano/google_flow.py` (**exclusivo del laboratorio**, no importado ni registrado en `app.py` ni en los servicios JM/FER).
- Se reutilizan `urano.google_oidc.verify_google_id_token`, `GoogleOwnerStore`, `SessionStore`, `project_blueprint` y el catálogo SQLite existente. **No se inventa otro catálogo**.
- No se han instalado paquetes en GCP ni ejecutado tareas sobre 8101/8102/8103.

## Flujo implementado (backend)

1. `GET /urano/v1/google/start` crea en SQLite un intento de login (TTL 10 minutos): `state`, `nonce`, `code_verifier` de alta entropía. Solo guarda SHA-256 de `state` y cookie de vinculación. Cookie temporal `__Host-montara-oidc-flow` Secure/HttpOnly/SameSite=Lax. Devuelve 302 al **endpoint fijo** de Google con `response_type=code`, `scope=openid email`, `code_challenge=S256`, callback exacto HTTPS.
2. `GET /urano/v1/google/callback`: valida mismo host HTTPS que el redirect configurado, `state` y vinculación de cookie, consume el intento **transaccionalmente y una sola vez, incluso si la vinculación falla**; rechaza duplicidad de parámetros/missing code. Hace exchange de code+PKCE+Client ID+Client Secret vía POST al endpoint fijo HTTPS de Google y obtiene JWKS del endpoint fijo HTTPS Google; el adaptador HTTP rechaza redirecciones, limita tamaño de respuesta y tiene timeout. Verifica firma y claims del ID token con U15A y el nonce del intento.
3. Si la identidad verificada pertenece a la allowlist del operador: crea/recupera owner UUID estable, emite **nueva sesión opaca revocable** de U11 con cookie segura, revoca token de sesión anterior si lo había y responde 303 al endpoint **del catálogo protegido**, sin URL de redirección suministrada por el usuario. Borra la cookie de intento. Si falla: 401 y **sin sesión nueva**.
4. `OIDCSettings` requiere Client ID, Secret, callback HTTPS exacto y allowlist no vacía desde configuración privada. El código de la rama no contiene credenciales reales ni autoriza secretos desde query/formulario.

## Evidencia

`tests/test_google_flow_contract.py` utiliza **Google falso, claves RSA temporales firmadas y dos navegadores lógicos independientes** mediante Flask test clients (NO OAuth contra Google real). Incluye happy path con PKCE/nonce, cookies, catálogo protegido y CSRF; reuso de state, binding cruzado, nonce falso, email fuera de allowlist, token caducado en U15A, parámetros duplicados, host/protocolo distintos, expiración, y dos `sub` Google con historiales distintos y rechazo de lectura cruzada.

La primera CI encontró que un intento con state válido pero cookie equivocada se rechazaba *sin consumir* la transacción. Se corrigió el manejo: el `state` se elimina de SQLite bajo bloqueo antes de la validación de binding. Segundo run de `URANO U15B isolated Google authorization PKCE`: **SUCCESS** (run `42510385019`, commit `1cc7440c`). Esto es una prueba real del protocolo **dentro de backend falso**, no un test navegador/Internet.

## Pendiente antes de una beta navegable

- Añadir **fábrica Flask opt-in** para U15B y una UI Google separada del login de contraseña U12b, sin poner endpoints en app principal ni activar JM. Validar HTTPS/Chrome con dos contextos de navegador y un proveedor falso, capturas, login/logout/revocación.
- Configurar por parte del operador una aplicación OAuth de Google, redirect URI HTTPS exacta, Client ID/Secret y allowlist **en secrets**, comprobar JWKS/tokens de Google reales y autorización de dos cuentas de pruebas.
- Definir políticas de expiración/rotación del cache de JWKS y reintentos prudentes, invalidación/cancelación de intentos, límites de intentos por IP/usuario, configuración de proxy/Host permitido, política CSRF/logout/cookies entre distintos entornos 8101/8102/8103. El código HTTP actual obtiene JWKS en cada autenticación (sin caché).
- **La identidad no autoriza al Engine/medios compartidos**: vinculación owner→proyecto→worker/ruta, control de permisos en uploads/descargas, cuotas y concurrencia están pendientes. No usar el login de laboratorio como protección de una web SaaS.
- No usar el mismo nombre de cookie en diferentes puertos del mismo host: las cookies HTTP **no están aisladas por puerto**. Proveer hostname aislado para beta o separación deliberada de sesiones.
- No integrar ni desplegar de forma automática: solo PR de revisión para Chema.

**Colaboración:** este módulo no toca selección de cámaras, snapshots, `web/cut-editor.js`, Engines ni la rama de fixes de Chema. Seguimos avanzando en la capa de identidad por separado.
