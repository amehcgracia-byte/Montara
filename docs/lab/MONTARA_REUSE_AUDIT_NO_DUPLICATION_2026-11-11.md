# MONTARA — Auditoría anti-duplicación URANO y ruta directa al editor de Chema

**Fecha:** 2026-11-11 · **Rama:** `fernando/integracion` · **Tipo:** revisión de código, documentación y regresiones existentes (sin despliegue ni fusión).

## Hallazgo ejecutivo

**Fernando tenía razón: buena parte de I31–I37 vuelve a comprobar fronteras ya construidas y ensayadas en U13C/U13D e I19–I27.** Hay diferencias técnicas reales (consulta de estado de Stage y Unix worker dedicado), pero **ningún motivo para seguir ampliando laboratorios de apertura de Engine o de sockets por sí mismos**. La prioridad cambia de inmediato a integrar el **editor auténtico JM con proyectos privados y Companion**, reutilizando los módulos existentes.

## Inventario / decisión de reutilización

| Componente | Ya existía / evidencia | Decisión |
| --- | --- | --- |
| Owner autenticado Google, catálogo, CSRF, proyectos privados | C1/C8, I27 y prueba humana anterior. `urano/minimal_owner_api.py`, `http_projects.py`, `session_auth.py` | **REUTILIZAR**. No crear segundo login/dashboard. |
| Project binding Engine y proceso dedicado | U13A/U13C `engine_worker_process.py`, U13D `private_worker_supervisor.py` | **REUTILIZAR**. No replicar protocolo/gestión de procesos. |
| Fencing y recuperación de trabajos | I18 `job_recovery_ledger.py`, I19 `trusted_job_admission.py`, I21 `gateway_job_bridge.py` | **REUTILIZAR**; conservar sus pruebas, no otros registros de trabajos. |
| Engine real + cgroup/UID | I20–I25, I26 `private_broker_service.py` + `restricted_systemd_broker.py` | **REUTILIZAR**. I26 ya comprobó un Engine real bajo `DynamicUser`, reanudación/cierre y unit IDs; no repetir sin cambio funcional nuevo. |
| Google Owner → Engine privado, con revalidación dentro del broker | I27 `owner_broker_preview.py`, `private_owner_admission.py` | **REUTILIZAR**; evitar segunda ruta de confianza paralela. |
| El navegador JM → Companion → proxy → render local | `web/companion.js`, `web/montara.js`, `companion/video_jobs.py`, `tests/e2e_native_stage.py`. E2E existente usa navegador, Engine, Companion, FFmpeg y MP4 local **sin Owner multiusuario**. | **REUTILIZAR**. No escribir un segundo editor ni reimplementar exportación local. |
| Compatibilidad browser/Companion, original no transmitido por defecto | `tests/urano_companion_browser_bridge.cjs` (funciones reales, HTTP mock) | **REUTILIZAR**. Los tres casos success/missing/failed pasan en VM con shim `File` sobre Node 18 (producción/CI usa Node moderno). |
| Primer status privado Stage vía Owner → broker Unix → worker Unix → Engine auténtico | **I31–I37**, diferencia incremental legítima, PASS I37 en VM con Engine real y sesión lab | **CONSERVAR COMO CAPACIDAD DE STATUS**, no confundir con producto editable; no más reensayos redundantes. |
| I28 workspace y botones 'Abrir/Cerrar Engine' | Prototipo provisional, no el editor JM | **NO ADOPTAR COMO UI FINAL**. No añadir pantallas ni controles de Engine al usuario. |
| Rutas JM + Owner: wizard, review, sync, render, Push, Show, recuperación | Documentación `MONTARA_STAGE_PUSH_SHOW_OPERATION_MAP_2026-11-11.md`; rutas JM actuales dependen de instancia compartida `app.py` | **FALTA**: integrar todas las operaciones en Engine y almacenamiento **por proyecto/owner**. Esto es el bloqueo central, no apertura de Engine. |
| Companion Windows físico desde login real hasta MP4 Owner | Laboratorios y pruebas previas en Linux; **NO** test humano con Owner + editor JM + Windows | **FALTA**; puerta obligatoria de aprobación de Fernando. |

## Pruebas que se han vuelto a ejecutar en una copia aislada

