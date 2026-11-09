# C6 — Preparación de beta HTTPS + Google real + Companion local

**Estado:** configuración y validación offline, **sin despliegue**. La fase C7
elegirá un entorno beta aislado; no modificar servicios 8101–8103 ni `main`
sin permiso previo del usuario y Chema.

## Qué está implementado

- `urano/google_flow.py`: flujo OAuth Google Authorization Code + PKCE, state,
  nonce, one-time callback, lista beta de correos, sesión HttpOnly/Secure.
  `GoogleProvider` de producción consulta solo endpoints fijos de Google;
  los tests simulan Google sin credenciales reales.
- `urano/c6_beta_preflight.py`: verifica que servidor y Companion comparten
  un único origen `https://<dominio-beta>` sin comodines, que Google Client ID
  tiene estructura de aplicación web, que el secreto vive en un fichero
  privado (0600 en Linux) y que la lista beta no está vacía.
- `companion/companion.py`: el endpoint sensible de **recibos firmados**
  requiere `MONTARA_COMPANION_BETA_ORIGIN` exacto. Las antiguas expresiones
  de CORS para previews **no** bastan para emitir un recibo; los otros
  endpoints de Companion no cambian.
- Tests aislados en `tests/test_c6_https_google_preflight.py`, sin llamadas
  a Google ni necesidad de ordenador del usuario.

## Decisiones necesarias en C7 (sin secretos en GitHub)

1. Seleccionar **un** nombre de host HTTPS para beta, por ejemplo
   `https://beta.example.test` en los ejemplos **ficticios** de CI.
   No usar un dominio comodín ni una URL de preview que cambie en cada build.
2. Registrar en Google Cloud un cliente OAuth **Web application**;
   añadir exactamente `https://DOMINIO/urano/v1/google/callback`
   a los URI de redirección permitidos. El URI debe coincidir carácter a
   carácter con el configurado en `OIDCSettings`.
3. Proveer en **ficheros privados fuera del repositorio** las claves de
   Google y el emparejamiento HMAC de Companion. No almacenar secretos en
   variables públicas del frontend ni en PR, issues, logs o mensajes.
4. Configurar únicamente los correos autorizados para probar la beta.
5. Instalar un reverse proxy HTTPS con Host/scheme validados y conexión
   exclusivamente de loopback hacia la aplicación de propietario.
   **No aceptar cabeceras `X-Forwarded-Host` / `X-Forwarded-Proto`
   sin una frontera proxy de confianza y conectividad restringida**.
6. Verificar Chrome/Edge: la página HTTPS debe poder hablar con
   `127.0.0.1:47820` según las políticas actuales de acceso a red local;
   comprobar CORS, preflight y cualquier permiso de red local.
7. Emparejar el Companion instalado en Windows/macOS con el dominio
   `MONTARA_COMPANION_BETA_ORIGIN` y su clave privada. La aplicación web
   **solo transporta firmas**, no conoce ni puede solicitar la clave.

## Variables que valida el preflight

| Nombre | Ejemplo ficticio o uso |
|---|---|
| `MONTARA_BETA_ORIGIN` | `https://beta.example.test` |
| `MONTARA_COMPANION_BETA_ORIGIN` | **idéntico** al origen anterior |
| `MONTARA_GOOGLE_CLIENT_ID` | ID de OAuth tipo `...apps.googleusercontent.com` |
| `MONTARA_GOOGLE_SECRET_FILE` | ruta absoluta privada al secreto |
| `MONTARA_BETA_ALLOWED_EMAILS` | direcciones explícitas separadas por comas |

La función `validate_beta_settings(dict(os.environ))` **solo valida** y
construye `OIDCSettings`; no abre sockets, ejecuta proveedores, instala
software ni toca repositorios compartidos. El operador deberá usar este
resultado cuando monte la aplicación aislada en C7.

## Puertas antes de anunciar C6 terminada

- [x] OAuth Google con PKCE / nonce / sesión de un solo uso en laboratorio.
- [x] Configuración HTTPS fail-closed y CORS sensible por dominio exacto.
- [ ] Dominio real elegido y certificado TLS emitido.
- [ ] Cliente OAuth Google de producción creado y consent screen configurada.
- [ ] Login real de un usuario autorizado y rechazo de otro no autorizado.
- [ ] Companion local Windows/Mac emparejado con ese dominio; recepción
  privada y recibos firmados en HTTPS auténtico.
- [ ] Certificación completa y MP4 final en C8.

**No hacer limpieza de ramas ni merge a `main` antes de la beta humana:** C5
mantiene la referencia base, C6 queda como PR apilada. La consolidación general
vendrá después de C8, tras identificar ajustes reales del usuario.
