# URANO U12 — Registro y login de laboratorio con recuperación de proyectos

**Fecha:** 2026-11-06. **Estado:** contrato de backend en PR DRAFT, **NO desplegado ni conectado a la interfaz**, pendiente de veredicto CI. Basado en U11, que a su vez depende de U10.

## Lo que implementa

1. `urano/accounts.py`: cuentas de prueba con identificador UUID asignado exclusivamente en servidor; email normalizado en almacenamiento SQLite; contraseña de 12–256 caracteres hasheada mediante `hashlib.scrypt` con sal aleatoria independiente (N=16384, r=8, p=1).
2. Método `register(email,password)` crea cuenta persistente; `verify(email,password)` entrega el UUID del propietario solo tras verificar credenciales. La cuenta **no prueba la posesión de ese correo**.
3. Contador de fallos transaccional y bloqueo temporal de cuenta tras cinco intentos fallidos durante quince minutos; se conserva al reabrir SQLite. Es una protección inicial, **no rate-limit por IP/perímetro** ni defensa completa frente a abuso o ataques de denegación.
4. `urano/http_auth.py`: rutas *opt-in* `POST /urano/v1/register` y `POST /urano/v1/login`, exigen `Origin: https://{Host}`, responden con cookie de sesión HttpOnly, Secure, SameSite=Lax, Path=/, sin Domain, y token CSRF asociado a sesión; no aceptan ID de propietario elegido por navegador.
5. Se reutiliza sin modificar U11 `SessionStore` y U10 `ProjectCatalog`: dos clientes HTTP con distintas contraseñas crean proyectos, no pueden acceder a los ajenos, y un nuevo cliente puede iniciar sesión y recuperar su proyecto anterior.
6. Siete tests de integración de laboratorio: alta/login/recuperación y aislamiento, rechazo de duplicados, no almacenamiento de contraseña en claro, errores de contraseña, bloqueo y expiración, Origin y validación de registros.

## Límites de seguridad importantes

- **NO usar con usuarios reales ni exponer a Internet.** Sin verificación email, confirmación/recuperación de cuenta, MFA, protección anti-bots, política de privacidad, límite de intentos por IP, controles de redistribución de recursos y TLS/proxy revisados.
- `Origin` se compara con el `Host` recibido; antes de activar debe imponerse un host permitido y esquema HTTPS desde un proxy de confianza. Los clientes que no envían Origin se rechazan. `Origin` por sí solo no sustituye autenticación ni CSRF.
- El token CSRF vuelve al navegador en respuesta JSON de login/registro; no se almacena en localStorage. Al recargar página, `POST /urano/v1/session/refresh` con Origin HTTPS mismo host y cookie válida rota el secreto CSRF **sin extender la sesión**; invalida el anterior, no requiere repetir contraseña. La web aún no está conectada a este contrato.
- No se implementa UI de alta/login ni enlace al editor; la promesa de v1 sigue pendiente de integración real, aislamiento Engine/medios y persistencia de estado.
- El estado del Engine global en un proceso sigue **sin ser multiusuario**. Nunca conectar estos endpoints a un único Engine compartido sin aislamiento de trabajos.
- Las cuentas del laboratorio son ficticias, sin emails personales ni contraseñas reales.

## Gates y próximo paso

- Pruebas: `python -m unittest discover -s tests -p 'test_urano_*.py' -v`; workflow CI U12 específico y E2E general.
- Fusionar en orden U10 → U11 → U12, con revisión de seguridad y actualización de bases entre PR apiladas.
- Próximo trabajo U12b: definir UI separada de registro/login/catálogo en entorno aislado; ningún cambio a la portada principal hasta ensayo visual y aceptación; resolver recuperación de CSRF, cookies y aislamiento de runtime antes de publicar.
- El laboratorio Cloudflare estático está publicado como benchmark visual; **no** ejecutar sobre él estos endpoints ni sugerir que la réplica procesa vídeos.
- Sin modificaciones en `main`, VM FER/JM, Vercel, DNS, submódulos o Companion.

**Principio:** integración por piezas verificables, sin llamar producto comercial a un contrato de laboratorio.
