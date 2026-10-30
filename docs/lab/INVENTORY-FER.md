# Inventario — rama de Fernando (`fernando/continuacion-montara`)

Índice de capacidades para decidir qué entra en `main`. No sustituye a los informes originales: los enlaza.
Lo audita el equipo de Chema; el equipo de Fernando corrige y amplía.

## Avance de la auditoría
- Rama revisada hasta: `f77ba0e` (incluye la fusión de `main` `e46b685`, sin cambios de producto nuevos) · `main` de referencia: `d2dd61d`
- Familias: **F1 hecha** · F2–F8 pendientes (archivos asignados abajo; no volver a leer los de F1)

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

## Familias pendientes
| Familia | Archivos principales |
|---|---|
| F2 · SATURNO 00–19: identidad de fotogramas, códecs, divergencias de render, economía | `docs/SATURNO_0*`–`SATURNO_1*`, `docs/SATURNO_*AUDIT*`, `experiments/saturno_01`–`saturno_19`, `.github/workflows/saturno*` |
| F3 · Recursos de contenedor y cgroup (JÚPITER 11–15) | `experiments/container_budget/`, `docs/JUPITER_1[1-5]*` |
| F4 · Vídeo 360 (v360, interpolación, resolución) | `docs/JUPITER_1[7-9]*`, `docs/AUDIT_SPHERICAL_AND_PAPERS*` |
| F5 · Benchmarks de medios (B01–B10, MARS) | `experiments/media_optimization/`, `docs/BENCHMARK_*`, `docs/B10_*`, `docs/MARS_*`, `tests/test_benchmark_*` |
| F6 · Laboratorio en la nube (RunPod, GCP, ARM64, multiplataforma) | `experiments/cloud_lab/`, `docs/MONTARA_RUNPOD_*`, `docs/JUPITER_09*`, `docs/JUPITER_10*`, `docs/JUPITER_GCP_*` |
| F7 · Exportación y perfil | `experiments/export_profile/`, `docs/JUPITER_26*` |
| F8 · Auditorías, investigación y protocolo | `docs/AUDIT_*`, `docs/RESEARCH_RADAR*`, `docs/LUNA_*`, `docs/FOCUS_*`, `docs/CROSSWALK_*`, `docs/START_HERE_*`, `docs/MONTARA_COLLAB_*` |
