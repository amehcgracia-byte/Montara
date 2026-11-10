# I10 — Acceso estándar y decisión de ejecución por propietario

**Fecha:** 2026-11-10. **Objetivo:** un recorrido claro, sin prometer email/password antes de verificarlo; consolidar cerca de `main` sin introducir un editor multiusuario inseguro.

## Incidencia verificada al iniciar sesión

La VM se reinició a las 12:59:58 UTC y los dos servicios FER arrancaron automáticamente. El túnel había registrado errores `unable to dial tcp to origin [::1]:8115`, porque Cloudflare VPC estaba configurado con hostname `localhost` y el backend escuchaba solo por IPv4. Se devolvió el destino del VPC Service al IPv4 explícito `127.0.0.1` **con el túnel en funcionamiento** y se obtuvieron 20/20 GET de `/healthz` HTTP 200. No se puede asegurar que no haya futuras incidencias sin monitorización tras reinicios. Este arreglo no modifica la IP pública de la VM ni servicios de Chema.

## UX minimalista de entrada

La portada enlazará a dos rutas diferenciadas del mismo **Owner público HTTPS**:
- **Iniciar sesión** → `/login`.
- **Registrarse** → `/register`.

Ambas ofrecen **Continuar con Google** (único método disponible para testers autorizados). Email+contraseña se indica como **en preparación**, sin formularios ni registro falso. Son páginas del backend y comparten su protección de Host/scheme, CSP, cookies y anti-cache. La URL `/` mantiene la redirección Google original por compatibilidad con enlaces ya compartidos. Una sesión existente que visite la elección debe ir directamente a `Mis proyectos`.

**Estado:** primer paso de UX, no login email/password en producción. I8 ya aporta la reconciliación de propietario (doble prueba) a nivel de SQLite, pendiente de login de correo verificado, recuperación segura, sesiones y migración. El enlace a `Companion` debe esperar a un artefacto de instalador verificable, no a un ZIP o script provisional como producto final.

## Qué eran los laboratorios Docker de URANO

U13D2B (#95–#98) probó **contenedores Docker reales en CI** con dos carpetas sintéticas, sin acceso cruzado, sin red, rootfs readonly, capabilities dropped, usuario no-root, imagen fijada por digest, montaje exclusivo de workspace, límites CPU/RAM/PIDs y limpieza. U16B (#128) validó **dos Engines reales abriendo proyectos en paralelo** en contenedores aislados, con identidades Google firmadas en laboratorio. U16B usó permisividad `0777` en carpetas sintéticas para que el UID del contenedor pudiera escribir; ese permiso no se admite en producción.

- Un *owner* lógico de SQLite (UUID) no es una sesión Linux de escritorio. En producción un administrador de trabajos de confianza resuelve ID → workspace y ejecutor; la petición del navegador no elige rutas.
- Cada ejecutor debe ver **solo** su workspace privado, los recursos compartidos estrictamente de lectura necesarios (código, librerías), sockets necesarios y ficheros temporales aislados. Los originales del usuario permanecen en Companion, no dentro de carpetas accesibles por servidor. La VM comparte kernel, CPU, RAM, almacenamiento y red física; Docker no es una VM completa.
- Con CPU/RAM/PID limitados por cgroup, no se garantiza un número de usuarios sin medir carga Engine vs Companion. El overhead de contenedor puede ser pequeño, pero arranque de proceso, `FFmpeg`, imágenes y cachés sí tienen costes reales; medir la solución concreta.
- El acceso al socket Docker equivale a privilegios sensibles; **NO** montarlo en contenedores de usuario ni exponerlo desde HTTP. El controlador de confianza debe evitar comandos/rutas arbitrarios.

**Decisión de referencia:** elegir como *primer candidato práctico* el contenedor por propietario compatible con los contratos Docker ya probados. Es el trayecto con más pruebas y menos rediseño frente a hacer ahora un nuevo provisionador por UID Unix; no se declara ganador absoluto ni se instala Docker en GCP sin un gate operativo. La infraestructura futura podrá cambiar de Docker a LXD/UID si el benchmark, costes o permisos del host lo justifican: mantener `ExecutorBackend` como frontera para no acoplarlo a Cloudflare, Vercel o GCP. Tampoco se obliga a crear un contenedor por petición: cada trabajo puede utilizar worker persistente temporal y limpieza segura.

## Gate hacia main

Preparar **una PR de integración revisable con Chema** después del flujo mínimo, sin mezclar componentes de diseño y sin fusionar sin su aprobación. El núcleo Owner ya funciona separado en Cloudflare; el editor clásico de `main` permanece intacto. Los contratos de autenticación de I8 y Engine de I4/I5 se conservan como módulos hasta contar con E2E real y prueba negativa de aislamiento del host.

## Validación esperada

- Offline: tests de nuevo HTML de elección y CSP, rutas `/login` y `/register` seguras, compatibilidad `/`, pruebas C8 y build Pages; no OAuth real simulado en producción.
- Despliegue: primero el backend con estas rutas, luego actualizar Pages, evitando enlaces rotos. Comprobar 200/303/401, 20 peticiones de salud, ausencia de fuga de secretos y la recuperación tras reinicio sin detener Chema.
- Manual: cuenta tester Google → `Mis proyectos` → persistencia después de otra sesión. Todavía **no** se declara recorrido Engine/Companion.
