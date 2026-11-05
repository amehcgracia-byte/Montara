# PUENTE JÚPITER → URANO — triaje de integración selectiva

**Fecha:** 2026-11-05. **Estado:** lectura GitHub y clasificación; NO se ha ejecutado CI nuevo, merge, despliegue ni prueba de Windows/VM. Responsable documental: laboratorio FER. **Base de comparación:** Montara `main=bec8f85b70af1bde876cfe8a93b61925f4d57305` (0.66 aceptada por JM), `fernando/continuacion-montara` según GitHub en esta revisión. Consultar heads antes de desarrollar: ambos laboratorios avanzan.

## 1. Respuesta a la hipótesis «Chema solo toca estética»

**Refutada parcialmente.** La evolución de `main` no se reduce a UI. Una comparación histórica `e46b685..main` muestra **217 commits** (incluye documentación y merges), con cambios sustantivos en `companion/companion.py`, `companion/local_video.py`, `companion/video_jobs.py`, `companion/video_recipe.py`, `web/companion.js`, `web/montara.js`, `web/full-session.js`, `full_session.py`, `resumable_upload.py`, `mixer_adapter/*` y el pin `engine/`. La comparación no prueba que cada cambio sea incompatible, pero **sí evidencia solapamiento técnico y exige revisión por funcionalidad**.

- JM 0.66: motor fijado `bfb964c3`, mixer `f15ff91`, Companion 0.6.5 (STATUS-JM), recuperación web `?resume=frames`, vídeo Stage local y mezcla local ya existen. `zucker_videos/main` no es la referencia del motor efectivamente fijado.
- `main` vs `fernando/continuacion-montara`: **diverged**, FER 430 commits ahead / 95 behind según comparación GitHub. Son commits, NO funcionalidades. Muchos archivos experimentales e informes solo en FER. **No fusionar toda la rama** ni buscar actualizarla mediante merge masivo para desarrollar URANO.
- `INVENTORY-FER.md` sigue siendo índice valioso F1–F8, pero su cabecera cita referencias históricas (`f77ba0e`, `d2dd61d`); este informe añade la decisión actual sin reescribir los hallazgos originales.

## 2. Matriz de decisión

