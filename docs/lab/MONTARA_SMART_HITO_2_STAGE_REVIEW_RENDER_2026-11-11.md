# MONTARA SMART — Hito 2/5: Stage privado hasta solicitar render

**11 de noviembre de 2026 — Hito 2 cerrado dentro de su alcance acordado.**
**Destino:** `fernando/integracion`. **Rama de Chema y `main`: intactas.**

## Entregable funcional

Se ha conectado al Owner autenticado el recorrido Stage original del editor de Chema sin editar `web/index.html`, `web/montara.js` ni `web/cut-editor.js`:

1. Subida original y resumable Companion → `wizard/upload`, `uploads/*`, borrador → Stage privado.
2. Preparación y sincronización real → `wizard/prepare`, `wizard/start`, `wizard/status`, `artifacts/sync`.
3. Revisión de tomas: `GET wizard/review?render=1&shot=N`, miniaturas `assets-v2/*.jpg`, previsualizaciones MP4 con `Range`/HTTP 206 y cambio de toma `POST wizard/review/replace`.
4. Edición manual de Stage: `GET/PATCH edit/shot`, `GET/PATCH edit/timeline?kind=music`, `GET edit/shot/frame`. Método, query y proyecto Owner acotados.
5. Botón final de esta fase: `POST wizard/review/render` autorizado, cuerpo JSON y generación de worker privado. **HTTP 202 = tarea aceptada, no MP4 final.**

El adaptador `urano/owner_browser_bridge.js` mantiene el HTML/CSS/JS de Chema intacto, reescribe solo rutas revisadas y usa solicitudes `fetch` firmadas mediante sesión + CSRF para miniaturas/videos. Como las etiquetas `img`/`video` no pueden llevar headers privados, se construyen **blob URLs locales del navegador** después de la comprobación Owner, sin crear un proxy global público. Se bloquean explícitamente rutas de otros modos y queries arbitrarias. Interfaz original y navegación central conservadas.

## Evidencia real de aceptación de Stage (no simulación del Engine)

En GCP, prueba temporal contra **JM original `14cce126`, Engine auténtico `b867b3c` y Mixer `f15ff91`**, con Flask Owner autenticado sobre sockets HTTP Unix privados y vídeo sintético FFmpeg de 12 segundos con audio maestro:

- Subida de vídeo y audio: **HTTP 200** (dos archivos).
- Nuevo proyecto, borrador Stage y fillers: **HTTP 200**.
- Preparación: **HTTP 202**, sincronización alcanza **`waiting_choice`**.
- `wizard/start`: **HTTP 202**, Stage alcanza **`waiting_review`**.
- `GET wizard/review?render=1`: **HTTP 200**, **3 tomas reales**, plataforma youtube.
- Primera miniatura Stage `assets-v2`: **HTTP 200**, JPEG real de 8.242 bytes.
- `POST wizard/review/render`: **HTTP 202**, trabajo aceptado.
- Entorno de prueba cerrado con **código de salida 0** en ~33 s. La prueba no demuestra que haya terminado un render Owner/Companion, que corresponde al hito 3–4.

Otras pruebas:
- **11/11 PASS**, gateway Flask HTTP Unix: autenticación, CSRF, propietarios distintos, media por rangos, miniaturas, edición de toma y línea de tiempo, render.
- **Node PASS** (`tests/test_owner_review_bridge.cjs` y `tests/test_owner_browser_bridge.cjs`): adaptador del navegador para fotos, hover vídeo, edición revisada y ausencia de rutas a Engine compartido.
- La aplicación multimedia original completa de Chema ya había superado `tests/e2e_native_stage.py` con Chrome H.264 y Companion 0.6.10 en I59. **Eso no equivalía a Owner Google + Windows E2E; sigue pendiente.**
- Workflows CI existentes actualizados para incluir test del adaptador review; no afirmar que GitHub Actions se haya ejecutado.

## Publicación en beta real

El portal Owner de GCP/Cloudflare se actualizó con `owner_original_jm_rpc.py` y `owner_browser_bridge.js` a la revisión comprobada `94dd6a6f`. Se reinició **solo el portal Owner**, con copia de rollback de los dos archivos. Tras reinicio: `/healthz` **HTTP 200**, Google login **302**, dashboard sin sesión **401**, túnel y broker `active`. Ningún trabajo de prueba permanece activo. El Engine privado y los bundles son los instalados en Hito 1, sin nuevo cambio de unidad `systemd`.

**Nota de alcance:** no hemos hecho todavía navegación interactiva con una cuenta Google humana ni accedido a originales de Windows; se han verificado por separado el backend auténtico y la transformación de rutas desde el navegador. **Hito 2 significa Stage privado hasta solicitar render; no exportación final.** En el hito 3 se comprobarán juntos Companion y el servidor antes de pedir a Fernando el test completo.

## Próximo hito 3/5: Companion Windows

**Solo lo necesario para la validación humana:** configurar origen HTTPS de la beta, identidad del proyecto local y relación con el UUID Owner, comprobar `GET edit/native-recipe`, transferencia autorizada del audio máster y fallback consentido; render de MP4 **local**, con originales sin subir. El E2E original de Chema debe reutilizarse, no duplicarse. Faltan rutas `edit/native-master`, `edit/native-source` (solo fallback autorizado) y recuperación de proyecto Companion. CSRF multi-pestaña, estilos avanzados, Push/Show, tuning y cuotas agregadas se posponen salvo bloqueo real.

**No integrar a `main` hasta validación humana completa. Después, integración escalonada y revisable con Chema.**
