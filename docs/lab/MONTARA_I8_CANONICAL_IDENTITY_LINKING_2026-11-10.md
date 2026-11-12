# I8 — Una identidad, varios métodos de entrada, mismos proyectos

**Fecha:** 2026-11-10. **Entrega:** mecanismo de consolidación de propietarios de confianza (datos y tests), sin habilitar formulario web, email de verificación ni registro público. **Destino:** `fernando/integracion`, no `main`.

## Regla del producto

Una persona puede entrar con (1) Google OIDC verificado y (2) email + contraseña **con correo verificado**. Ambos métodos deben terminar en el **mismo owner_id canónico**. Sus proyectos, recetas, IDs y revisiones no deben perderse en ninguno de los dos órdenes:

- contraseña → crear proyecto → Google;
- Google → crear proyecto → contraseña.

**No enlazar automáticamente solo porque dos sistemas informen el mismo texto de email.** El login Google actual confía en el `sub` de Google y valida `email_verified`; el módulo `urano/accounts.py` de laboratorio registra contraseñas con scrypt, **pero no verifica la posesión del email**. Además, con cuentas Google de dominios externos, `email_verified` no demuestra necesariamente que Google siga siendo autoridad sobre ese buzón. Es preciso un paso explícito de vinculación/autenticación de los dos métodos o una comprobación adicional de correo confiable. Al completar el vínculo, los logins posteriores ya se resolverán al mismo propietario.

## Lo implementado en I8

- `urano/owner_identity_links.py`: módulo puro de SQLite **no registrado en HTTP**, sin lectura de secretos. Se acopla al fichero privado **projects.sqlite3** para que vincular propietarios y mover filas sea una única transacción atómica; no mueve medios originales.
- La identidad está indexada por proveedor + sujeto estable: Google `sub` o email de cuenta contraseña normalizado; el correo verificado es información adicional, **nunca autoridad suficiente para fusionar**.
- El vínculo de dos propietarios **exige dos grants opacos de un solo uso, cada uno emitido tras una autenticación reciente e independiente**. Solo una función de servidor de confianza podrá emitirlos después de haber comprobado un login real. Cada token se almacena como SHA-256, expira a los cinco minutos y se consume en la misma transacción que la migración de proyectos y aliases.
- Si se vinculan propietarios A+B: proyectos de ambos se conservan con idénticos UUID, `recipe_json`, revisión y timestamps. No se fusionan automáticamente proyectos con títulos iguales (son trabajos diferentes). El proveedor queda asociado a owner A y el alias B se documenta.
- La **sesión antigua del alias** no debe seguir usándose tras un merge: el futuro orquestador tendrá que revocar o transformar sesiones y reiniciar estado del worker; esto no se ha cableado aún y por eso esta pieza no está accesible desde la beta.
- Conflicto de proveedores, grant incorrecto/reutilizado/caducado, link repetido y creación de identidades por simple email coincidente: rechazo o separación segura.

## Lo que queda explícitamente por hacer antes de beta con contraseña

1. Diseñar y conectar proveedor email saliente independiente de nube, con plantillas y límites antiabuso, enlaces de verificación de un uso y caducidad, protección contra enumeración, recuperación de contraseña y revocación de sesiones.
2. El registro de contraseñas debe permanecer **pendiente** hasta verificar control del buzón; el lab `urano/http_auth.py` **no se puede montar sin más** en la aplicación C8.
3. Orquestador de vinculación segura en la sesión real: primero reautenticación de ambas identidades, consentimiento del propietario, creación de ambos grants **solo en servidor**, transacción, invalidación de sesiones antiguas, resolución posterior de aliases. Esta interfaz no acepta `owner_id` desde el navegador ni contraseñas desde la URL.
4. Migración cuidadosa de datos anteriores: `owners.sqlite3` de Google y `accounts.sqlite3` del lab son **fuentes distintas** a `projects.sqlite3`; preparar backup y migración probada **sin editar ni sobrescribir las DB de la beta en ejecución**. No introducir una segunda fuente de verdad para `owner_id`.
5. UI de elección Google/contraseña, cuentas vinculadas, ayudas y estados de verificación. Mismo dashboard (si finalmente es la página posterior al login). Tests con dos usuarios reales y sesión expirada, no solo pruebas de repositorio.

## Companion: botón de descarga real

Se comprobó `main` (10-11-2026): existe instalación macOS con `companion/Install Montara Companion.command` e `install.sh` (histórico), y `companion/windows_support.py` con pruebas Windows; **no se ha verificado un paquete instalador firmado y distribuible de Windows y macOS listo para descarga pública desde Pages**. No proporcionar a un visitante un botón engañoso ni un comando que ejecute `curl|bash` de `main` como si fuera el instalador final. La futura página debe usar un catálogo de releases/versiones por OS y arquitectura con URL HTTPS de artefacto fijado, hash SHA-256, instrucciones, permisos y versión mínima compatible con el servidor; ocultar o deshabilitar la descarga del OS sin artefacto verificado. No es requisito para ejecutar estos tests de identidad.

## Validación

`PYTHONPATH=tests python -m pytest -q tests/test_owner_identity_links.py` — cinco tests completos: contraseña→Google, Google→contraseña, conflictos y pruebas caducadas, sin deduplicación solo por email. Los tests adicionales de Google C1/C4/C8 y U12 deben pasar antes de integrar. **No acredita** que exista login público email+contraseña ni recorrido Editor/Companion completo.

## Puertas de producto y arquitectura

- Mantener una identidad lógica independiente de Cloudflare/GCP/Vercel; llevar el catálogo/registro por migraciones a PostgreSQL si llegan varios nodos de control, sin mover originales.
- Preparar el emparejamiento con Companion por identidad/proyecto y **origen del sitio autorizado**. Evitar que una instalación local se vincule a un proyecto que no pertenece a la sesión real.
- La portada ya contiene el enlace Google en la rama de integración (I7), pero el proyecto de Pages desplegado sigue siguiendo la rama histórica C8; no modificar ese ajuste sin comprobar build/deploy de la portada.

**Estado final:** fundamento de datos protegido por tests, pendiente de wiring de autenticación y verificación de email. No se ha activado nada en producción ni tocado `main`.
