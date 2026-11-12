# MONTARA · Hito 3 — Web original de Chema y Owner HTTP privado
**12 noviembre 2026 · Rama:** `fernando/chema-native-owner` (base limpia desde `main`).  
**Estado: contrato web/HTTP inicial implementado y validado en entorno aislado; NO desplegado en Cloudflare/portal productivo.**

## Decisión de producto respetada

El documento `web/index.html` de Chema se publica **íntegro, sin construir pantallas equivalentes**. Se añade exclusivamente un `owner-bridge.js` cargado antes de sus JS: no selector de proyectos Owner, no dashboard alternativo, no botón nuevo de gestionar Engine, ni un navegador artificial de New/Latest. Su portada Music/Video, Stage/Push/Show y los botones New y Resume Latest permanecen exactamente donde Chema los situó.

El **portal Owner** se responsabiliza únicamente de Google OAuth existente, sesión opaca, renovación de CSRF, asignación de workspace privado por usuario, admisión al broker y transporte al worker. Dentro de ese workspace, New y Latest son las operaciones **originales** de Chema, con sesión de música o último vídeo según `recovery.py`.

## Archivos implementados o portados selectivamente

- `urano/native_owner_browser_surface.py`: sirve HTML completo original + archivos `web/` SHA-pinneados, autentica todos los assets y rechaza variantes no conocidas.
- `urano/native_owner_browser_bridge.js`: único adaptador de navegador; intercepta Fetch/XHR para las APIs revisadas; exige CSRF y generación broker; no arranca Engine por el **GET Latest automático** de `full-session.js` al mostrar la portada; espera a la pantalla nativa **Footage**. Convierte miniaturas/previsualizaciones protegidas en `blob:` locales.
- `urano/native_owner_web_gateway.py`: resuelve workspace mediante el Owner **en servidor**, sin parámetros de propietario/worker dados por navegador. Verifica Origin, sesión, CSRF, generación y lista blanca HTTP; obtiene descriptor Unix por autorización independiente del root broker existente. Transfiere datos con límites; nunca permite rutas arbitrarias. Verifica metadatos de Companion y transfiere sus fragmentos sin almacenar originales en el portal. Devuelve JSON o binarios/rangos únicamente de rutas revisadas.
- `urano/native_owner_new_latest_http.py` y `urano/native_owner_stage_http.py`: métodos/rutas/query explícitos; incluye entradas New/Open/Draft/Latest, settings Stage, sync, review, uploader directo/resumible y previews. Desconocidas bloqueadas, no se envían a un Engine global.
- `urano/native_owner_workspace_gate.py`: fronteras de carpetas privadas de proyectos y medios; las rutas de settings de cámaras, fillers y otras referencias a archivos se validan dentro de Owner.
- `urano/native_owner_app.py`: composición de la web de Chema, OAuth PKCE original, Owner SQLite, SessionStore y RPC, sin dashboard.
- `urano/native_owner_trusted_wsgi.py`: **factory de Gunicorn exclusivamente opt-in** (`MONTARA_NATIVE_OWNER_PORTAL=reviewed-opt-in`) con preflight beta, archivo de secret privado, paquete Chema y Engine pinneados, manifiesto verificado, directorio de datos 0700 y la frontera HTTPS loopback estricta que ya protegía la beta anterior. **No crea, instala ni reinicia servicios.**
- Portados solo los módulos ya revisados necesarios: `google_flow.py`, `google_oidc.py`, `google_owner.py`, `owner_broker_preview.py`, `owner_private_http_client.py`, `first_valid_upload_gate.py`, `c6_beta_preflight.py`, `trusted_local_https.py`, `jm_bundle_manifest.py`; el código de aislamiento H2 permanece en la misma rama.

## Evidencia obtenida

