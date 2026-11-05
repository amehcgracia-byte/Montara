# URANO U2 — mapa del recorrido real de archivos, proyectos y procesamiento

**Fecha:** 2026-11-05 · **Estado:** análisis de código; sin cambios de ejecución.  
**Código fuente:** `fernando/companion-windows-w1` de `amehcgracia-byte/Montara`.  
**Continuidad:** [U1](URANO_U1_REPOSITORY_INVENTORY_2026-11-05.md) · [W3S](JUPITER_WINDOWS_W3S_TECHNICAL_HANDOFF_2026-11-05.md).

## 1. Qué ficheros se han examinado realmente

`web/index.html` (orden de scripts), `web/montara.js` (~144 kB), `web/companion.js`, `web/resumable-upload.js`, `web/footage-memory.js`, `web/full-session.js` (cabecera y menciones de rutas), `companion/companion.py` (API, generación de proxies y control de Origin), `app.py` (registro de módulos), `resumable_upload.py` (rutas y límites), `full_session.py` (rutas/sesión), `deploy/README.md` y `deployment/vercel/README.md`. Inspección **focalizada**, no auditoría exhaustiva de todo el código ni de Engine/Mixer.

## 2. Ruta A: vídeo local con Companion disponible

```text
Usuario selecciona vídeo en navegador
    |
    v
web/montara.js -> montaraCompanion.smallVersion(file)
    |
    v
web/companion.js: GET /health (127.0.0.1:47820)
    |
    v
SHA-256 de primeros y últimos 64 KiB del File
    |
    v
Companion POST /locate -> busca original por nombre, tamaño y fingerprint
    |
    v
Companion POST /proxies -> FFmpeg local -> fichero temporal .part
    |
    v
GET /proxies/<id> hasta estado ready
    |
    v
GET /proxies/<id>/file -> pequeño .small.mp4 (o audio FLAC/WV/Opus)
    |
    v
web/montara.js upload() -> /api/v1/wizard/upload (<=8 MiB)
                   o -> /montara/uploads (fichero grande)
    |
    v
Servidor Flask / Engine clasifica e incorpora medio al proyecto
```

**Hecho relevante:** los proxies **sí viajan al servidor**. Lo que se intenta evitar es subir los originales completos; la frase «el original nunca sale» solo es válida mientras funciona esa ruta concreta. La captura del archivo local en JavaScript utiliza File API y no requiere que Companion explore el disco arbitrariamente.

En sesión Stage, `web/companion.js` contempla audio ligero Opus y peticiones posteriores `/segment` con rangos de audio originales. El camino de renders nativos contempla `/video-renders`, pero no se ha auditado todavía cada condición de habilitación.

## 3. Ruta B: sin Companion o con fallo

`web/montara.js`:
- `upload(file, entry)` consulta si Companion está detectado y ayuda para ese tipo de archivo; si no, sube por el flujo histórico del servidor.
- `uploadSmall` llama a `smallVersion`. Ante estado `{missing:true}` y tamaño > 200 MiB coloca entrada en error, conserva el original y evita subirlo automáticamente en ese caso **específico**.
- Si `smallVersion` devuelve `null` por un error diferente, el código cae a `upload(small ? small.file : file, entry)`: **puede iniciar subida del archivo original sin una autorización específica de reemplazo por original**, incluso con Companion detectado y para fichero grande. `uploadInParts` puede enviar el contenido dentro de los límites del servidor. Es un **riesgo de privacidad, coste y expectativa de usuario** que requiere prueba y decisión explícita de UX.
- Cuando Companion está totalmente ausente, la ruta habitual sigue enviando originales; hay que informar claramente en interfaz antes de comenzar.
- No cambiar esta lógica en U2 sin pruebas de regresión y criterios de producto: abrir tarea focalizada U3.

## 4. Subida y recuperación del lado servidor

`web/resumable-upload.js`:
- Separa carriles de audio y vídeo con límite de cuatro archivos activos por carril.
- Consulta `GET /montara/uploads` para conocer el límite vigente.
- Calcula fingerprint de bordes y crea un registro `POST /montara/uploads`.
- Envía por `PUT /montara/uploads/<id>` con `Upload-Offset` y fragmentos de tamaño suministrado por el servidor, con reintentos por fragmento; confirma con `POST .../finish`.

