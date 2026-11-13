# I2 — Google verificado + catálogo SQLite privado en main (opt-in, sin editor)
**Fecha:** 2026-11-13 · **Estado:** candidato integrado por PR desde main; NO habilita todavía el recorrido completo de Stage/Push/Show.

> **Para Chema y su IA.** La interfaz de Montara no cambia en este PR. Internamente, se prepara una aplicación Owner separada que verifica la identidad Google, emite sesiones Montara de 3 días y utiliza el catálogo y permisos SQLite **ya existentes** en main. El editor original, los workers, el render local y Companion no se conectan aquí. Hasta que se integren las siguientes piezas, no activar este módulo como sustituto del editor en producción.

## A. Novedades
- `urano/google_oidc.py`: verificación criptográfica de firmas JWT RS256 con JWKS Google **de origen fijo**; verifica issuer, audience, nonce de una sola transacción, caducidad, correo verificado y alg/key id.
- `urano/google_owner.py`: persistencia del Google `sub` validado → identificador de propietario de Montara; lista explícita de correos autorizados, no enlaza por correo cuentas de contraseña ni permite elegir `owner_id` desde navegador.
- `urano/google_flow.py`: Authorization Code + PKCE S256, `state` y `nonce` de un solo uso, cookie de flujo segura, intercambio con Google en endpoints fijos, firma validada, sesiones Montara de **72 horas** desde `SessionStore.issue` sin TTL opcionales.
- `urano/google_catalog_app.py`: factoría Flask optativa para un **origen HTTPS y directorio SQLite privado independiente**. Reutiliza `project_blueprint` de main, protege `Host`/`Origin`, ofrece refresh CSRF; no conecta ni arranca el editor o Engine.
- `requirements.txt`: declara `cryptography>=42` para verificar firmas (también necesario en CI).
- `tests/test_google_owner_catalog_i2.py`: Google falso con RSA real (sin Internet/credenciales), dos cuentas y dos proyectos, bloqueo de acceso cruzado, orígenes falsos, CSRF, logout y rechazo de Google sin autorización.

## B. Duplicidades
`main` **ya incluye** `urano/session_auth.py`, `project_catalog.py`, `http_projects.py` y `accounts.py`. Reutilizamos esas piezas sin crear una segunda API de catálogo ni modificar el servidor de Chema, y no copiamos los módulos H4 de gateway/worker.

## C. Reutilización
Los tres módulos Google ya se ejecutaban en la beta aislada H4 y están revisados como fuente. Su contrato se inserta en `main` con un montaje explícito de la factoría aislada. El inicio de sesión Google y la sesión de Montara son cosas distintas: los ID tokens de Google se validan en el callback, y nuestra cookie Montara dura 3 días sin necesitar un token Google de igual duración.

## D. Riesgos / límites y gates
- **Sin despliegue en este PR**: la factoría exige ruta de datos privada preexistente con permisos 0700, dueño real del proceso, URL de callback HTTPS exacta y lista de usuarios permitidos. No guarda tokens ni secretos en GitHub; no configura Cloudflare ni provisiona base de datos.
- No registrar el blueprint Google en la aplicación global `app.py` ni exponer el motor directamente. El proxy inverso debe entregar Host/esquema verificados y no permitir spoofing mediante X-Forwarded-*.
- No reutilizar un Google `email` como clave de `owner_id` ni convertir usuarios Google a cuentas password silenciosamente.
- Aún falta el contrato de ejecución por propietario: adaptar el editor de Chema con un broker que no acepte IDs del navegador como permisos; comprobar aislamiento real de media/frames/mix/render; un catálogo privado sin Engine privado no es el producto multiusuario.
- La UI de catálogo es una API JSON, **no** el editor. El usuario no recibirá el flujo Stage H4 en main hasta I3/I4.
- Riesgo controlado: las dependencias declaradas pueden ampliar las instalaciones Linux; revisar CI completo. Los tests con proveedor sintético no sustituyen una prueba humana posterior contra Google OAuth real.
- No modificar `engine/`, `mixer/` ni componentes Windows/Mac en I2.

## E. Recomendaciones
Pruebas realizadas en un directorio temporal separado de la VM, con los módulos I2 exactos y dependencias existentes de main, con Python 3.11 y `cryptography 48.0.1`:
```sh
PYTHONPATH="$dir" /home/fgardel00/montara-owner-portal-release/.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```
**PASS 15/15**, incluyendo 3 tests de nuevo login Google RSA, 5 de catálogo y 7 de sesiones HTTP. No se realizó E2E Linux con capturas ni despliegue (no cambia UI).

**Orden de integración restante:** I3 broker/worker por propietario, I4 puente al editor Chema, I5 Companion con detección Windows/Mac e instaladores alojados en nuestro servidor, I6 ciclo de vida y VM, I7 E2E real de dos usuarios y regresiones. Revisar `docs/COLLABORATION.md`, issue #216, el informe general de handoff Owner de `fernando/chema-native-owner` y las auditorías de aislamiento antes de tocar rutas, sesiones o medios.

**Política de integración:** autorizada por Chema a Fernando para avanzar por piezas; el PR sirve de trazabilidad, no de almacén de código eternamente abierto. Integrar si tests/CI/compatibilidad son satisfactorios. No fusionar una rama H4 entera ni presentar `main` como beta funcional completa sin I3–I7.
