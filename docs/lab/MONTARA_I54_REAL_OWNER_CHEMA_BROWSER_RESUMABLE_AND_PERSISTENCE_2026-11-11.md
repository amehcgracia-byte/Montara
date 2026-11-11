# MONTARA — Avance de integración I51–I54, editor Chema + recuperación

**Fecha:** 2026-11-11 · Rama: `fernando/integracion` · **LAB PASS, NO desplegado en beta, NO fusionado a main**.

## Resultado de producto alcanzado

Se ha confirmado físicamente que las rutas del servidor de la cuenta propietaria pueden reenviar **un proxy real** a un worker HTTP Unix privado, usando las rutas **originales de Chema**. La UI original no se ha reescrito; se le puede insertar opcionalmente un pequeño adaptador de URLs bajo un conmutador independiente del despliegue.

Se ha confirmado además que el **borrador original Stage sobrevive a la finalización del proceso** si se mantiene su carpeta de trabajo en almacenamiento persistente; el siguiente Engine reabre el mismo UUID y no permite sobrescribir su proyecto con «Nuevo».

## Nuevos módulos

- `urano/owner_original_jm_rpc.py`: `/urano/v1/media/<UUID>/...`, exige Host/Origin apropiados, sesión Google Owner almacenada, CSRF y catálogo Stage del propietario. Primer `POST wizard/upload` o `POST uploads`: `ensure_owner` contra broker; demás solicitudes exigen generación vigente (revalidada por el broker). Rutas revisadas exclusivamente: `wizard/upload`, `wizard/projects/new`, `wizard/draft`, `wizard/status`, `project`, `branding`; subida original reanudable `GET/POST uploads`, `GET/PUT/DELETE uploads/<32hex>`, `POST uploads/<32hex>/finish`. No proxy HTTP global, no endpoints arbitrarios.
- `urano/owner_browser_bridge.js`: adapta `fetch` y `XMLHttpRequest` del editor original exclusivamente hacia las anteriores rutas Owner. Antes de primera subida, `/session/refresh` solicita token CSRF y `/projects/<UUID>/ensure` activa/reutiliza un único worker. Bloquea las demás rutas originales `/api/v1/` y `/montara/` en el piloto. No envía claves ni medios al broker root.
- `urano/original_jm_owner_assets.py`: opción `enable_browser_pilot` sirve una copia HTTP del HTML original con un solo `<script>` previo a los scripts originales. `web/index.html`, `web/montara.js`, las subfases de Stage, JS de Push/Show y CSS de Chema **permanecen intactos**. El script solo se entrega a la cuenta propietaria.
- `urano/minimal_owner_api.py`: `enable_original_jm_rpc` y `enable_original_jm_browser_pilot` independientes y **falsos por defecto**, este último exige el primero, que exige el editor real instalado; la aplicación Owner C8 activa no pasa esos argumentos.
- `urano/owner_first_stage_wizard.py`: además de vídeo, comprueba que `master`, `songs` y `audio_paths` remitan a ficheros reales, finalizados y admitidos en el propio espacio privado. No puede abrir archivos externos arbitrarios mediante parámetros de audio.
- `urano/worker_state_policy.py` y adaptadores systemd: `StateDirectory=montara-owner-<sha256_del_owner[:40]>` con `StateDirectoryMode=0700`, solo para worker JM completo y a petición del root broker. Los sockets y el marcador `ready` siguen en el directorio temporal de la generación. Al reiniciar el worker se vuelve a abrir su `project.json` persistente. El nombre es estable incluso cuando cambien la generación del Engine, la VM, CPU/RAM o el proveedor de nube.

## Pruebas directas, con alcance exacto

