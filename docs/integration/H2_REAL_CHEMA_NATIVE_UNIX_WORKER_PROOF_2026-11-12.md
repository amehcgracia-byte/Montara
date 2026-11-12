# Hito 2 · Validación del worker nativo de Chema y socket privado
**12 noviembre 2026 · Rama `fernando/chema-native-owner` · Sin despliegue.**

## Resultado práctico obtenido
En la VM real de GCP se ha probado el **paquete original de Chema** (`jm-14cce126137a0ef30a987351ff35b750f54473bd`) con su **Engine/CPU original ya fijado** (`engine-b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b`) y nuestro montaje nativo de workspace. La prueba se ejecutó como usuario SSH sin utilizar el worker de ningún Owner; no hubo cambio de servicios, broker, main, Cloudflare ni datos personales.

La VM presenta una particularidad: `/opt/montara-engine` y `/opt/montara-jm` están montados en el **namespace del worker real**, no en la sesión SSH. Para comprobar el paquete sin entrar en el worker activo se utilizó una **copia temporal de un único `app.py` original**, con enlaces simbólicos temporales a los bundles físicos inmutables; no se editó ni `app.py` ni ningún paquete fijado.

- **Prueba real de New/Draft/Latest:** con un MP4 de un segundo y un WAV de un segundo creados por FFmpeg en `/tmp`, `create_montara_app` original y `bind_native_owner_application` dieron `New HTTP 200`, `Draft HTTP 200`, `Latest HTTP 200 kind=project`. Tras llamar **New otra vez**, Latest siguió encontrando el proyecto guardado. Stage snapshot se mantuvo dentro del workspace.
- **Prueba real de socket Unix:** `create_private_jm_wsgi_server` y `VerifiedJMUnixConnection` del código existente de integración comprobaron `jm-editor-http.sock` con modo **0600**, PID/UID del proceso y HTTP **200** en `wizard/status`, `wizard/projects/new`, `wizard/draft`, `montara/recovery/latest`. El socket se cerró y se eliminaron sus datos temporales. **No significa que el broker público ya publique esas rutas**.
- **Regresión en Oracle:** con el nuevo `native_owner_worker_service.py` y `tests/test_native_owner_worker_service.py`, se verificó por socket AF_UNIX que *no se anuncia ready* antes de comprobar ambos sockets, que los permisos son 0600, que una generación inválida falla y que fallos del listener no se ocultan. **54 pruebas y 41 subpruebas PASS**.

### Lo que sí está demostrado

El mismo Chema que llegará a `main` puede iniciar un proyecto, generar draft y recuperar Latest sin catálogo de proyectos y con raíz privada; el transporte privado real soporta esas operaciones y las comprobaciones de identidad de Unix.

### Lo que NO está demostrado todavía

- La variante nativa **no está instalada como servicio** en `montara-i26-broker.service`; el worker activo todavía usa `OwnerFirstStageWizard` y crea/abre una carpeta UUID artificial. `native_owner_worker_service.py` es una composición opt-in probada con socket, pero su función debe ser llamada por el worker supervisado que ya tenemos, sin cambiar los cgroups ni la forma de autenticar.
- No hay aún pasarela completa de editor HTTP/CSRF desde Chrome ni dominio de validación.
- El MP4 pequeño generado por FFmpeg se utilizó **solo como entrada de prueba para Draft**. No se ha renderizado ni aprobado un MP4 final de Stage. La aceptación E2E y dos usuarios humanos siguen pendientes.

## Siguiente conexión mínima

**Worker, sin duplicación:** en el worker existente `private_broker_worker.py`, reservar un modo de arranque nativo que ya no construya `Projects/<workspace_uuid>/project.json`; conservar la reserva exclusiva Owner/generation/StateDirectory/UID/cgroup. En `full_jm_worker.py`, tras las mismas validaciones de bundles, Python/Mixer y tokens, sustituir solo el **montaje antiguo** (`OwnerFirstStageWizard`, auto-open y `OwnerStageNativeExport`) por `serve_native_owner_workspace(..., make_private_server=create_private_jm_wsgi_server, serve_stage_socket=serve_stage_socket)`. Es importante que la app provenga de `create_montara_app` nativa, que `data_root` proceda del **StateDirectory del broker** y que los métodos HTTP solo lleguen por la pasarela autorizada.

**HTTP y UI:** eliminar picker/segunda portada solo al conectar las rutas Owner autenticadas por sesión+CSRF y permitidas en el contrato nativo; mantener el original `web/` intacto. Todas las operaciones extra de Stage/Mixer/exportación requieren su propia cobertura y no se deducen de las cuatro llamadas de prueba.

