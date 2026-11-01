# Inventario — rama de Fernando (`fernando/continuacion-montara`)

Índice de capacidades para decidir qué entra en `main`. No sustituye a los informes originales: los enlaza.
Lo audita el equipo de Chema; el equipo de Fernando corrige y amplía.

## Avance de la auditoría
- Rama revisada hasta: `f77ba0e` (incluye la fusión de `main` `e46b685`, sin cambios de producto nuevos) · `main` de referencia: `d2dd61d`
- Familias: **F1–F8 auditadas en primera pasada** (resumen y resultados de cada informe, código de las piezas candidatas). Profundizar solo en la pieza que se vaya a decidir.

Cada utilidad ocupa 10 líneas como máximo: problema · archivos · evidencia · mejora medida · ¿existe en `main`? · veredicto · riesgos · qué leer (3 archivos como máximo) · **Decisión JM** (solo la rellena José Manuel).

---

## F1 · Subida, proxies, acceso local y transferencia selectiva (área compartida)

### F1.1 Proxies locales con caché
- **Problema:** editar sobre versiones ligeras sin tocar los originales.
- **Archivos:** `local_media/proxies.py`, `local_media/session_proxies.py`, `docs/LOCAL_PROXIES_019.md`, `docs/BENCHMARK_B04_FAST_PROXY_CACHE_039.md`.
- **Evidencia:** tests de proxies (`test_proxy_*`, `test_session_proxies.py`); en la VM, 11/11 tests de proxies.
- **¿En main?:** **parcial**. La PR #8 integró la caché revisada y la herramienta de benchmarks.
- **Veredicto:** solo queda la diferencia con lo integrado; resolverla al traer `main` a la rama de Fer, donde hay 2 conflictos en este código.
- **Riesgo:** el bloqueo single-flight es solo POSIX (no funciona en Windows).
- **Decisión JM:**

### F1.2 Vista previa de proxies por HTTP y botón en Cameras
- **Problema:** ver la cámara en ligero dentro de Stage.
- **Archivos:** `local_media/preview_http.py`, `tests/test_local_proxy_preview.py`, `tests/test_stage_proxy_preview.py`, `docs/INTEGRATION_JUMP_02_LOCAL_PREVIEW_039.md`, `docs/INTEGRATION_STAGE_PROXY_039.md`, cambio en `web/montara.js`.
- **Evidencia:** tests unitarios. No probado en un Stage real (lo dice el propio documento).
- **¿En main?:** no.
- **Veredicto:** **no integrar tal cual.** Solo sirve si el servidor está en el mismo ordenador que los archivos: en la VM el proxy llega después de subir el original, así que no acorta la subida.
- **Corregido en `3bbee90`:** `renderCameras()` usaba `$` en lugar de `$$`, que lanzaba `TypeError` y dejaba sin conectar los tipos de cámara y los puntos de vista 360.
- **Decisión JM:**

### F1.3 Puente subidas → proxies
- **Problema:** crear proxies de lo ya subido, con validación de rutas.
- **Archivos:** `local_media/uploaded_session_bridge.py`, `local_media/test_uploaded_session_bridge.py`, `docs/JUPITER_16_UPLOAD_BRIDGE_UNIT_TEST_RESULTS_2026-10-28.md`.
- **Evidencia:** 6 tests unitarios. No conectado a HTTP ni con control de propiedad.
- **¿En main?:** no.
- **Veredicto:** **investigar.** El motor ya crea sus propios proxies en la ingesta (`engine/core/stages/ingest.py`, `proxy_path` frente a `source_path` en el export), así que puede ser redundante.
- **Decisión JM:**

### F1.4 Carpeta local en el navegador (B09, JÚPITER-02)
- **Problema:** reproducir y guardar recetas de edición sin subir los originales.
- **Archivos:** `web/folder-lab.*`, `web/jupiter-02.*`, `docs/B09_BROWSER_FOLDER_ARCHITECTURE*.md`, `docs/JUPITER_02_BROWSER_RW_039.md`.
- **Evidencia:** el usuario lo probó a mano en Windows con Chrome (3 MP4, recortes que se conservan tras recargar). Sin pruebas automáticas.
- **¿En main?:** no.
- **Veredicto:** **candidato de arquitectura** para la Fase 1: un proxy hecho en el navegador mientras el original sube después. Mantener como laboratorio aparte de Stage.
- **Riesgo:** solo Chromium de escritorio (`showDirectoryPicker`).
- **Decisión JM:**

