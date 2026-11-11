# MONTARA I35–I37 — Lectura Stage real mediante sesión Owner y dos canales Unix

**Fecha:** 2026-11-11. **Rama:** `fernando/integracion`. **Estado:** PASS en laboratorios locales aislados. **No desplegado, no fusionado, no aprobado para usuarios reales.**

## Avances comprobados

1. `tests/urano_i35_real_engine_stage_socket_lab.py`: carga el **Engine auténtico** desde el bundle inmutable instalado (`engine-b5e48317ef85225f901adc69af8cc17aa8146880`), crea un proyecto temporal y abre `/api/v1/wizard/projects/open` con el cliente interno del motor. Consulta Stage mediante **AF_UNIX real**; estado real devuelto: `ingest, sync, cut, edit, export = pending`, `camera_count = 0`. Sin medios.
2. I34 corregido: marcador `ready.json` solo después de `bind/listen` del socket para evitar que el broker declare Engine listo antes de poder leer. Broker incluye `generation` durable en parámetros del worker. Los módulos de ejecución siguen bajo `urano/`; **ninguna unidad systemd activa ha sido sustituida**.
3. I36: `GET /urano/v1/projects/<UUID>/stage-status?generation=N` en Owner beta, **solo** bajo su bandera experimental existente. Flask verifica sesión, CSRF y propiedad/modalidad; el broker privado vuelve a verificar token+CSRF+propiedad contra SQLite en modo lectura, el ledger persistido comprueba owner, proyecto, estado `running`, generación y unidad; el transporte vuelve a comprobar PID+UID de socket de proceso y el worker devuelve solo estados/cantidad. Negaciones: sesión revocada, otro propietario, modo distinto, unidad incorrecta, worker cambiado, generación antigua, JSON o campo arbitrario.
4. `tests/urano_i37_real_owner_to_stage_lab.py`: **prueba completa física de transporte local** Owner Flask HTTPS test client → socket Unix del broker → ledger real y catálogo readonly → socket Unix del worker → **Engine real** → respuesta HTTP 200, con HTTP 404 para proyecto ajeno. Salida: `real_engine_open=true, broker_unix_socket_verified=true, worker_unix_socket_verified=true, foreign_project_http_denied=true`, y las cinco fases en `pending`.
5. I36 pruebas unitarias y regresión: **29 PASS** para módulos I36/I27/Unix/ledger; suite I35 anterior 8 PASS; I37 físico PASS. CI offline del contrato creada. El test I37 no se ejecuta automáticamente en GitHub Actions porque los runners no disponen del bundle real de la VM.

## Límites importantes

- Todos los procesos del laboratorio I37 comparten el mismo usuario del host, aunque la comunicación sea **AF_UNIX real**. **No** verifica la separación de UIDs/cgroups real de systemd DynamicUser de producción, que aún exige pruebas específicas y endurecimiento de controles.
- I37 usa una sesión **sintética local emitida por SessionStore**; no realiza OAuth Google real. La ruta Google OAuth se verificó anteriormente por separado, pero no se ha demostrado desde navegador un flujo integral con Google + Engine + edición.
- `/stage-status` es **solo lectura**: no sube proxies, sincroniza cámaras, corta, guarda el editor de Chema, ni produce MP4. Las operaciones multimedia no deben exponerse mediante un proxy genérico a `/api/v1/*`.
- Aún no se ha montado la interfaz HTML/JS auténtica de Chema en Owner, no se ha probado Companion Windows con esa interfaz y no se ha validado exportación local.
- El `main` consultado al comenzar este bloque permanecía en `765a34c`; Chema mantenía su trabajo principal en rama separada. Revisar justo antes de integrar.
- Servicios actuales 8115/Owner/broker permanecen sin cambiar. Todos los datos experimentales existentes, dos cuentas Linux y laboratorios históricos se conservan.
- La separación arquitectura/ejecutor continúa: `private_stage_snapshot_bridge.py` acepta `PrivateSnapshotTransport` abstracto; Unix/systemd es implementación Linux, no bloqueo con GCP, Azure, Oracle, AWS ni Cloudflare. Cotas `CPUQuota=100%`, `MemoryMax=768M`, `TasksMax=64` del **laboratorio** no se trasladarán como parámetros universales del producto. Se requerirá perfil de recursos configurable/admisión con telemetría.

## Próxima integración necesaria (no marcar como terminada todavía)

1. Validar en **systemd DynamicUser real** el canal de lectura con UIDs/cgroups diferentes, permisos del socket y cierre/recuperación sin afectar a servicios activos (laboratorio segregado).
2. Encajar el **editor JM verdadero**, no el estudio temporal I28: servir los assets originales desde la sesión Owner, selector contextual por modalidad, traducir las operaciones Stage/Push/Show a comandos **permitidos y versionados** del worker privado. No exponer Engine compartido.
3. Companion como dependencia obligatoria para medios pesados: versión Windows/Mac, HTTPS CORS con orígenes exactos, proxy, recibos/manifiestos y receta del mismo Engine, render MP4 local; repetir con dos propietarios y reinicios.
4. Cuando pase la prueba offline + real E2E, **Fernando valida Windows/browser**; solo entonces preparar el corte contra la nueva `main` de Chema, sin fusionar antes.

## Comandos de laboratorio (solo autorizados)

Ejemplo en VM, con Python del bundle y checkout temporal de la rama, `PYTHONPATH` apuntando al código de la rama, `--execute` y bundle pinneado. **No utilizar en servicios activos ni en ordenadores de usuarios.** Los scripts fallan sin `--execute`; usan `TemporaryDirectory` para no modificar proyectos de verdad.

## I37: integración física completa del camino de lectura (verificado después)

Se ejecutó `tests/urano_i37_real_owner_to_stage_lab.py --execute` en la VM con el Engine pinneado `b5e48317ef85225f901adc69af8cc17aa8146880`, sin iniciar servicios de producción y sin vídeo. **PASS:** cliente HTTPS de Flask con sesión Owner local y CSRF -> socket Unix de broker auténtico en `/tmp` -> revalidación de Owner y catálogo readonly -> ledger real -> socket Unix de worker -> motor JM auténtico -> HTTP 200 con Ingest/Sync/Cut/Edit/Export en `pending`. Proyecto de otro propietario devuelve **HTTP 404** sin hablar con el broker.

Salida de laboratorio: `real_engine_open=true`, `private_owner_session_verified=true`, `foreign_project_http_denied=true`, `broker_unix_socket_verified=true`, `worker_unix_socket_verified=true`, `physical_multiuser_isolation_verified=false`, `google_oauth_verified_in_this_lab=false`, `companion_video_export_verified=false`.

**La prueba I37 usa una sesión de laboratorio y todos los procesos bajo el mismo UID:** no equivale a Google OAuth real desde navegador ni a systemd DynamicUser real, y aún falta el transporte de las operaciones **de escritura** del editor Chema, proxies y exportación a Companion. Ninguna parte de la beta pública se ha desplegado.
