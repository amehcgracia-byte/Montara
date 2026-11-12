# MONTARA — Auditoría de integración Owner/JM y consolidación de navegación
**Fecha:** 11-11-2026. **Rama:** fernando/integracion. **Runtime:** beta privada GCP+Cloudflare, editor JM inmutable 14cce126. **Objetivo:** un solo producto, Stage funcional con Companion local, posterior integración selectiva a main.

## 1. Criterio de revisión

Ante la retroalimentación humana acumulada, se auditó el conjunto y no una incidencia puntual:
- Decisiones previas en docs/lab/MONTARA_EDITOR_PRODUCT_UX_AND_LOCAL_STORAGE_DECISIONS_2026-11-11.md, MONTARA_PRODUCT_DECISIONS_AND_HANDOFF_2026-11-10.md y documentación SMART/I29–I59.
- web/index.html, web/montara.js, web/footage-memory.js, web/full-session.js y web/companion.js del bundle real de Chema.
- Capa Owner: owner_mode_entry.py, original_jm_owner_assets.py, owner_project_picker.js/.css, owner_browser_bridge.js, editor_project_bridge.py, owner_original_jm_rpc.py, owner_broker_preview.py, session_auth.py.
- Pruebas originales de RPC privado y Companion; estado de portal, broker y túnel en VM. Sin tocar archivos originales, SQLite de usuarios, procesos privados ni main.

## 2. Modelo de navegación contrastado

| Acción | Modelo correcto | Corrección efectuada |
|---|---|---|
| Entrar a Montara | Logo/intro original de Chema → Video/Music | La entrada autenticada reutiliza el bloque original #home y la animación Home, seguida de #mode |
| Home/logo | Reproducir el Home original, volver a selección de modalidades | No sustituir el data-go=home original de Chema por mode; restaurado |
| Video → Stage | Ir a Footage, sin un segundo logo cortado | ?start=stage oculta exclusivamente el Home inicial redundante del editor, mantiene sus handlers nativos y salta a Footage una vez |
| All/Video/Music/Stage projects | Un selector modal compartido y contextual | El picker observa los screens y el título de tarea de Chema; Music en Footage no debe etiquetarse Stage |
| Recuperar Stage | Recuperación nativa, sin pantalla técnica fugaz | ?resume=footage conserva recuperación nativa, cubre temporalmente Making con el logo original y retira la cobertura al terminar/fallar |
| Nuevo proyecto | Una operación contextual en el modal | Eliminada sección Owner antigua de proyectos y su formulario duplicado |
| Nombre proyecto/vídeo | No confundir entidad privada con nombre de exportación | En HTML Owner, campo de Chema etiquetado Output video name; título privado sigue en catálogo |
| Cuenta | Acceso a la derecha, subfases de Chema en centro | Account a la derecha; Projects junto al logo |

La distinción **Home** frente a **Stage launch** es crítica: el clip debe correr en Home, no cortarse durante el salto entre dos aplicaciones.

## 3. Integraciones y límites revisados

**Identidad y proyectos.** Google OAuth PASS humano anterior. Catálogo SQLite privado por propietario. CSRF rotatorio compartido por los adaptadores dentro de cada pestaña; no se eliminan autorizaciones. La entrada no crea proyectos automáticamente. El cambio entre proyectos distintos aún puede devolver 409 BusyOwner, sin cerrar el worker anterior; el modal debe conservar el error hasta la siguiente acción.

**Recuperación de archivos.** Chema usa sessionStorage montara-open-edit e IndexedDB montara-footage, originalmente por sesión/plataforma local. Owner intercepta ambas solo en piloto para aislar por UUID. Los registros anteriores se conservan y no se migran automáticamente. Resume latest global del editor se oculta en Owner porque no referencia inequívocamente el proyecto privado.

**Rutas/proxies.** owner_original_jm_rpc.py utiliza lista explícita de operaciones (wizard/status/upload, review, previews, edits, resumable uploads), CSRF, UUID y generación del worker. Límite de subida original heredado de 256 MiB; límites de chunks 16 MiB; techo de preview privado configurable vía jm_private_proxy_overlay. No abrir proxy HTTP general ni ampliar límites a ciegas. El Companion original restringe CORS al origen exacto de la beta; no admite dominios Workers arbitrarios.

**Versiones.** main nuevo 5d65ec3 fija Engine 92c7bc3; beta usa bundle JM 14cce126 y Engine probado anterior. El estado del repositorio (main incorporado a nuestra rama) NO implica que el runtime Engine/Companion Windows esté actualizado. No cambiar a mitad de validación humana sin matriz de compatibilidad.

**Arquitectura:** la VM solo coordina, el Companion local conserva originales y genera proxies; exportar MP4 final en local sigue siendo la prueba de producto pendiente. Push/Show/Music quedan fuera del hito E2E actual.

## 4. Pruebas y despliegue

- Contrato amplio: **36 pruebas Python y 55 subpruebas PASS** incluyendo entrada real, assets JM, RPC Owner, rutas de proxies, handoff Companion y política de orígenes.
- **11 tests Node PASS** de navegación/puente, recuperación, aislamientos y proxy/Companion.
- Python compile y JS syntax PASS.
- Nuevas comprobaciones en tests/test_owner_navigation_consistency.py contra el index real de Chema (Home intro, Stage launch, etiqueta de salida, logo Home y scripts originales).
- Beta desplegada con copia reversible en ~/.config/montara-owner-beta/rollback-nav-unification-20261111/. Cloudflare /healthz=200, entrada anónima 401, picker anónimo 401, inicio OAuth 302; portal, túnel y broker activos.
- **No hay PASS navegador end-to-end** de esta revisión: Playwright no pudo iniciar el Chromium presente en la VM porque falta libcups.so.2; no se instaló ningún paquete en la infraestructura compartida. No confundir PASS de contratos con PASS de UX real.

## 5. Defectos aún abiertos y prioridad de producto

**Bloqueantes antes de dar Stage por terminado:**
1. Validar la nueva navegación en el navegador real con una única comprobación conjunta, no tests parciales repetidos.
2. Rotación segura del worker Owner: consultar inactividad y renders pendientes, parar solo de forma autorizada/segura, conservar estado. La selección del proyecto ocupado debe ser predecible.
3. Recuperación persistente de un Stage con originales/proxies y cambio entre proyectos; respetar diferentes pestañas y CSRF.
4. Versionado de la beta frente a main nuevo y Companion Windows 0.6.10, comprobar contrato del Engine y paquetes.
5. **Stage real:** vídeo local corto → proxy Companion → subida privada → sincronización/edición JM → MP4 local. Solo este resultado cierra el recorrido.

**No bloqueantes ahora:** instalador definitivo Windows/Mac, perfil Account completo, monetización y UX de Push/Show/Music.

## 6. Principios de trabajo futuros

- Evitar seguir inventando pantallas, wizards y catálogos. Modificar preferentemente adaptadores, no los assets de Chema.
- Mantener una matriz única de flujos y tests de regresión al incorporar cada versión de main; exigir PASS de comportamiento, no solo HTTP 200.
- Un solo despliegue reversible por conjunto coherente; ninguna operación sobre los archivos personales ni servicios compartidos sin razón y autorización.
- Tras Stage + Companion + MP4 humano, preparar PRs pequeños y revisables hacia main (sin merge de toda la historia de laboratorio).
