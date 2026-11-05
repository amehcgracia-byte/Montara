# URANO U4B — auditoría de superficies HTTP, identidad y propiedad de medios

**Fecha:** 2026-11-05  
**Ámbito revisado:** código de la rama experimental `fernando/companion-windows-w1` de `amehcgracia-byte/Montara` (lectura puntual de rutas y guardas).  
**Tipo de evidencia:** inspección estática de código. **No se ejecutaron ataques, fuzzing, pruebas multiusuario reales ni auditorías dinámicas.**  
**Estado:** inventario U4B terminado; **no** es aprobación de seguridad ni implementación de autenticación comercial.

## 0. Resultado ejecutivo

El producto tiene **dos modelos de acceso válidos para pruebas, pero distintos de un SaaS multiusuario**:

1. **Vercel Sandbox:** `deployment/vercel/runtime.js` crea y recupera Sandboxes usando un identificador de sesión de 32 hexadecimales. `deploy/sandbox_entry.py` exige un cookie `montara_preview` con secreto de sesión, ofrece `/_preview/grant` validado y limita determinadas rutas y rutas de disco. Un Sandbox de la demo puede tener su propio disco; **no afirmar que la demo carece de aislamiento**.
2. **Linux privado:** `deploy/entry.py` comprueba HTTP Basic en `before_request` con un usuario/contraseña configurados. La instalación documentada está pensada para **un editor a la vez**, no cuentas simultáneas.

Dentro de esos entornos, las rutas de medios y trabajos **no muestran una capa propia de propiedad por cuenta**: los IDs de upload, sesión, mix y pack permiten encontrar recursos existentes sin una comparación visible contra `user_id`/`owner_id` en los módulos examinados. En las pruebas actuales esto no equivale automáticamente a una fuga entre usuarios, porque la sesión de Vercel y el acceso básico privado aportan fronteras externas. Sí es un **requisito de seguridad antes de compartir un mismo backend entre clientes**.

**Prioridad:** definir primero aislamiento/autorización por recurso para un SaaS compartido, sin destruir la sesión individual ni el motor existente.

## 1. Fuentes examinadas

| Archivo | Qué aporta |
|---|---|
| `deploy/sandbox_entry.py` | Cookie de preview con token y revisión de rutas dentro de la sesión |
| `deployment/vercel/runtime.js` | Identidad de Sandbox por sesión, recursos y límite de cuatro demos activas |
| `deploy/entry.py` | Autenticación Basic para único entorno privado |
| `app.py` | Construye la app Flask/Engine, registra rutas Montara y operaciones Mixer |
| `resumable_upload.py` | API completa de subidas fragmentadas y reserva de espacio |
| `full_session.py` | Sesiones musicales y transferencia de rangos/resultados |
| `push_pack.py` | Estado de packs/reels, cambios y descarga |
| `show_library.py` | Biblioteca reutilizable y acciones sobre elementos |
| `music_shelf.py` | Catálogo/importación de audio |
| `companion/companion.py` | Servicio local 127.0.0.1, rutas de lectura/escritura y control Origin |

No se ha revisado íntegramente el submódulo `engine/`, `mixer/`, todas las rutas de `Show`, ni la totalidad de la capa externa de Vercel. La tabla es **selección de endpoints sensibles inspeccionados, no inventario completo de Flask**.

## 2. Matriz priorizada de endpoints

**Leyenda**: `ENV` = protegido por puerta de despliegue si se ejecuta en `deploy/entry.py` o `deploy/sandbox_entry.py`. `OWN` = comprobación de propietario del recurso **en el handler inspeccionado**. `LIM` = límites conocidos por petición/archivo, que no son una cuota por cuenta. La ausencia de OWN a nivel de handler **no** demuestra ausencia de ENV ni exposición pública.

