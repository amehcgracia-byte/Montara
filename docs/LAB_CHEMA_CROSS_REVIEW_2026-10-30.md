# Revisión cruzada del laboratorio Chema — 2026-10-30

Fuente: `main:CLAUDE.md`, `docs/COLLABORATION.md`, `docs/lab/STATUS-JM.md`, `docs/lab/RUNS.md`, `docs/lab/INVENTORY-FER.md`, issues/PR #32–34. Consultados directamente en GitHub el 2026-10-30. Esta nota no ejecuta pruebas, no cambia engine/mixer/main.

## A. Novedades verificadas
- PR #32 **cerrada**: controles del reproductor debajo del vídeo, corrección de layout flex; evidencia declarada Playwright.
- PR #33 **cerrada**: actualización de STATUS-JM y peticiones al laboratorio Fer. Los dos cierres fueron el 30-10 alrededor de 18:00 UTC. Una PR cerrada no demuestra por sí sola que fue fusionada; verificar merge SHA antes de actualizar despliegues.
- Main STATUS-JM: #20 IndexedDB/handles persistentes; #21 zoom 360 navegador; #22–24 Companion **macOS** proxy 720p / carpeta proyecto / guardado MP4, rangos de canción; #26 vista previa estereográfica y barras por plano; #27–28 registro RUNS; #25/#29 utilidades Mac y autoshutdown; #32 reproductor.
- Issue #34 **abierto**, expresamente dirigido a la IA de Fer (Windows). Mensaje adicional: trabajo con originales completos 6.6 GB, render en VM; 4 vCPU 4101.5 s para 654 s; 8 vCPU 1388.1 s para 628 s. Cambian también inputs, mezcla de cámaras y CPU; no hay speedup causal defendible. La exportación ocupa 98% del motor en el proyecto completo.
- Chema pide por orden: **Companion Windows**, F4 bilineal sobre 360 real, relink/render final local con originales sin cambios al motor aún. Pedir medición de mezcla y coste por cámara; posible PR separada a `deploy/vm/run_history.py`.
- Inventario de Fer auditado F1–F8 en primera pasada por Chema; las piezas F1.2 y F1.3 podrían duplicar ingesta/proxy actual. F1.4 folder browser es laboratorio; F1.5 subida selectiva es candidato fase 2, necesita WAN y datos reales.

## B. Duplicidades / qué NO rehacer
- Evitar nuevo companion macOS o un segundo pipeline de proxies ligado a subida antes de revisar #22–24.
- No duplicar preview 360/browser (#21/#26) ni render esférico actual; usar análisis del inventario y pinned engine.
- No aplicar SATURNO transfer selective a producción sin validación WAN/real GOP.
- No tratar nuestros 45.325 s sintéticos y 231.567 s reales mini como benchmarks comparables con 1388.1 s Chema; pruebas distintas.

## C. Reutilización inmediata
- `companion/companion.py`: API HTTP congelada `/health`, `/locate`, `/proxies`, `/projects`, `/projects/<id>/save`, puerto 47820. Windows: setup de doble clic, diálogo carpeta nativo, búsqueda limitada en ubicaciones comunes/unidades, NVENC/QSV/AMF fallback libx264, proxy 720p CFR H.264 BT709.
- Planes `edit_plan.json` tienen identidad por plano (`camera_id`, `source_path`, `clip_path`); útiles para distribución por cámara en logs, sin cambiar motor si se puede resolver desde manifest/proyecto.
- F4 v360 linear vs lanczos probado anteriormente solo sintético (29–51% mejora, SSIM~.999): benchmark real A/B antes de recomendar.
- FOCUS A/C ya demostró edit con proxies y export desde originales sintéticos; mini real iPhone+Sony eligió **solo Sony**, 231.567 s total, 218.846 s hasta edición, FFmpeg de plano 6.122 s, sin sincronía real. Falta demostrar render iPhone y 360 y localizar costes de EditStage.

## D. Riesgos
- No cambiar engine/mixer ni main ni compaginar CPU sin permiso del laboratorio de Chema.
- Repo público: evitar paths privados, credenciales, identificadores personales en docs/commits.
- `STATUS-FER.md` en main está obsoleto vs commits recientes de la rama; actualizarlo cuando se trabaje en la sincronización documental, no sustituir a la ligera la versión de Chema.
- No afirmar merge de PR a partir de estado closed, ni readiness de producción sin Linux E2E + screenshots según CLAUDE.md.
- No prometer subida 6.6 GB evitada hasta comprobar Companion conectado y original local accesible durante render local.

## E. Prioridad recomendada cuando se retome
1. Revisar rápidamente qué tiene hoy Companion Mac y diseñar paridad Windows sin romper API ni tocar engine; primer objetivo funcionamiento Windows con clip real y tiempos.
2. Medición por cámara del plan/manifest, diferenciando duración de plano, trabajo FFmpeg y mezcla de 360; proponer PR estrecha si hace falta.
3. F4 benchmark real 360 `lanczos` vs `linear`, misma VM, settings y segmento, con SSIM + inspección visual.
4. Arquitectura local render y relink: separar contrato de identidad, tiempos, original y proxy; diseñar antes de codificar.
5. Entregar resultados consolidados por issue #34 / PR pequeñas, actualizar RUNS/STATUS-FER para benchmarks comparables.
