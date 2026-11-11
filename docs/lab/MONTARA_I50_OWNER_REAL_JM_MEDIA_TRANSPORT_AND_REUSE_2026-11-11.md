# MONTARA — Etapa 5: integración Owner + editor JM + subida privada (I45–I50)

**11 de noviembre de 2026** · Rama de trabajo: `fernando/integracion` · **LAB PASS; NO desplegado ni fusionado**.

## Resultado resumido

Se ha superado el mayor bloqueo de arquitectura del vídeo: **el editor original de Chema y su Engine pueden operar juntos en un proceso privado por proyecto**, iniciado bajo demanda, con su HTML/JS/CSS originales, su protocolo de subida original y el borrador Stage asociado al UUID del Owner. La app auténtica ha funcionado desde una copia TEMPORAL de la rama JM `fix/jm-native-video-save-project-recovery-20261110`, con Engine inmutable `b5e48317ef85225f901adc69af8cc17aa8146880`. Sin segunda UI, sin segundo uploader y sin modificar el submódulo Engine.

La comunicación multimedia está diseñada sin pasar vídeos por el broker root: este comprueba SQLite Owner sesión/CSRF, propietario/proyecto/generación, ledger y PID/UID/cgroup; abre el socket HTTP Unix privado del worker y entrega **una conexión AF_UNIX ya establecida mediante SCM_RIGHTS** al servidor web. El servidor web puede transmitir peticiones HTTP/archivos DIRECTAMENTE por el descriptor. Los originales del usuario permanecen locales por defecto; no se ha probado aún el Companion Windows en este recorrido.

## Piezas concretas nuevas

1. **`urano/original_jm_owner_assets.py`**: muestra HTML y assets originales de Chema bajo una ruta privada por UUID y sesión Owner **sin arrancar el Engine**. Se probó con assets reales de la rama JM: index de 41.905 bytes, `montara.js` de 184.474 bytes, `companion.js`, CSS y Push; todos HTTP 200. Un proyecto de otra cuenta: 404. Opcional en `create_owner_api(original_jm_web_root=...)`; la beta actual NO pasa ese parámetro.
2. **`urano/first_valid_upload_gate.py`**: middleware WSGI opcional que dispara una llamada a la autorización de Engine **solo antes de una subida válida** (`/api/v1/wizard/upload` o `/montara/uploads`); consultas y navegación no arrancan nada. No absorbe la carga de vídeo ni crea una segunda vía de entrada.
3. **`urano/private_owner_admission.py` + `owner_broker_preview.py` + `private_broker_service.py`**: operación `ensure_owner`, autenticada dos veces, idempotente para el mismo proyecto/generación. Solo reutiliza un worker que aún exista y se pueda verificar; nunca sustituye uno con estado incierto. Entrada opt-in `POST /urano/v1/projects/<UUID>/ensure`, sin botón visible de Engine.
4. **`urano/private_editor_connect_admission.py`, `private_editor_fd_handoff.py`, `owner_private_http_client.py`**: concesión exacta de descriptor del socket del editor JM, con sesión/CSRF/Owner/generación y `SO_PEERCRED` (PID+UID), cgroup systemd, unidad guardada en ledger, socket 0600 y directorio privado 0700. Se probaron `sendmsg`/`recvmsg` y flujo real de ~1,5 MB por HTTP POST **sin pasar por el broker**. El servidor web aún necesita el gateway autorizado que exponga las rutas de edición con alias de proyecto de forma segura; **no hay un proxy global inseguro desplegado**.
5. **`urano/full_jm_worker.py` + opción `--jm-bundle`** en el launcher existente: permite ejecutar la app completa de Chema dentro de una unidad `systemd DynamicUser` de un proyecto, cuando el operador instale un bundle JM `/opt/montara/bundles/jm-<SHA>` raíz, de solo lectura, junto al Engine `engine-<SHA>`. Reutiliza rutas y la app originales, el WSGI Unix privado, y conserva el UUID original al hacer el primer `/wizard/draft`. No crea otro Engine Flask ni reemplaza el Engine instalado. La ruta JM es **opt-in**, por defecto sigue I26 sin alteraciones. El marcador `ready` solo se emite cuando los dos sockets locales han hecho `listen()`. Metadata `project.json` ya no se sobrescribe al iniciar si existe.
6. **`urano/restricted_systemd_broker.WorkerResourceProfile`**: CPU %, RAM y máximo de tareas configurables desde argumentos de arranque OPERADOR, no desde HTTP. Históricos defaults I26 (768M, 100% CPU, 64 tareas) preservados; se probó perfil 4 GB/400% CPU/256 tareas. No se presupone Google Cloud, Cloudflare, 4/8 vCPU, Azure, Oracle o AWS. El adaptador `systemd` sí presupone Linux; la lógica de Owner permanece portable.
7. **Vallado de fuentes** en `urano/owner_first_stage_wizard.py`: el primer borrador original JM acepta únicamente rutas verificables del Upload interno del worker (WizardUploads o carga reanudable completada en Uploads); nunca rutas externas, symlink o vídeo incompleto. Protege también reabrir proyecto existente sin sobreescritura silenciosa.
8. **Límite remoto**: el worker JM establece un token aleatorio local de modo remoto antes de cargar la app, de forma que el módulo `resumable_upload.py` original conserva su techo remoto de **256 MiB por fichero** y no el límite de 30 GiB de una instalación de escritorio. El fallback con originales sigue existiendo para pruebas explícitas; archivos originales mayores que ese límite NO podrán usar esa vía hasta establecer otra política protegida.