| Grupo y rutas | Acción / dato | Protección observada | Falta para SaaS compartido | Prioridad |
|---|---|---|---|---|
| `GET/POST /montara/uploads`; `GET/PUT/DELETE /montara/uploads/<upload_id>`; `POST .../finish` | Asignar almacenamiento, subir trozos, borrar incompleto, registrar medio | ENV; UUID hex32; validación de nombre/tamaño/fingerprint, `flock`; LIM 256 MiB preview o 30 GiB privado, reserva de espacio | No se identifica OWN en `lookup(upload_id)` ni deduplicación `name+size+fingerprint` por cliente; cuota/retención por cuenta; idempotencia entre proyectos | **P0** |
| `POST /montara/session`; `GET /montara/session/latest`; `GET /montara/session/<id>`; `POST .../<action>` | Crear/consultar/cancelar/modificar sesión musical | ENV; IDs hex12; `folder(job_id)` comprueba formato/existencia; `session_start` valida rutas dentro de data_root/fixtures | `latest` selecciona último del servidor, no del usuario; `folder` no verifica OWN; transiciones y cancelación por cuenta | **P0** |
| `POST /montara/session/<id>/local-result`; `POST .../originals`; `GET .../results.zip` y `GET .../result/<song_id>` | Asociar upload a sesión y entregar archivos | ENV; formato upload ID, `complete`, ruta bajo Uploads, ventana y estado de canciones; resultados restringidos al directorio de sesión | No se compara propietario de **upload y sesión** antes de mover/registrar material; acceso a descarga por usuario/proyecto | **P0** |
| `POST /montara/mix`; `GET /montara/mix/<id>`; `POST .../render`; `GET .../result`, `.../track/*` | Analizar, renderizar, descargar mezcla y pistas | ENV; `resolve_mix_sources` limita fuentes, mix_jobs en memoria por ID | OWN y cuotas/concurrencia por usuario; aislamiento de trabajos dentro de un proceso compartido | **P0/P1** |
| `POST /montara/push/packs`; `GET .../latest`; `GET/PATCH .../<pack_id>`; `POST .../export`; `GET .../file` | Crear, recuperar, editar/exportar reels | ENV; `PushPacks` valida IDs/estado; `latest` recorre almacenamiento global del runtime | OWN para pack/reel; `latest` específico por cuenta; cuotas de procesamiento y retención | **P0/P1** |
| `GET/POST /montara/show/shelf`; `POST .../<asset_id>/use`; `POST .../visibility` | Biblioteca reutilizable, copiar medios a proyecto y ocultar | ENV; ID de asset y catálogo de `data_root/ShowLibrary`; referencia de biblioteca del Engine | Decidir si biblioteca pertenece a proyecto, usuario o espacio compartido; OWN para leer/copiar/ocultar | **P1** |
| `POST /montara/music/import`, `/montara/music/link`; `GET /montara/music/file/<track_id>` | Importar y servir audio/licencias | ENV; comprobación de formato de ID en descarga y validación del enlace YouTube en importación | Propiedad y permisos sobre catálogo, límites de coste y tamaño, gestión de derechos | **P1** |
| `POST /api/v1/wizard/upload` y rutas `/api/v1/show/*` del Engine | Entrada de vídeos y medios auxiliares | ENV; `app.py` rechaza formatos de cámara específicos; la preview permite un subconjunto de Engine | Auditoría **separada del submódulo Engine** para autenticación, ownership y clasificación original/proxy | **P0 antes de multiusuario** |
| Companion `GET /health`, `POST /locate`, `POST /proxies`, `POST /projects`, `POST .../save`, `POST /video-renders`, `GET .../file`, `POST /mix-song` | Accede a originales, procesamientos y guardado local | Solo 127.0.0.1, regex de `Origin` para gran parte de GET/POST, IDs de fuente/proyecto; validaciones de ruta, nombre y tamaño en rutas | Autorización vinculada a una sesión de usuario y a un proyecto; confirmar excepciones de rutas sin `Origin` y controlar orígenes permitidos | **P0 antes de interfaz web pública real** |

Los riesgos P0 son **brechas de diseño para la futura arquitectura compartida**, no afirmaciones de explotación confirmada.