1. **84 pruebas Python y 106 subpruebas PASS** en GCP usando el entorno del portal que ya dispone de Flask y criptografía; incluye todo el contrato nuevo y H2. Node VM de `native_owner_browser_bridge.js` PASS.
2. El documento servido se compara byte a byte con el HTML de `main`, **menos la única etiqueta de adaptación**. Los CSS/JS originales conservan sus bytes. La primera portada no inicia Engine; primer Footage sí comprueba Owner/CSRF y acceso privado.
3. Dos identidades de sesión de ensayo y sus workspaces independientes, con autorización I27 en SQLite, descriptor Unix y rechazo de proyecto/cámara de otro usuario. Anónimo 401, autenticado sin CSRF 403, generación caducada rechazada.
4. Transferencia Companion directa/resumible (incluido tamaño superior al límite JSON del portal), rechazo de extensión/fingerprint/metadatos inválidos, y HTTP de imagen/MP4 Range 206 con blobs locales seguros.
5. **Prueba física adicional con el paquete original de Chema en GCP**: el `resumable_upload.py` auténtico recibió un MP4 válido de 3 segundos y 640×360 mediante Create 201 → PUT 200 → Finish 200; lo clasificó como 1 vídeo, el guard de Owner aceptó su ruta privada y `New → Draft → Latest` devolvió **200 / 200 / 200**. Se eliminó el entorno temporal.
6. La WSGI factory nativa funcionó con el **bundle original y su manifiesto verificado** en GCP y una identidad/datos/secret de ensayo: login no autenticado redirigido a Google; autenticado veía Home de Chema y activos JS originales; Host/Forwarded no autorizado rechazado. No se llamó Google realmente ni se desplegó el portal.
7. **Corrección detectada en ensayo:** un vídeo de solo 1 segundo y 160×90 no era aceptado por el propio `validate_camera_video_metadata` de Chema (mínimo duración >2 s, resolución >=320×240). Con entrada válida la transferencia se clasificó correctamente. No fue un fallo de Owner.
8. `GET /montara/uploads` responde desde el uploader auténtico de Chema, **no una imitación hecha por Owner**. El máximo de transferencia es el `private_preview_limit_mib` aprobado por el operador, coherente con el manifiesto de Chema.

## Límites y trabajo restante — no declarar un E2E falso

- La **nueva rama no está desplegada**: Cloudflare Worker y portal GCP siguen sirviendo la versión anterior, con su worker original activo. El código del nuevo broker/worker está preparado por H2 y probado en transitorio systemd, pero **no se ha activado mediante el broker de producción**.
- H3 demuestra portada original, Google/CSRF/comunicación privada y **primer camino Stage con proxies**. No significa que Music, Push y Show tengan todas sus APIs activadas: se preservan las opciones de Chema visualmente, pero las APIs aún no revisadas se bloquean, sin falsos resultados.
- Faltan las fases posteriores de Stage: editor/audio completo, efectos, composición, exportación MP4 final, persistencia tras reinicio con navegador y Companion Windows. Su aceptación física pertenece a los próximos hitos y debe usar el producto real, no un segundo editor.
- **Migración no destructiva necesaria para usuarios actuales:** `NativeOwnerWorkspaceRegistry` niega la elección automática si el Owner ya tiene UUID/proyectos antiguos. Antes de una primera prueba humana, inspeccionar mapeo vigente, broker/ledger/StateDirectory y elegir explícitamente el workspace correcto, sin ocultar ni borrar ningún proyecto. No se han cambiado esas bases de datos.
- **Hito 4**: publicar en un origen Cloudflare aislado, no cambiar la rama de Pages ni interrumpir el Worker/Tunnel anteriores; aislar Google OAuth y datos/servicio, validar originales/Companion Windows, y dar al usuario una URL concreta una vez verificada. **Hito 5**: MP4 real completo, reanudación, dos usuarios de Google y concurrencia; solo después PR a `main` para Chema.

## Operación y deuda posterior

Durante este hito no se ha fusionado `main`, no se han alterado los scripts originales de `web/`, no se ha parado ningún worker real ni se han borrado datos históricos. Las pruebas de GCP se ejecutaron en carpetas temporales con limpieza automática. No se ha instalado Python, criptografía ni otro entorno innecesario.

**No prioritario, pospuesto por indicación del usuario:** localizar después en GitHub el acuerdo entre IAs de Fernando y Chema para reflejar decisiones, coordinar issues, propuestas y peticiones; trabajar sobre el acuerdo existente en vez de inventarlo.
