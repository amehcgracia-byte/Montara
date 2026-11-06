# URANO U11 — Sesión revocable y API de proyectos por propietario

**Fecha:** 2026-11-06 · **Estado:** contrato aislado, pendiente de resultados CI. **No desplegado ni montado en la aplicación pública.** Rama basada en `fernando/urano-u10-project-ownership-contract`; PR apilada sobre U10.

## Diseño entregado

- `urano/session_auth.py`: sesiones con identificadores aleatorios de 256 bits; base SQLite guarda solo SHA-256 del token y del CSRF, no los valores originales. Caducidad explícita (1–86400 s), verificación y revocación persistentes.
- Cookie `__Host-montara-urano` con `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/` y sin `Domain`.
- `urano/http_projects.py`: blueprint opt-in bajo `/urano/v1`. **No se registra automáticamente** en `app.py` ni `deploy/entry.py`. Endpoints: `GET /projects`, `POST /projects`, `GET /projects/{id}`, `PUT /projects/{id}/recipe`, `POST /logout` (todos bajo el prefijo).
- Identidad: `SessionStore.verify(cookie)` resuelve el `owner_id`; encabezados `X-User-ID`, `owner_id` en JSON y otros datos arbitrarios del cliente **no sirven para suplantar**. SQL vuelve a comprobar propiedad en cada operación.
- Protección CSRF para todo método mutante con `X-Urano-CSRF`; la cadena debe coincidir con el hash asociado a la sesión. Los proyectos ajenos producen 404; revisiones obsoletas, 409.
- Pruebas reales HTTP con Flask `test_client`, dos identidades ficticias: aislamiento lectura/escritura, suplantación, ausencia de cookie, CSRF, persistencia, revocación/caducidad y atributos de cookie.

## Lo que NO significa

- **No hay alta de cuenta, login, verificación de correo ni proveedor de identidad**. La función `SessionStore.issue(verified_owner_id)` solo debe invocarse desde un login real que haya verificado al usuario en el servidor. **No implementar nunca una ruta pública que reciba `owner_id` y emita sesiones**. Los tests crean sesiones deliberadamente desde código de confianza.
- El token CSRF debe entregarse al frontend **tras autenticación real**, nunca a una sesión ajena. En un despliegue se requiere TLS, configuración de proxies, política de orígenes, rate-limits, gestión de sesiones vencidas/rotación y comprobación de CSRF en todos los endpoints mutantes de la aplicación, incluidos media/Engine.
- El Engine actual mantiene un proyecto activo global dentro del proceso; la protección del catálogo **no aísla todavía trabajos, medios, exportaciones ni el runtime Engine entre usuarios**.
- No existe integración con interfaz web real, Companion, Cloudflare, Vercel ni VM FER; esos son gates posteriores.
- SQLite y el tamaño máximo de receta son decisiones de prototipo, sujetas a backups, esquema y pruebas de escalado; las claves no almacenan originales multimedia.

## Comprobación automatizada

`python -m unittest discover -s tests -p 'test_urano_*.py' -v` con Flask 3.x instalado para `test_client`.

En GitHub Actions el workflow específico `urano-session-http.yml` debe estar en verde y hay que confirmar el E2E general. En caso de fallo, corregir sobre esta rama antes de solicitar integración.

## Secuencia de integración

1. Revisar PR U10 y aprobar/mergear **antes de** integrar U11; evitar mezclar ramas sin decisión.
2. Elegir proveedor de autenticación verificada, flujo de alta/login real, entrega de cookie+CSRF y revocación de sesiones, rate-limit e incidencias.
3. Probar que la app web original conoce el proyecto correcto tras login/logout y tras abrir una pestaña nueva; exigir HTTPS y separación real de dominios/hostnames.
4. Diseñar aislamiento Engine/archivos por propietario y proyectos y prueba E2E con dos usuarios; no conectar este catálogo a un único proceso Engine compartido sin resolverlo.
5. Conectar Companion y recuperación sin enviar originales pesados por defecto.
6. Desplegar únicamente en entorno aislado y con rollback tras superar los gates; conservar Vercel y servicios activos.

**Guardarraíles:** sin datos personales reales, sin secretos en repositorio, sin cambios en `main`, Chema, VM activa, Vercel o DNS.