1. **I51 PASS**, 5 tests del gateway Flask Owner → socket Unix HTTP, con autenticación, proyecto extranjero denegado, generación antigua, método y ruta no permitidos. Request `POST wizard/upload` de decenas de KB llega al backend sin bufferizarse en root.
2. **I52 PASS**, dos procesos reales distintos, dos `runtime_root` efímeros y un solo `data_root` durable. Primer proceso abre app y Engine originales de Chema, sube MP4 FFmpeg sintético 640×360 3s y guarda el primer borrador. Tras detenerlo, el segundo proceso abre el mismo proyecto con estado **idéntico**; `POST wizard/projects/new` responde **409** para no sobrescribir. No se ha probado todavía systemd real.
3. **I53 PASS**, 4 tests del servidor de assets + `node --check` + Node test de `fetch` y `XMLHttpRequest`: ambas APIs se reescriben a ruta Owner, preflight único y rechazo de operaciones no revisadas. El HTML original solo se adapta en la respuesta HTTP con opt-in; el archivo fuente no cambia.
4. **I54 PASS**, **Flask original de Chema + Engine real pinneado** en copia temporal, session+CSRF Owner, conexión Unix, `GET uploads` sin arrancar, `POST uploads` con fingerprint y activación única, `PUT uploads/<id>` con contenido real, `POST uploads/<id>/finish` y borrador Stage con UUID Owner. Respuestas: 201/200/200/200. El callback de broker se inyectó en laboratorio; autorización root real fue probada separadamente en I47–I48, **no constituye un E2E OAuth → root broker → systemd real**.
5. **Regresiones:** 28 tests PASS para políticas systemd/recursos, owner gateway, audio/video y estados (después de I52); el nuevo protocolo reanudable I54 se probó además de modo físico. Nuevo CI `.github/workflows/fer-i54-owner-browser-resumable.yml` creado, **no afirmar que GitHub Actions se haya ejecutado**.

## Pendientes antes de pedir a Fernando su prueba Windows

**Innegociables:**

- **El JS original usa más rutas**: previews, Range, selección de cámaras, música, render, salida y recuperación, además de Stage/Push/Show. En este piloto, las no revisadas quedan bloqueadas, no están implementadas. Hay que ampliar el gateway deliberadamente y probar el E2E original, no habilitar un reverse proxy genérico.
- **Token CSRF entre pestañas**: `/session/refresh` rota el token de toda la sesión. El script piloto conserva uno en memoria; si se abren dos pestañas de la misma cuenta, pueden invalidarse mutuamente. Antes de beta multi-pestaña, diseñar tokens independientes por pestaña o sesiones de editor en backend. No llamar esto «multi-tab ready».
- **Cuota de archivos largos**: el JM original con `MONTARA_SESSION_TOKEN` impone **256 MiB por fichero remoto**. Un proxy de una hora a ~1,45 Mb/s puede ocupar ~650 MB, de modo que **no cabe actualmente** sin mejorar el contrato. El límite se debe elevar con política segura, control de espacio libre, prevención de abusos y cambios mínimos claramente localizados, o una nueva receta de proxy que no degrade calidad. No prometer aún una hora de vídeo. El fallback con originales requiere permiso explícito y no debe consumir 30 GiB sin quota.
- **Persistencia systemd real**: `StateDirectory` está preparado y la recuperación se probó con dos procesos reales, pero NO se ha instalado el nuevo bundle JM `jm-<SHA>` ni probado la reasignación de permisos de `DynamicUser` en la unidad. Ejecutar solo en entorno aislado, sin tocar el broker root activo hasta verificarlo. La ruta de estado físico depende del ejecutor (systemd Linux actual); nombre lógico Owner independiente de nube.
- **Media local Companion**: el laboratorio I54 usa vídeo sintético reanudable, NO se ha probado todavía el Companion instalado en Windows/Mac ni exportado MP4 final usando originales locales. El primer test humano es el recorrido **Google → Proyecto Stage → Companion → proxies → sincronización → edición → render local**, no I54.
- **Front UX**: logo izquierda, pasos de Chema centro, menú Mis proyectos izquierda, perfil derecha; sin nueva pantalla/diseño duplicado. La opción de carpeta visible es elegible, no obligatoria; AppData no se impone.

## Garantías de no interferencia

- Ninguna fusión `main`, actualización del Editor original de Chema, submódulos `engine/` o `mixer/`, ni despliegue de la beta actual.
- Servicios Owner/túnel que estaban activos siguen con su versión anterior. Root broker de producción conserva sus propiedades; código nuevo solo en rama.
- No se copiaron ni subieron medios de usuarios; solo clips FFmpeg sintéticos en `/tmp`.

**Siguiente prioridad:** resolver el límite de proxies largos, robustecer la admisión de piezas reanudables y recuperar el E2E nativo Stage sin añadir un segundo sistema de subida. Desplegar el bundle JM completo en un entorno de ensayo separado cuando tenga contrato de rutas suficiente.
