# MONTARA — Contrato de integración nativa de Chema, sin multiproyecto visible
**12 noviembre 2026 · Rama `fernando/integracion` · Investigación 1 — Inventario y decisión; NO desplegado.**

## Decisión de producto confirmada
Integrar **la aplicación de Chema tal cual se navega**, con Google Owner/identidad persistente, aislamiento multiusuario, Engine privado y Companion. El destino funcional y visual es la web original: intro Montara → Music / Video → Stage / Push / Show → editor y recuperación original. El multiproyecto visible se aplaza hasta validar flujo integral, dos usuarios y una integración revisable en `main`.

No sustituir la portada original por un dashboard ni mover **New project** y **Resume latest** a una pantalla ajena. No borrar proyectos antiguos; aun sin selector, el sistema conserva identificadores UUID y persistencia bajo propietario. **No confundir «un proyecto activo» con «un único proyecto existente».**

## Baseline real comprobado
- GitHub `main@5d65ec3`, `fernando/integracion@b2f1018` durante esta auditoría; la rama estaba **0 commits detrás** y **449 por delante**. `web/` de nuestra rama era **idéntico** a `main:web/` (diff vacío).
- Se inspeccionaron los originales de Chema `web/index.html`, `montara.js`, `full-session.js`, `footage-memory.js`, `companion.js`, `native-export.js`, además de nuestra `owner_mode_entry.py`, `owner_project_picker.js/.css`, `owner_browser_bridge.js`, `original_jm_owner_assets.py` y `owner_first_stage_wizard.py`.
- Despliegue GCP observado antes del trabajo: portal, túnel y broker **activos**; un worker `running`. **No se ha reiniciado ni modificado.** Runtime JM pinneado puede ser anterior a `main`; cada cambio requiere cotejo de versiones y assets antes de desplegar.

## Contrato real de Chema (NO rediseñar)
1. **`web/index.html:13,20,35,46-60`**: marca/intro, botón nativo `#newVideo`, pregunta Music/Video, Stage `data-platform=youtube`, Push `reel`, Show `show`. Music tiene Mix a song, Mix a full session y Master.
2. **`web/montara.js:198-271`**: los elementos originales controlan selección y transición a Footage; `#newVideo` vuelve al modo original. `web/montara.js:274-302` define `resetFlow`, que limpia el estado de la sesión del navegador.
3. **`web/index.html:114,118`**: Footage incluye `#sessionResume` y `#restoreFiles`. **`web/full-session.js:3-26`** consulta `/montara/recovery/latest`, puede recuperar proyecto o sesión musical; `web/montara.js:2946-3039` usa `sessionStorage['montara-open-edit']` y estado real del proyecto para restaurar edición. `footage-memory.js` conserva referencias locales mediante IndexedDB.
4. **`web/full-session.js:119-167`**: Stage puede entrar en sesión musical, generar guía y lanzar la secuencia original `POST /wizard/projects/new` → `POST /wizard/draft` → preparación. **No** sustituirla por un «paso» de Owner.
5. **`web/companion.js`**: los originales permanecen locales; Companion puede pedir seleccionar carpeta para proyecto/exportación. Elegir carpeta no equivale a trasladar proyecto de GCP. No crear otro uploader.

## Interferencias Owner encontradas (lista de remoción/adaptación)
| Pieza actual | Diferencia comprobada | Decisión destino |
| --- | --- | --- |
| `owner_mode_entry.py:15-127,139-169` | Construye otra página con fragmentos de Chema, pero tiene su propio JS de navegación y selección de Stage; Music/Push/Show muestran mensajes «not connected». | Eliminar navegación alternativa **en la versión integrada**. Usar navegación nativa y una entrada autenticada mínima. No simular soporte en rutas no conectadas. |
| `owner_project_picker.js` | Inyecta catálogo/selector, diálogo de crear, selector de modos y estado Engine en cabecera. | Retirar del recorrido visible. Conservar código histórico sin borrarlo. |
| `owner_project_picker.css:26-29` | **Oculta nativos** `#sessionResume` y `#newVideo`; por ello Chema no puede aplicar su contrato real de New/Latest. | Restaurar controles originales una vez que la API Owner soporte ambos sin cruces de propietarios. No eliminar los guards de seguridad antes. |
| `owner_browser_bridge.js:70-90` | Reescribe `montara-open-edit` por UUID y conserva snapshots Owner por proyecto; también re-clasifica IndexedDB. | Mantener aislamiento entre propietarios, pero definir una única fuente de verdad para proyecto reciente; quitar depender del selector multiproyecto. |
| `owner_first_stage_wizard.py:111-136` | Intercepta `/wizard/projects/new` y devuelve `Create a new private Montara project first` si el proyecto activo ya no está vacío. | **Bloqueo funcional verdadero**: rediseñar transición New → nuevo contexto Owner permitido, con cierre seguro del worker anterior; no desactivar el guard. |
| `owner_original_jm_rpc.py` y `owner_session_bindings.py` | Intermediación de rutas y sesiones desde Owner al worker. | Conservar y auditar extensiones necesarias por contrato nativo, sin proxy general de rutas sensibles ni acceso anónimo. |
| `original_jm_owner_assets.py` | Sirve el editor Chema real, inyecta bridge y reemplaza unas etiquetas/notas. | Mantener único editor original; minimizar modificaciones HTML y congelar/validar anchors. |
| Engine read-only propuesto | Estado activo/busy y color explicaban detalles técnicos en cabecera. | No imponer ON/OFF ni catálogo; estado de trabajo manejado por backend. Diagnóstico técnico solo cuando sea útil. |