## Comprobaciones ejecutadas

- **55/55 PASS** en las regresiones unitarias agrupadas: políticas de recursos I25, broker I26, autorización Owner I27, FD kernel real, client HTTP, activación al subir, editor assets, Stage borrador privado. Test suite en `/tmp` de la VM, sin despliegue.
- **I45 PASS**: aplicación JM auténtica, Engine real, subida por `/wizard/upload` de MP4 sintético 640×360 de 3 s generado con FFmpeg, ensure inyectado y Stage draft conservando UUID. La activación de prueba utiliza callback simulado; el broker real se probó por separado.
- **I49 PASS**: proceso Python SEPARADO con app/HTML/JS/Engine originales, dos sockets Unix privados, subida de MP4 sintético real y borrador Stage sobre Owner UUID. No se instaló unit systemd.
- **I50 PASS**: dos procesos JM simultáneos con UUID y carpetas distintas, A sube y registra un proxy, B intenta usar su ruta y recibe **HTTP 400**; B permanece sin vídeos registrados. Comparten UID de laboratorio, por lo que esto NO equivale a aislamiento físico `DynamicUser`.
- **I48 PASS**: HTTP 200 para GET del editor y POST de ~1,5 MB por descriptor SCM_RIGHTS; root solo maneja el frame de autorización <384 bytes. Generación equivocada se rechaza.
- Se mantuvieron activos y sin modificaciones el Owner portal y su túnel. `main` de Chema seguía en `765a34c` en la última consulta. Ninguna prueba real Windows, navegador OAuth → completo JM, export final, Push ni Show dentro del nuevo gateway fue realizada.

## Lo que falta para entregar el turno a Fernando

**A. Puerta web autenticada de operaciones JM.** La UI original usa rutas absolutas `/api/v1/*` y `/montara/*`; debemos transmitir un **contexto por pestaña de UUID Owner** y CSRF en todas sus llamadas (también uploads reanudables, HEAD/range/preview) sin cambiar ni perder los pasos centrales Stage/Push/Show. El servidor debe autorizar cada operación, obtendrá el descriptor FD root-broker por Owner+generación y transportará los bytes en streaming. No es seguro usar un único proyecto activo por cookie de cuenta si hay varias pestañas.

**B. Bundle JM reproducible y systemd DynamicUser real.** El bundle JM `jm-<SHA>` ha de empaquetarse de forma inmutable a partir de `main` Chema o rama candidata explícitamente fijada; incluir enlace al Engine EXACTO; probar con usuarios Linux distintos, montajes read-only, permisos 0600, cgroup, recuperación tras reinicios, límite 256MiB y política de limpieza. No tocar servicio root actual hasta pasar esos gates.

**C. App y Companion.** Reusar `tests/e2e_native_stage.py` y Companion actual (Windows/Mac), comprobar contrato de proxy versión 3 y originales locales, carpeta de proyecto elegible, render MP4 local y recuperar una exportación interrumpida. No subir originales por defecto. Mantener fallback manual de laboratorio; revisar límites y seguridad antes de permitir ensayos grandes.

**D. UX definitiva.** Mantener logo izquierda, subfases Stage de Chema en el centro, `Mis proyectos` junto al logo y perfil derecha. Mostrar editor sin Engine, iniciar solo en primera subida válida o primera operación que necesite cálculo. Idempotencia sin botón de Engine.

**E. Probar dos propietarios con aislamiento systemd real**, más Stage/Push/Show, navegador con Google, proxy Companion y render hasta MP4; solo entonces invitar a Fernando a probar Windows.

## Riesgos abiertos explícitos

- `/run/<unit>/Projects/<UUID>` es almacenamiento **efímero** de un unit systemd. El Companion local guarda datos finales, pero la restauración transparente de metadata remota tras reinicio requiere un diseño de persistencia/re-hidratación por propietario. **No prometer recuperación completa todavía.**
- El broker root actual está marcado **LAB ONLY**; los cambios de esta rama no están instalados. No dar por hecha la funcionalidad de FD en el broker en producción.
- No se debe exponer directamente el socket JM del worker ni conectar el JS original a un Engine compartido. No hacer proxy HTTP genérico desde el navegador con un socket elegido por él.
- No duplicar ni modificar `web/montara.js`, `companion.js`, `engine/`, `mixer/` o `main` de Chema para cerrar artificialmente una etapa.

## Adenda de endurecimiento: subida válida y arranque automático

Se reforzó `urano/first_valid_upload_gate.py`: el POST inicial con bytes debe declarar un nombre de formato de medios reconocido y longitud positiva; el inicio de la carga reanudable debe aportar metadatos JSON pequeños válidos (nombre, tamaño acotado, huella SHA-256). **Una subida malformada devuelve HTTP 400 y no ejecuta ni deja pasar el arranque del Engine**. El JSON de metadatos se devuelve intacto al handler original mediante un stream repuesto; nunca se leen ni almacenan en el gate los bytes de vídeo. El callback de arranque no es el broker real en los ensayos de media de I45, pero el contrato `ensure_owner` y la autorización root por sesión/CSRF se han probado independientemente.

La prueba unitaria `test_urano_first_valid_upload_gate.py` quedó en **6 PASS** tras añadir casos de rutas maliciosas/metadatos inconsistentes. Las suites anteriores de recurso, root broker, Owner y FD sumaban 55 PASS antes de esta adenda (56 casos acumulados al añadir el nuevo). **No se ha desplegado nada** en los servicios activos.
