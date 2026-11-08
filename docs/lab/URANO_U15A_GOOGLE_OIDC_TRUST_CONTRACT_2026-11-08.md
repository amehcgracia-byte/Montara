# URANO U15A · Contrato de identidad Google OIDC (08-11-2026)

**Estado:** implementación aislada + pruebas de firma/propiedad; **no** login de Google listo para usar, **no** URL beta publicada, **no** integración con Engine/Companion ni servicio de JM. Código público, **sin secretos**.

## Base
- Rama `fernando/urano-u15-google-oidc-trust-contract` creada desde Montara `main` `765a34ceec33311cd520856d46fec15adfc6c0a1` (incluye PR #122).
- Reutiliza el catálogo `ProjectCatalog` de U10, las sesiones opacas revocables `SessionStore` de U11 y los contratos existentes de propietarios sin tocar su funcionamiento. El laboratorio web U12b continúa separado del producto.
- Nuevos `urano/google_oidc.py` y `urano/google_owner.py`, tests offline y dependencia opcional `requirements-urano-oidc.txt`. No modifica `app.py`, `web/`, `engine/`, `mixer/` ni deploy.

## Qué se verifica y qué NO

`verify_google_id_token` comprueba **firma RS256** frente a un conjunto de claves JWKS **suministrado de un origen Google confiable**, `kid` único, tamaño RSA mínimo, `iss` de Google, `aud` del Client ID configurado, `azp` cuando corresponda, `exp`, `iat`, `nonce` de intento de acceso y `email_verified` booleano. Devuelve únicamente `GoogleIdentity(sub, email)`. Se rechazan firmas inválidas, `alg=none`, audiencia ajena, credenciales caducadas, nonce incorrecto y claims malformados. **No confundir este verificador con un OAuth completo:** la verificación no consume el nonce ni intercambia códigos.

`GoogleOwnerStore` asigna a cada `sub` verificado un UUID propietario persistente y diferente. Su lista de emails autorizados procede de configuración privada del operador, validada en cada login; dos `sub` distintos **no se fusionan por tener el mismo email**. El almacén no guarda contraseñas Google, tokens ni archivos. No enlaza automáticamente a cuentas con contraseña U12b por email.

Prueba adicional: dos identidades Google de ejemplo generan propietarios distintos, proyectos distintos en `ProjectCatalog`, sesiones distintas en `SessionStore` y se rechaza el acceso cruzado; la revocación de la sesión de A no invalida la de B.

## Seguridad y siguientes pasos imprescindibles

Para poder usar esto en una página privada hay que añadir, **en una PR separada y opt-in**:

1. Authorization Code + PKCE con `state` y `nonce` aleatorios vinculados a la sesión de navegador, **consumidos una sola vez**, timeout corto y protección contra replay/login CSRF.
2. Intercambio del código con el endpoint token HTTPS fijo de Google; obtención/cache con caducidad de JWKS exclusivamente desde el endpoint HTTPS oficial, manejo de rotación y errores fail-closed; validación con este verificador **en backend**.
3. Client ID, Client Secret y allowlist en configuración/secrets del servidor, redirect URI HTTPS exacta, cookies `__Host-` Secure/HttpOnly, sesión rotada y revocable, logout, restricción de beta y rate limiting.
4. Test navegador HTTPS/Chrome con dos Google sujetos simulados **sin llamar a Google ni utilizar credenciales reales**; posteriormente smoke con credenciales de Google configuradas por el operador, 2 cuentas reales, URL laboratorio privada y acceso al historial. No habilitar el registro por contraseña actual en un entorno público.
5. **Independientemente** de la autenticación, el catálogo de recetas aún **no** da acceso seguro al Engine compartido ni a medios: vincular owner→proyecto→runtime/worker y proteger todos los endpoints, descargas y rutas. Esta PR no pretende resolverlo.

El objetivo inmediato es evitar un login «simulado» por email que daría acceso a proyectos ajenos y disponer de una unidad de confianza probada antes de construir el callback.

## Pruebas y ejecución

- `python -m unittest discover -s tests -p 'test_urano_google_oidc.py' -v` usando `requirements-urano-oidc.txt`; todos los tokens, claves RSA, emails y propietarios son **ficticios**.
- GitHub Actions `.github/workflows/urano-u15-google-oidc.yml` instala `cryptography` solo en el job de tests.
- Biblioteca de criptografía no estaba presente en el venv FER de la GCP; no se modificó ni se instaló ningún paquete global. La CI de GitHub ejecuta el contrato en aislamiento.
- No se han tocado medios originales, servicios de JM, FER, GCP/red ni secretos.

**No publicar un acceso beta hasta validar el flujo completo de OAuth/OIDC y la autorización efectiva de proyecto y media.**