## 3. Hallazgos específicos y su alcance

### U4B-01 · Deduplicación global de upload (P0 en backend compartido)

`resumable_upload.py` busca registros existentes por **nombre + tamaño + fingerprint**, y devuelve el registro si coincide. No incorpora el identificador de usuario en esa comparación. El fingerprint se calcula sobre los primeros y últimos 64 KiB; **no** es una certificación del contenido total por sí sola.

**Riesgo futuro:** reutilización de una transferencia de otro usuario y revelación de metadatos de progreso si se permite compartir `data_root`. No se ha demostrado explotación entre Sandboxes, que cuentan con aislamiento externo.

**Prueba U4C:** dos identidades ficticias, misma descripción de archivo: la segunda no debe recuperar ni reanudar el registro de la primera. Confirmar la propiedad también en PUT/GET/DELETE/finish.

### U4B-02 · Identidad de sesión y rutas `latest` (P0)

`full_session.py` busca por fecha el último `session.json` del servidor; `push_pack.py` tiene otra ruta `latest` que ordena `pack.json`. Este comportamiento es razonable con una instancia/editor y no sirve como asociación usuario-proyecto dentro de un servidor común.

**Prueba U4C:** preparar dos sesiones/packs de propietarios diferentes y verificar que cada cuenta recupera solo su último trabajo, aun compartiendo ejecución.

### U4B-03 · Vinculación de export y upload (P0)

`full_session.py` valida que los rangos correspondan a una canción y que un upload esté completo y dentro de Uploads antes de moverlo a `exports` o registrarlo como original. Son controles de integridad importantes, pero no aparece una verificación explícita de **mismo propietario** entre el upload y la sesión.

**Prueba U4C:** subir un MP3 como usuario A e intentar enlazar su ID a un trabajo de B; debe fallar antes de leer/mover el fichero.

### U4B-04 · Mixer y recursos por ID (P0/P1)

`app.py` mantiene `mix_jobs` en memoria y permite consultar/trabajar con ID del job, y entrega pistas o masters. `resolve_mix_sources` limita rutas aceptadas; no es un token de permiso a nivel de cuenta.

**Prueba U4C:** al cambiar de identidad, `/montara/mix/<id>` y descargas deben devolver 403/404 uniformes sin procesar otro proyecto.

### U4B-05 · Biblioteca reutilizable Show y catálogo musical (P1)

`show_library.py` escribe un catálogo de `ShowLibrary` dentro del `data_root`, permite marcar elementos ocultos y reutilizarlos en un proyecto. Hay que decidir explícitamente si los medios son *privados*, *de proyecto* o *compartidos*, y comprobar ambos lados de la copia. Lo mismo aplica a importación de música.

**Prueba U4C:** biblioteca privada de A no aparece en B ni puede reutilizarse mediante ID; biblioteca compartida requiere permisos y procedencia documentados.

### U4B-06 · Protección local de Companion (P0 para producto público)

`companion/companion.py` escucha en localhost y valida `Origin` en operaciones normales. `GET /health` es intencionadamente accesible sin Origin; se permite además `GET /video-renders/<id>/file?download=1` sin coincidencia de Origin. El patrón predeterminado incluye cualquier subdominio con forma `https://[a-z0-9-]+.vercel.app` y determinados túneles `trycloudflare.com` (además de localhost).

**Precaución:** control de `Origin` **no autentica a un usuario ni autoriza un proyecto**; los IDs tampoco deben tratarse como sustituto de identidad. La excepción de descarga merece una prueba controlada de exposición y un rediseño con tokens vinculados a sesión. No se afirma vulnerabilidad explotada.

**Prueba U4C:** validar con orígenes permitidos y no permitidos, solicitudes sin Origin, métodos, descargas, y operaciones sobre proyecto ajeno simulado. Ninguna prueba debe intentar acceder a medios reales de usuarios.

### U4B-07 · Capas actuales de acceso: valoración correcta