## APIs/recorridos identificados: inventario de cobertura, no certificación
Revisión estática de **24 módulos JS** de Chema, de los cuales 11 contienen rutas API literales. El bridge Owner define **29 entradas literales** y patrones dinámicos adicionales. La extracción textual encontró **43 prefijos no coincidentes literalmente**, incluidos algunos patrones que Owner sí maneja de forma dinámica; **NO son 43 fallos demostrados**. Este análisis es una primera red de cobertura, no un resultado E2E.
- **Stage y edición:** `/api/v1/wizard/*`, `/api/v1/edit/*`, `/montara/uploads/*`, `/montara/session/*`. Integración parcial verificada; no hay MP4 final E2E aprobado.
- **Music:** `/montara/mix/*`, `/montara/master/*`, `/montara/music/*`, `/montara/recovery/latest`: faltan contratos Owner y recuperación nativa completa.
- **Push:** `/montara/push/packs` y su secuencia con el wizard: no certificada.
- **Show:** `/montara/show/*`, `/api/v1/show/*`, library/shelf/editor/audio/playback: no certificada.
- **Companion:** `/health`, `/locate`, `/proxies`, `/projects`, `/video-renders` y subrutas del dispositivo, según I29. Deben probarse en Windows y Mac sobre el contrato del Companion actual.

La auditoría definitiva por endpoint debe registrar verbo, payload, identidad, archivo/carpeta admitidos, estado persistido, respuesta, error, cancelación y reanudación. En particular, revisar las URLs construidas mediante plantillas y botones HTML (que una búsqueda textual no captura por completo).

## Reutilización demostrable de las etapas anteriores
- **I16:** Engine real aislado con cgroup/PID namespace; sus tiempos y límites son de ensayo físico, no un benchmark completo.
- **I19:** admisión Owner + ledger con `BusyOwner`; **laboratorio de contrato**, no prueba producción. Es la razón de la exclusividad de un proyecto activo por usuario.
- **I24:** unidad durable/recuperación exacta de worker; aún había requisitos operativos al documentarse.
- **I26–I27:** broker real de permisos mínimos y acceso vía sesión Google/CSRF con UID y socket, con validaciones físicas; se auditará la implementación actual de beta.
- **I28:** workspace provisional, **no** editor objetivo.
- **I29:** documento precedente que ya prohíbe dashboard técnico, exige interfaz original y Companion, y no permite declarar PASS sin E2E humano.
- **U13D2A:** dos procesos y usuarios sintéticos concurrentes; **no** evidencia de dos renders pesados ni dos usuarios Google reales simultáneos. No repetirlo salvo cambio de contrato.

## Orden operativo corto (sin laboratorios paralelos)
**Bloque 1 — Contratos exactos y fuente de verdad.** Verificar `main` + runtime; cerrar matriz endpoints y persistencia para Stage; definir explícitamente «último proyecto» por propietario y transición New sin riesgo. **No tocar beta activa todavía.**

**Bloque 2 — Integración nativa detrás de Owner.** Portar mínimo de identidad/sesión/CSRF/proyecto activo al editor Chema original; conservar New/Latest, Home y animación nativos; no picker ni segundas pantallas. Guardar en propiedad persistente; usar aislamiento existente I19–I27.

**Bloque 3 — Un proyecto por usuario, Stage íntegro.** Un solo recorrido autenticado: Chrome → Cloudflare → Companion (proxies y originales locales) → Stage → sesión/mixer según Chema → edición → MP4 nativo local, recuperación y export. Incorporar pruebas de fallo y reinicio.

**Bloque 4 — Dos personas y `main`.** Dos sesiones Google reales y trabajos simultáneos con métricas de VM, sin cruce de carpetas ni jobs. PR(s) mínimos desde `main`, para revisión de Chema; sin fusionar a ciegas los cientos de commits de nuestra rama. Posponer multiproyecto, sin borrar sus datos.

## Criterio de parada y seguridad
- No desmontar `owner_first_stage_wizard` ni habilitar `/montara/recovery/latest` global sin sustituirlos primero por equivalentes Owner con propiedad comprobada.
- No reiniciar broker/worker en ejecución ni limpiar IndexedDB, SQLite o carpetas locales.
- Toda validación sobre el **mismo editor nativo** que llegará a `main`; no interfaz temporal adicional para declararlo probado.
- Reportar solo evidencias: pruebas históricas reutilizadas, tests regresivos nuevos cuando un contrato cambia, y una única aceptación humana por hito significativo.