### F1.5 Transferencia selectiva por GOP (SATURNO 20–25)
- **Problema:** subir solo los trozos del original que usa el montaje.
- **Archivos:** `experiments/saturno_20`…`saturno_25`, `experiments/saturno_common`, `docs/SATURNO_24_FULL_SELECTIVE_ISOLATED_RESULTS_2026-10-29.md`, `docs/SATURNO_25_CONTROLLED_TRANSFER_RESULTS_2026-10-29.md`, `docs/SATURNO_FINAL_DECISION_GATE*.md`.
- **Evidencia:** render A/B idéntico (3007/3007 fotogramas, mismo hash del MP4) y **39,8 % menos bytes de medios**, en un caso controlado con fuentes alargadas artificialmente. Transferencia solo en loopback.
- **¿En main?:** no.
- **Veredicto:** **candidato para la Fase 2.** Antes hace falta medirlo en una red real y con material real (códecs y GOP abiertos).
- **Riesgo:** necesita el plan de edición antes de subir el original, y depende del exportador del motor.
- **Decisión JM:**

### F1.6 Validación de fuentes del mezclador
- **Problema:** que el servidor solo mezcle subidas propias y completas.
- **Archivos:** `mixer_adapter/source_access.py`, `tests/test_mixer_source_access.py`.
- **¿En main?:** en PR #15 (`a56f095`, `e15d78f`, `5c54457`).
- **Veredicto:** **integrar.** El propio módulo dice que no implementa propiedad por usuario.
- **Decisión JM:**

---

## F2 · SATURNO 00–19: identidad de fotogramas, paquete parcial y repetibilidad

### F2.1 Teoría y modelo económico (SAT-00, SAT-04)
- **Qué es:** el criterio de qué tiene que llegar a la máquina de render (intervalos usados y sus dependencias de decodificación) y unas fórmulas de punto de equilibrio entre render local, remoto completo y remoto parcial.
- **Estado:** `investigado`. **Veredicto:** referencia para decidir las fases 1–2; no es código.
- **Leer:** `docs/SATURNO_00_*`, `docs/SATURNO_04_BREAK_EVEN_DECISION_*`.
- **Decisión JM:**

### F2.2 Cortes por stream-copy: identidad exacta (FRAME_IDENTITY, GOP_END_BOUNDARY, THREE_CODEC, SAT-02/03)
- **Hallazgo:** un corte con `-ss … -c copy` sobre H.264/HEVC con fotogramas B **no** devuelve una secuencia exacta y contigua, y añadir margen no lo arregla de forma monótona. Solo los vídeos todo-intra salen exactos.
- **Consecuencia:** descarta «subir trozos recortados»; el método válido es el de SAT-11/20–24, que quita GOP enteros conservando los tiempos.
- **Estado:** `validado-lab` con material sintético. **Veredicto:** conocimiento clave para la fase 2; nada que integrar.
- **Decisión JM:**

### F2.3 Repetibilidad A/A del render (SAT-07, SAT-08)
- **Hallazgo:** dos renders del mismo clip con el motor salían distintos (55/60 fotogramas). La causa es libx264 con VBV y varios hilos. Con un control QA del codificador, son idénticos.
- **Estado:** `validado-lab` (Actions 40878313397). **Veredicto:** mantener como control QA para benchmarks y comparaciones A/B. No es un fallo del producto.
- **Decisión JM:**

### F2.4 Paquete parcial y render real (SAT-05, 09–12, 18, 19)
- **Hallazgo:**
  - Primero, un plano de 2 s idéntico A/B (SAT-09).
  - Después, un Stage real de 19 planos idéntico A/A/B con el control de decodificación (SAT-18).
  - En el fixture corto **hacen falta todos los GOP**: el ahorro venía solo de quitar el audio de las cámaras (SAT-11/19). El ahorro de GOP aparece con fuentes largas (F1.5).
- **Estado:** `validado-lab` controlado, con motor `60a7b7e`. **Veredicto:** base de la fase 2; repetir con `c89e779` antes de comparar.
- **Decisión JM:**

### F2.5 Decodificación 360 con `-fps_mode passthrough` (SAT-13–17)
- **Hallazgo:** sin ese ajuste, el decodificador 360 elige fotogramas distintos según dónde empieza la entrada (A/B 47/278). Con él, coinciden exactos en 6 ventanas (1259/1259) y tras la reproyección real.
- **Estado:** `validado-lab`, aplicado solo como control QA, sin cambiar el motor.
- **Veredicto:** **candidato para el motor** (`zucker_videos`): podría hacer los renders 360 más deterministas. Antes, comprobar en E2E que no cambia la salida normal.
- **Leer:** `docs/SATURNO_16_SIX_WINDOWS_RESULTS_*`, `docs/SATURNO_17_REAL_REPROJECTION_RESULTS_*`.
- **Decisión JM:**

## F3 · Recursos de contenedor y cgroup (JÚPITER 11–15)
- **Hallazgo:** `_segment_worker_count` y `_verification_overlap_enabled` del motor miden CPU y RAM del **host**, no los límites del contenedor. En un contenedor de 8 GiB sobre un host grande podrían lanzar demasiado trabajo en paralelo. Medido: 4 procesos FFmpeg en una cuota de 4 CPU / 4 GiB, pico de 1 GiB (JÚPITER-14).
- **Código:** `experiments/container_budget/` (`resource_policy.py`, `cgroup_guard.py` y sus tests, 7 + 4 pasan); parche candidato `patches/engine_overlap_cgroup_v2_candidate.patch`.
- **Estado:** `implementado` fuera del motor; **no reproducido** como fallo real.
- **Veredicto:** **candidato para el motor** si se despliega en contenedor (Docker/compose). En la VM actual no aplica, porque no tiene límites cgroup por debajo del host.
- **Decisión JM:**