Desde el mismo `fernando/integracion` se extrajeron los fuentes a `/tmp` y se ejecutaron sin reiniciar servicios: `tests/test_urano_engine_worker_process.py` **5 PASS**; `test_urano_gateway_job_bridge.py` **6 PASS**; `test_urano_i26_private_broker.py` **5 PASS**; `test_urano_i27_owner_admission.py` **8 PASS**; `test_urano_i27_owner_http.py` **8 PASS**. **32 pruebas históricas PASS**. Además, `tests/urano_companion_browser_bridge.cjs` **3 casos PASS** (con Node 18 y `global.File=require('node:buffer').File` por carecer ese Node de `File` global; sin alterar el test). Son **comprobaciones de regresión**, no se proclaman pruebas nuevas de funcionamiento del producto.

`tests/e2e_native_stage.py` está **ya implementado**: browser Playwright + app JM + Companion local + vídeos sintéticos + FFmpeg + receta y MP4 local, con recuperación de vídeo; **no se ha vuelto a ejecutar en esta auditoría** ni incorpora login Owner ni separación de dos tenants. No atribuir al flujo completo de Owner sus resultados.

## Diferencias que siguen sin resolver

1. **La instancia JM actual y sus múltiples rutas no están autorizadas por Owner UUID**. No se debe montar el editor original sobre un servidor Engine global y hacer proxy indiscriminado de `/api/v1/*`.
2. **Las identidades JM (`wizard project_id`), Owner UUID, Push pack ID, Show y carpeta local Companion son distintas**. Hace falta un mapeo explícito de proyecto y alcance de sesión / recuperación, sin duplicar bases de medios.
3. **La UI original JM debe permanecer intacta** (Stage/Push/Show). El usuario decide sobre UX; objetivo selector contextual por modalidad, no dashboard intermedio ni botones de Engine.
4. **Los endpoints multimedia específicos** (`/wizard/*`, `/edit/*`, `/montara/push/*`, `/montara/show/*`, uploads y respuestas de preview/range) requieren adaptación y política owner+project, no otra suite de apertura.
5. **Compatibilidad Windows**: Companion físico anterior Windows 0.6.2 y JM candidato 0.6.10; versiones/recetas no equivalentes. El render local y el control de update/tray siguen pendientes de verificación humana.
6. **Seguridad / cloud-neutralidad**: la interfaz de ejecución debe ser portable; systemd es adaptador Linux. No fijar Cloudflare, GCP, 4/8 vCPU ni 16GB en la lógica.
7. El código experimental I34–I37 es laboratorio y **no instalado** en el broker de sistema, que sigue en I27. No confundir un test de sockets todos bajo un mismo UID con prueba física de distintos tenants.

## Cambio de plan operativo — sin más laboratorios duplicados

**A. Integración funcional única, primero Stage:** elegir referencia de editor JM más actual, comparar contra `main`, conservar scripts HTML/JS/CSS y tests E2E; conectar Owner UUID a proyecto JM y su catálogo privado; enrutar operaciones mínimas de edición y metadatos hacia Engine/worker aislado tras control owner y generación. Ninguna nueva portada o editor provisional.

**B. Transporte de medios ya existente:** reutilizar `web/companion.js` y `companion/` y mantener originales locales; enlazar proxies/manifiestos/recetas con el proyecto privado, versión pinneada y recuperación. Probar `tests/e2e_native_stage.py` adaptado al aislamiento Owner y luego dos usuarios.

**C. Resto de mundos:** extender el mismo aislamiento y mapeo, respetando rutas independientes Push y Show. Preservar flujos de recuperación y UI.

**D. Gate humano:** cuando A–C estén operativos en beta restringida, Fernando prueba su Windows real con Companion, tray/update, un proyecto en Stage y export MP4, luego Push/Show. No solicitar su participación antes de que el recorrido funcione sin pasos técnicos ficticios.

**E. Main:** esperar a que Chema incorpore su gran rama; comparar nuevo `main` con `fernando/integracion`, resolver diferencias mínimas y **no fusionar hasta beta verificada**.

## Política nueva para evitar repetición

Una nueva pieza de infraestructura solo se justifica si supera un **gate de producto todavía no demostrado** (primero editor JM autenticado con owner, después proxies reales en Engine privado, después render Companion Windows), no porque añada un nuevo número Ixx o repita las pruebas de I20–I27. Mantener regresiones existentes y CI; no duplicar archivos de pruebas equivalentes salvo que evidencien un riesgo nuevo.