| Componente y evidencia previa | Solapamiento con `main` | Decisión / prioridad | Gate antes de integrar |
|---|---|---|---|
| **Companion Windows W1–W3S**, PR Montara [#74](https://github.com/amehcgracia-byte/Montara/pull/74), Windows CI W3Q PASS histórico | **Alto**: `companion.py`, `video_jobs.py` y `web/montara.js` cambian también en `main`; `main` tiene Mac 0.6.5 y render local | **P0: primera PR candidata, selectiva**. Partir de nuevo `main`; separar soporte Windows de política U3C y packaging, preservar rutas Mac | Tests Windows reales focalizados + Linux/Mac relevantes; API health/locate/proxies, BT.709, selector/cancelación, procesos, proyecto local, E2E Linux/capturas; revisar puertos y seguridad. NO distribuir bundle FFmpeg sin cierre jurídico |
| **U3B/U3C** fallback vídeo original, pruebas Node 12 escenarios PASS previos | **Alto**: `web/montara.js` ha evolucionado (Stage, previews y recuperación) | **P0 de arquitectura, PR distinta del port Windows**. Conservar confirmación manual experimental; evitar fallback silencioso | Aplicar cambios a JS vigente, pruebas 12 escenarios + E2E Stage/Push/Show relevantes; no bloquear audio/proxies/medios auxiliares; política backend multiusuario aún por diseñar |
| **FOCUS_A_C / identidad proxy→original**, informes `docs/FOCUS_*` | **Alto**: export Stage nativo y recetas ya existen (JM 0.59–0.66); motor usa rutas y fuentes de proyecto | **P0 antes de URANO persistencia/relink**: evaluar diferencial mínimo, no reimplementar export local | Leer `/edit/native-recipe`, `video_jobs.py`, validaciones de originales y `core/project.py` del motor fijado; solo PR si falta función demostrable |
| **Caché proxies B03/B04 / normalización**, INVENTORY F1.1/F5 | Parcial/alto: PR #8 integrada y Companion crea proxies | **Ya integrado parcialmente: no duplicar** | Comparación puntual de diferencia, prioridad baja salvo fallo medido |
| **Mixer source access**, INVENTORY F1.6 | PR #15 integrada: `mixer_adapter/source_access.py` presente | **Integrado**, no repetir. Ownership SaaS continúa aparte | Tests por tenant cuando se implemente autenticación; no tratar validación de rutas como permiso de cuenta |
| **EX-07/EX-13 optimización 360**, ZuckerVideos PR [#51](https://github.com/amehcgracia-byte/zucker_videos/pull/51) draft, EX-14H cierre | **Motor se movió a `bfb964c3`**; PR #51 se creó contra base antigua | **P1**: adaptar únicamente flags opt-in de EX-07/13 en rama corta de repo ZuckerVideos desde motor actualizado. No fusionar #51 tal cual | Tests engine actuales, A/B sobre fuentes reales y misma máquina, comparabilidad, equivalencia visual/MP4, E2E Stage, revisión 360 Mac/Windows. No extrapolar ahorro al montaje completo |
| **EX-06 interpolación bilineal**, misma PR #51 / F4 | Cambia posible imagen | **Separar, aplazar** hasta revisión perceptual con material real | A/B visual caras/textos/cables y degradación aceptada antes de activar |
| **GOP selectivo SATURNO-20–25**, inventario F1.5/F2 | Arquitectura de export actual evolucionó; sólo loopback y metraje artificialmente ampliado | **P1 de URANO remoto**, no merge ahora | Actualizar contrato del motor, datos reales, red real y costes/bytes/tiempos, preservar fidelidad |
| **Cgroup / workers**, F3 | Motor `_segment_worker_count` y VM actual; hipótesis de contenedor | **Condicional**, esperar a despliegue remoto bajo límites reales | Reproducción bajo cuota cgroup y tests de concurrencia, default estable |
| **Cadence ffprobe, muestreo, instrumentos varios**, F5/F7 | Posibles rutas ya optimizadas | **P2/archivo** hasta cuello real medido | No añadir complejidad por mejoras micro |
| **Carpeta navegador B09/JÚPITER-02 y continuidad local**, F1.4/U2 | Ya existen `montara-project.json`, `projects.json`, `sessionStorage`, IndexedDB y Engine project v1 | **Reutilizar como conocimiento, NO portar prototipo tal cual.** URANO debe resolver persistencia mínima tras cierre/reinicio | Diferencia funcional comprobada sobre `main` actualizado; contrato segura de sesión/propiedad antes de exponer lectura local |

## 3. PR #74: por qué requiere separación

Revisión de ficheros modificados mediante GitHub: **16 ficheros**. Además de `companion/windows_support.py`, `companion/companion.py`, `companion/video_jobs.py`, `companion/windows_tray.ps1`, tests y workflows Windows, modifica **`web/montara.js`** e introduce el flujo U3B/U3C. Está **draft, abierta, sin merge**, HEAD `78518ef0c2ec7a5da9a94eb35fa4653dd976c175`; no es una PR reducida de tres archivos como su descripción original (desactualizada). **No copiar el conjunto del diff sobre `main`**; reorganizarlo en 2+ PR cortas, una para compatibilidad Windows y otra para política de upload, más empaquetado si procede.

La validación Windows W3L–W3Q y aceptación visual 5/5 comunicadas por FER son evidencia valiosa, **pero no garantizan compatibilidad contra el nuevo `main` ni autorizan distribución GPLv3**.

## 4. Orden operativo y criterios de cierre del puente

1. **Primera tarea: revisar diferencial Windows W3 frente a `main` 0.66**. Iniciar rama corta desde HEAD `main`, portar solo adaptaciones Windows, fixtures y tests útiles; **no** modificar Mac, motor, mixer o pines. Dejar la PR #74 como historial hasta extraer todo; no mergearla.
2. **Segunda: U3C explícito** separado, con JS vigente; política comercial Companion-first, subida manual excepcional de pruebas, sin fallback automático. Construir gates de tests por tipo de archivo.
3. **Tercera: FOCUS_A_C diferencial**, solo si evidencia señala una capacidad aún ausente en 0.66. Delimitar qué falla en relink/receta y no repetir render local ya existente.
4. **Después URANO**, en rama nueva desde `main` integrado, enfocando continuidad de proyecto en mismo equipo; el motor, el esquema de proyecto y persistencia actuales son base. Cuentas y aislamiento SaaS más adelante en PR propias.
5. **En paralelo o después:** EX-07/EX-13 selectivos en repo Engine, F4 aparte; GOP y cgroup cuando arquitectura los requiera. No bloquear URANO por todas las optimizaciones.
6. Medición base del **mismo flujo real** antes y después del cambio arquitectónico: bytes subidos/bajados, tiempos E2E, CPU/RAM/disco, caché, calidad, sincronía y coste; distinguir optimizaciones aisladas del efecto global.

**Gate común:** pruebas focalizadas precisas, CI y E2E Linux con capturas examinadas cuando haya cambio de comportamiento; Windows runner y prueba local si se altera Companion Windows; revisar diffs y preservar pin de engine/mixer salvo PR autónoma; rollback y documentación. La autorización comunicada de JM para integrar selectivamente no implica aprobar cualquier cambio automáticamente. Para `main`, solo después de gates superados.

**No ejecutado en este hito:** cherry-pick, código, CI, pruebas en VM, merge, despliegue, modificación de submódulos, publicación de artefactos comerciales.

## 5. Riesgos anotados

- Cambios de comportamiento **no estéticos** en `main`: export nativo, persistencia, Session/Mixer, uploads; no asumir inocuidad de un cherry-pick antiguo.
- Falsa equivalencia entre motor `zucker_videos/main` y motor efectivamente fijado por Montara.
- Reintroducción de subida completa de vídeo original sin consentimiento al copiar rutas viejas de JS.
- PR #74 con descripción obsoleta respecto a sus 16 ficheros; separar funcionalidades sin descartar evidencia Windows.
- Pruebas Linux / CI simuladas no sustituyen validación visual Windows y E2E de producto.
- Paquete FFmpeg Gyan GPLv3: no distribuir al público hasta revisión de licencias.
- No transformar una prueba de carpetas local en arquitectura aprobada ni duplicar Engine project v1.

**Próximo entregable verificable:** PR corta Windows de compatibilidad sobre el `main` actualizado, no continuación indiscriminada de experimentos.