- **Vercel demo:** `deploy/sandbox_entry.py` controla cookie/sesión, limita rutas del Engine y comprueba rutas absolutas de cuerpos JSON/queries dentro de su almacenamiento; `deployment/vercel/runtime.js` crea Sandboxes nombrados por sesión con límite de cuatro activos. No equipararlo a un backend abierto con un único directorio para todo el mundo.
- **Docker privado:** `deploy/entry.py` aplica Basic para un solo usuario/editor. No confundir esta puerta con sistema de cuentas.
- **Backend futuro:** cuando usuarios compartan proceso/almacenamiento se necesitarán identidad, permisos y aislamiento internos. Si se mantiene **un Sandbox por usuario/sesión** durante más tiempo, cambia el modelo de amenaza y de costes; evaluar antes de diseñar una base de datos central.

## 4. Contrato mínimo que debe plantearse antes de fusionar una infraestructura multiusuario

| Entidad | Campos mínimos propuestos | Regla |
|---|---|---|
| Cuenta | `account_id`, plan, estado, límites | La identidad proviene del servidor, nunca del JSON del navegador |
| Proyecto | `project_id`, `account_id`, fecha, estado | Todas las lecturas/escrituras prueban ownership |
| Media | `media_id`, `project_id`, origen (local-proxy, original-manual, segmento, remoto, biblioteca), hash, tamaño, retención | No confiar en nombre/extensión para distinguir proxy/original |
| Upload | `upload_id`, `account_id`, `project_id`, tamaño reservado, bytes, expiración, estado | Cada PUT/GET/DELETE/finish verifica propiedad y cuota |
| Job | `job_id`, `account_id`, `project_id`, tipo, estado, prioridad, límites | Verificación en status/cancel/download |
| Sesión Companion | asociación de cuenta/proyecto, token local de duración corta, permisos por acción | No usar solo `Origin`; no exponer caminos locales gratuitamente |

Esto es **propuesta de diseño**, no esquema existente ni decisión técnica aprobada.

## 5. Puertas de aceptación antes de publicar SaaS multiusuario

- [ ] Elegir aislamiento: **Sandboxes independientes por cuenta/sesión** frente a backend compartido con tenants; comparar coste, rendimiento y tiempos de activación.
- [ ] Identidad autenticada central y permisos de proyecto sin confiar en `account_id` cliente.
- [ ] Deduplicación de uploads aislada por propietario, cuota, expiración y limpieza.
- [ ] Relación transaccional entre uploads, sesiones y resultados, sin mover medios ajenos.
- [ ] Protección de `latest`, historial, packs, bibliotecas y descargas.
- [ ] Contrato navegador–Companion con autorización por sesión/proyecto; revisión de lista Origin y excepciones.
- [ ] Mantener opción manual de subir originales **solo tras consentimiento**, con límites de tamaño y cuotas; no convertirla de nuevo en fallback silencioso.
- [ ] Auditoría del submódulo Engine para rutas `/api/v1/*` y de integraciones Show/Mixer.
- [ ] Pruebas dos usuarios ficticios con aislamiento y regresiones Stage/Push/Show.
- [ ] No distribuir el paquete Windows con FFmpeg hasta revisión legal y aceptación de release.

## 6. Orden de trabajo recomendado

**U4C (siguiente):** especificar y ejecutar pruebas de aislamiento **sin datos personales** y en entorno de laboratorio. Primero validar el comportamiento de un Sandbox/cookie y de Basic con `test_client`, después caracterizar los handlers de uploads y `latest` bajo **una instancia ficticia compartida**. Separar «PASS del aislamiento actual» de «FAIL/ausente del tenant compartido». No forzar refactor de Engine mientras no se resuelva el modelo de despliegue.

**U4D:** comparar con cifras los dos modelos de aislamiento (Sandbox por cuenta vs compartido); capacidad, espacio persistente, costes y tiempos. No comprar infraestructura ni publicar servicios en esta fase.

**Salida U4B:** inventario y amenazas clasificadas, no código productivo modificado. Documentación en `fernando/continuacion-montara`, PR #74 en draft.