**Legacy:** la primera activación de un Owner que tenga proyectos antiguos requiere comprobar el workspace por estado de broker/SQLite y carpeta real. `NativeOwnerWorkspaceRegistry` falla cerrado si existen proyectos; no migrar ni borrar archivos para hacer que la beta parezca nueva.

## Limpieza y operación
Las pruebas de GCP se realizaron en `/tmp/montara-chema-native-smoke.*` y `/tmp/montara-native-socket.*`, con `trap rm -rf` al salir y sin procesos persistentes. Los tests de Oracle utilizaron carpetas temporales `/tmp`. No se instalaron paquetes, no se creó otro venv, no se modificó la web original ni `main`. Preservar el Worker, Tunnel y la beta actual hasta que exista el nuevo entorno aislado de aceptación.


## Actualización de hito 2 — Entrada administrativa del worker supervisado

Tras la prueba con Chema real por socket privado, se ha implementado **la selección de la variante nativa desde el mismo broker root** sin modificar el comportamiento predeterminado de la beta:

- `native_owner_systemd_worker.py` + `urano/native_owner_systemd_entry.py`: entrada separada de la antigua, diseñada para ser **seleccionada por el operador**, nunca por el navegador. Valida los argumentos existentes del broker, el UUID del workspace, `STATE_DIRECTORY`, `RuntimeDirectory`, versión/generación, quotas de proxy y dependencia exacta entre los bundles Engine/JM. Conserva `PYTHONPATH` del mixer fijado y emite `ready.json` **solo tras haber comprobado ambos sockets**.
- `urano/native_owner_broker_policy.py`: whitelist de tres rutas exactas de script, de las cuales las dos originales siguen permitidas. La nueva solo admite JM pinneado y exige ejecutable Python regular propiedad de root, sin escritura por terceros ni enlaces simbólicos. El broker conserva la versión anterior como default.
- `urano/private_broker_service.py`: portado selectivamente del trabajo revisado de `fernando/integracion` y conectado a esa whitelist. No se cambió su política de autorización, ledger, cgroups ni comandos `systemd-run`.
- Se portaron también **solo las dependencias de seguridad realmente utilizadas** del broker/Unix (ledger de reservas, verificación de credenciales y procesos, políticas systemd, handoff del descriptor, límites JM/Engine y snapshot), sin incorporar dashboard ni selector multiproyecto. El pequeño soporte atómico opcional de `recipe` de `ProjectCatalog.create` se recuperó porque las pruebas de seguridad posteriores dependían de él. Eso no habilita catálogo visible.
- `tests/test_native_owner_supervised_launch.py` ejercita el constructor de comandos del **broker real**, sustituyendo únicamente la ejecución privilegiada `systemd-run` y el marcador del kernel. Demuestra la línea de comandos nativa, todos los límites y el comportamiento de la ruta antigua, **sin iniciar ningún servicio**.

### Regresión acreditada

- **66 pruebas Python nuevas + 84 subpruebas** PASS (incluyen los dos casos del comando de arranque).
- **44 pruebas históricas de I24/I25/socket/ledger + 42 subpruebas** PASS, ejecutadas contra las versiones portadas en la rama limpia.
- Paquete original Chema + Engine nativo en GCP: New/Draft/Latest y socket privado `0600`, HTTP 200, verificados en la prueba anterior; no se confunde con ejecución de un worker systemd.
- `web/` original de Chema no se modifica. **El broker instalado en GCP no ha cambiado y continúa utilizando el worker anterior**.

### Condición necesaria para terminar el hito 2 operativo

Realizar **una única** validación supervisada del nuevo script, pero solo con un contexto Owner de validación aislado de los datos actuales. Primero deben estar presentes en el despliegue sus archivos revisados y dependencias fijadas, y debe definirse la forma de habilitarlo sin sustituir al broker actual, sin interrupción ni creación de un segundo servicio persistente. No reiniciar ni limpiar el worker activo para forzar la prueba.

La comprobación de autorización externa Chrome → Google Owner/CSRF → broker → WSGI + la sustitución del picker corresponden al hito siguiente y **no están terminadas**.

## Actualización final — prueba systemd real aprobada (12 noviembre 2026)

La validación técnica aislada del arranque systemd **ya se ha completado**. Ver `docs/integration/H2_SYSTEMD_NATIVE_ACCEPTANCE_2026-11-12.md`: unidad transient con DynamicUser/cgroup, ambos sockets 0600, New y Stage status reales, limpieza acreditada y 67 pruebas PASS. **Pendiente para el hito 3:** activar el worker a través del broker y la sesión Owner real, sin tocar todavía la beta existente. No interpretar esta aceptación aislada como un despliegue completo.
