# URANO U19 — Sesión Google → worker Engine privado (08-11-2026)

**Objetivo limitado:** enlazar las sesiones privadas de U15/U16A con el control de ejecución que ya se validó en contenedores reales U16B. Este incremento NO crea una plataforma pública, no expone Engine genérico ni demuestra aún el Stage/Companion distribuido final.

## Código de integración

- `urano/owner_runtime_controller.py`: registro de infraestructura **solo de confianza** para un `ContainerWorkerBridge` de U13 **por propietario**. No se puede provisionar ningún contenedor desde una petición HTTP. Cada owner tiene su propio bloqueo para que cambios de proyecto del mismo dueño no se solapen, **sin serializar a los demás**.
- `urano/http_owner_runtime.py`: tres endpoints opt-in bajo `/urano/v1/runtime`:
  - `GET /state`: estado genérico del único worker asignado a la sesión. Sin rutas ni identificadores internos.
  - `POST /projects/<UUID>/activate`: sesión opaca no revocada, CSRF y `Origin` HTTPS exacto, cuerpo **vacío**; valida que el propietario de la sesión tiene ese UUID catalogado **y** que el proyecto está vinculado a su carpeta Engine permitida **antes de arrancar Docker**. Abre únicamente dentro del worker asignado. Nadie puede elegir owner, nombre de carpeta, Docker image, Docker command o worker.
  - `POST /close`: cierra solo el worker de la sesión y exige confirmación de retirada por parte del bridge antes de ofrecer estado libre.
- `urano/google_lab_app.py`: parámetro **opcional** `runtime_controller`. Ruta inactiva salvo que infraestructura proporcione explícitamente un controlador y `engine_data_root`. No montada en la app Montara habitual, no hay botón de UI en producción ni cambio de despliegue.
- `tests/test_urano_owner_runtime_http.py`: sesión+cookie+CSRF+origen, owner extranjero denegado antes del arranque, logout y token revocado, payloads de owner/path ignorados o denegados, estado sin rutas ni permiso de render. Estado SQLite de guardia de activación **real**, con transporte Docker simulado. Incluye barrera para asegurar arranque paralelo de dos propietarios.
- `tests/test_urano_owner_runtime_docker.py`: gate pesado en runner GitHub **desechable**. Dos JWT de Google falso firmados y verificados dan dos UUID. Se crean proyectos reales según el esquema del Engine, dos carpetas privadas y dos contenedores Docker con red `none`, imagen pinned por SHA local y procesos Engine reales. Activación vía **Flask HTTP test client** de dos sesiones independientes, acceso extranjero rechazado antes de Docker y cierre aislado.

## Seguridad y alcance

- Cookies `__Host-montara-urano` emitidas desde el flujo Google de prueba, no peticiones con `owner_id`. `request.host_url`, `Origin` y `X-Urano-CSRF` deben coincidir para escritura.
- Estado y errores no devuelven carpeta Engine, ruta de disco, nombre del contenedor, identificador del proveedor Google, ni datos de proyectos de otro usuario.
- No se acepta cuerpo al solicitar activación; los recursos exactos del Engine se configuran **solo** en backend y están sujetos a los límites U13.
- Las rutas son **control plane limitado**. `render_access=false` y `companion_access=false` hasta tener un adaptador de trabajos/recetas/bytes con autorización de descargas y cancelación. No confundir `/activate` con poder editar vídeo desde un servidor remoto.
- Al cerrar un worker existente, errores de Docker que impidan demostrar retirada deben mantener el runtime bloqueado; no liberar nunca un contenedor que siga vivo.
- La provisión de worker es **memoria del proceso de laboratorio**; se necesita coordinación de varios servidores/servicios, reanudación ante caída del orquestador y control real de recursos antes de beta. El adaptador no crea automáticamente un worker de propietario al iniciar sesión.
- El test actual usa medios/carpetas **sintéticos** con permisos especiales para UID de Docker en un runner desechable. No copiar esos permisos a producción.
- **Sin peticiones a Google real, sin Mac Companion, sin Stage+export completo por dos cuentas HTTPS públicas, sin datos de usuarios y sin acceso a infraestructura real.** No se ha tocado `main`, 8101/8102/8103, GCP, Companion o el Engine de Chema.

## Integración y dependencias

Esta rama `fernando/urano-u19-owner-private-engine-activation` nace de U16C **#129**, apilada sobre #128/#127/#126/#125/#124. **No está integrada con** la rama de benchmarking local U18 **#133** (que va apilada sobre #132/#131/#130/#121). La futura integración debe ser selectiva, evitando duplicar archivos en U13 y preservando los cambios de Chema en `main`. No fusionar todo a ciegas ni desplegar directamente.

## Evidencia

Workflow `.github/workflows/urano-u19-owner-engine-activation.yml`. **No declarar PASS en Engine real sin confirmar CI del commit final.** El gate ligero con transporte simulado tampoco sustituye las pruebas con contenedor real.

## Siguiente puerta mínima

Un adaptador **de trabajo/receta de Stage y export a Companion**, solo para proyectos validados por sesión, sin subida del original completo y con cancelación y límites de recursos; después acceptance real de dos clientes físicos distintos conectados a laboratorio HTTPS. La política de fallback de subida de originales debe resolverse antes de beta comercial.