`resumable_upload.py`:
- Ruta de almacenamiento `<data_root>/Uploads`; tamaño de fragmento **4 MiB**.
- Límite de fichero **256 MiB** si existe `MONTARA_SESSION_TOKEN` (preview) o **30 GiB** en servidor sin ese token; ambos sujetos a espacio disponible y validaciones del servidor.
- Estado de upload en archivos `upload.json` y `source.part`; se serializan accesos por archivo mediante flock.
- Mover a un servicio multiusuario requerirá revisión de identidad/propiedad y aislamiento, no solo cambiar el hostname.

## 5. Dónde persiste qué

| Componente | Persistencia observada | Límite |
|---|---|---|
| Web `footage-memory.js` | IndexedDB `montara-footage`, records por archivo con marca temporal, handle opcional y metadata | Caduca a **14 días**; permiso de lectura local se vuelve a comprobar cuando reabre |
| Web `montara.js` | `sessionStorage['montara-open-edit']` con estado de edición/ID/medios | Por sesión de navegador; recuperación asociada a proyecto de backend |
| Web `full-session.js` | `localStorage['montara-session']` para ID de sesión | No demuestra control de propiedad entre usuarios |
| Companion `companion.py` | `HOME/proxies`, `HOME/places.json`, carpeta elegida para el proyecto | Proxies pueden recuperarse por clave; trabajos en memoria y `.part` requieren controles de ciclo de vida |
| Servidor `app.py` + `resumable_upload.py` | `data_root`, `Uploads` y ficheros de los proyectos en Engine | El servidor privado existente no es por sí solo multiusuario |
| Sesión musical `full_session.py` | `<data_root>/Sessions/<id>/session.json` y ficheros relacionados | `/montara/session/latest` busca la sesión más reciente del servidor, no una sesión asociada a una identidad individual |

## 6. Seguridad: hallazgos que necesitan diseño antes de SaaS público

**Companion local:** escucha en `127.0.0.1:47820` y filtra el encabezado `Origin` mediante una lista de patrones. En las rutas revisadas, el filtro de Origin es la principal barrera y **no constituye autenticación de usuario**. `GET /health` está permitido sin Origin y existe una excepción para la descarga `/video-renders/<id>/file?download=1`. Evaluar amenazas de rebinding, origen autorizado, navegación directa y robo de URLs de exportación. **No afirmar que hay una vulnerabilidad explotable sin prueba controlada.**

**Servidor:** `full_session.py` valida que rutas de audio pertenezcan a `data_root` o a fixtures. `/montara/session/latest` busca por fecha el último registro del servidor. Es coherente con el despliegue privado/un usuario, pero no demuestra aislamiento por cuenta para una oferta SaaS.

**Interfaz:** `web/montara.js` muestra actualmente `Choose on your Mac where Montara keeps this project` aunque Companion funcione en Windows. Corregir en el backlog UX para un mensaje independiente de plataforma.

## 7. Primeras decisiones U3 priorizadas

1. **Consentimiento antes de subir originales:** determinar si la app debe detenerse o mostrar elección clara cuando Companion falla; probar escenarios `missing`, `failed`, `skipped`, timeout, ausencia total de Companion, archivos mayores/menores de 200 MiB.
2. **Identidad y permisos:** quién puede consultar sesiones, trabajos, ficheros locales y resultados, si hay usuarios simultáneos; introducir un modelo mínimo de propiedad de trabajos/sesiones antes de exponer SaaS.
3. **Modelo de proyecto:** estado de edición en navegador vs proyecto local vs servidor; recuperación tras reinicio de navegador/Companion/servidor, caducidad de datos.
4. **Economía y carga:** matriz de tamaño original/proxy/audio; límites de subida, almacenamiento, CPU, tráfico y trabajo cloud; determinar qué flujo permanece local por tipo de proyecto.
5. **Experiencia cross-platform:** textos Windows/Mac, primer arranque, errores previsibles y recuperación; mantener aceptación ya validada W3Q.
6. **Alcance de Stage/Push/Show:** seguir llamadas reales y contrastar los modos con E2E y servidor privado antes de afirmar disponibilidad comercial.

## 8. Criterio de esta entrega

**U2 completado como mapa inicial verificable de flujos y riesgos**, no como certificación de seguridad ni aprobación de un nuevo diseño. No hay cambios a producción ni a `fernando/companion-windows-w1`; solo documentación en `fernando/continuacion-montara`. PR #74 sigue sin merge. Distribución FFmpeg pendiente por decisión del usuario.