## F4 · Vídeo 360: interpolación de la reproyección (JÚPITER 17–19, AUDIT_SPHERICAL)
- **Hallazgo:** cambiar `interp=lanczos` por `linear` en `v360` ahorra entre el 29 y el 51 % de la reproyección (4K/6K/8K → 1080p), con un SSIM de 0,999 frente a lanczos. Medido con fuentes **sintéticas**, fuera del motor.
- **Ya en el motor:** el proxy esférico se omite cuando el movimiento usa el original (AUDIT_SPHERICAL). No duplicarlo.
- **Estado:** `validado-lab` sintético. **Veredicto:** **candidato de alto valor** para los renders 360. Siguiente paso: A/B con material 360 real (caras, letras, cables) y revisión visual. Primero como opción, sin cambiar el valor por defecto.
- **Leer:** `docs/JUPITER_19_V360_RESOLUTION_DURATION_MATRIX_*`.
- **Decisión JM:**

## F5 · Benchmarks de medios (B01–B10, MARS, BENCHMARK_PLAN)
- **Proxies (B03, B04, MARS):**
  - caché rápida sin `ffprobe`;
  - firma acotada contra proxies dañados;
  - un solo generador a la vez;
  - tiempos de audio y vídeo del proxy idénticos al original (0 ms de deriva, también con VFR).
  - **Ya en `main`** (PR #8).
- **Muestreo (B01, B02):** una pasada con `fps=0.2` es unas 2 veces más rápida que siete búsquedas sueltas. Una sola ejecución con material sintético. `investigado`.
- **B09/B10:** inventario de carpetas sin leer los vídeos. El tiempo depende del número de archivos, no de su tamaño. Ver F1.4.
- **Plan de benchmarks:** protocolo de medición por fases, reutilizable para la medición de tiempos «del minuto 0 al final».
- **Decisión JM:**

## F6 · Nube e infraestructura (LUNA 05–08, JÚPITER 09–10, RunPod, GCP)
- **Contenido:** comparativas de proveedores y créditos, compatibilidad ARM64 (Oracle; el lock es x86_64; varias wheels sí tienen aarch64), kit de humo para RunPod y plan de benchmarks multiplataforma reutilizando el E2E.
- **Dato útil (LUNA-05):** contenedor x86_64 de 2 CPU / 8 GiB, Stage de 100 s: ingest 48 s, sync 12 s, edit 13 s, **render 329 s**.
- **Estado:** `investigado`. **Veredicto:** referencia para decidir dónde se renderiza; nada que integrar. ARM64 sigue sin validar.
- **Decisión JM:**

## F7 · Exportación y perfil (JÚPITER 26, `experiments/export_profile/`)
- **Hipótesis:** la verificación de cadencia lanza 7 `ffprobe`; uno solo con `-read_intervals` daría las mismas marcas.
- **Estado:** `investigado`; ahorro pequeño (arranque de procesos). **Veredicto:** baja prioridad para el motor.
- **Decisión JM:**

## F8 · Auditorías e investigación
- **AUDIT_MIXER_SECURITY:** rutas arbitrarias (cubierto por PR #15), trabajos sin dueño, estado en memoria, bloqueo global, colisión de nombres (cubierto por PR #15), referencias sin límite de tamaño. **Pendiente para multiusuario.**
- **FOCUS_A_C:** la identidad de una fuente depende de su ruta física. Es la pieza que hay que resolver para cambiar un proxy por su original en el render (fase 1).
- **AUDIT_HYBRID_PROJECT_PORTABILITY, AUDIT_JUPITER_03, AUDIT_MAIN_VS_JUPITER:** el esquema de proyecto y las cachés del motor ya existen y no hay que reinventarlos.
- **CROSSWALK_PR6:**
  - render −22 % en la ronda 3 del Mac;
  - **un proxy esférico completo gastó ~866 s que 65 tomas no necesitaron**.
  - Candidato a investigar en el motor: preparar solo bajo demanda.
- **RESEARCH_RADAR, MONTARA_COLLAB_*, START_HERE:** referencias y protocolo previo (sustituido por `docs/COLLABORATION.md`).
- **Decisión JM:**

## Prioridades propuestas
1. **Fase 1–2 de subida** (F1.4, F1.5, F2.2, F2.4, F8 FOCUS_A_C): resuelve la espera al subir.
2. **360 más rápido** (F4) y **proxy esférico bajo demanda** (F8 CROSSWALK): mayor ahorro de render medido.
3. **Determinismo 360** (F2.5) y **cgroup** (F3): robustez del motor, PR en `zucker_videos`.
