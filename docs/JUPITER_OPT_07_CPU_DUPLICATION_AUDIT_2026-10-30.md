# JÚPITER-OPT-07 — Auditoría de CPU sin repetir renders (2026-10-30)

## Objetivo y alcance
Identificar trabajo evitable con potencial **material** en la exportación, sin optimizaciones prematuras en el motor ni nuevas pruebas largas. Auditoría basada en el pin `zucker_videos c89e7791ff6200e29c4281b79e84307277f9527f`, documentos del E2E y código existente. **No se ejecutó benchmark.**

## Evidencia reutilizada
- E2E Stage sintético: exportación etapa 195.097 s; recorrido navegador 410.831 s; la VM compartía recursos FFmpeg con jm (no sirve para comparar configuraciones).
- Manifiesto export: total_wall_sec 186.427, wall_sec 109.354, intro 30.824, outro 26.829, 6 segmentos FFmpeg individuales 36.097/33.826/64.501/26.828/11.233/23.349 s. Estos trabajos **se solapan**; sumarlos como tiempo total sería incorrecto.
- 8 vCPU/31 GiB disponibles en VM tras ampliación; no hay evidencia medida para elegir automáticamente `segment_workers>2`. Antes de variar la concurrencia, medir CPU compartida con jm y límites de memoria.
- El código ya tiene caché segmentaria por receta con sidecars atestados SHA-256: `core/stages/export.py::cached_segment_path`, `_segment_cache_stamp_matches`; cambiar cache keys sin cuidar invalidación es inseguro.
- `_video_frame_count` de `core/stages/export.py` utiliza **ffprobe metadata antes de decodificar** y únicamente recurre a `-count_frames` si falta un valor fiable. No duplicar trabajo de optimización para una ruta que ya evita decodificación repetida cuando hay metadatos válidos.
- `experiments/export_profile/benchmark_cadence_batch.py` reúne ventanas ffprobe en un comando y compara timestamps, pero el resumen de suite 8 vCPU **no incluyó tiempos**: recuperar `/home/fer/montara-bench-8vcpu-20261030/cadence.log` en la siguiente sesión de diagnóstico, sin relanzar el test.
- FOCUS A/C valida resolución proxy/original para seis segmentos, pero no demuestra que el procesamiento de un plan editado con proxies sea equivalente al render con originales.

## Priorización y criterio de decisión
**P1: perfil de costes con manifiesto real (sin render nuevo).** Confirmar fases **críticas** y si intro/outro/segmentos se solapan, conteos de cache-hit, filtro vs encoder, uso de librerías nativas 360, y cuántos subprocesos ffmpeg verdaderamente se ejecutan. El tiempo de intro+outro no es automáticamente ahorro: ya hay cachés de logos y pueden ejecutarse concurrentemente.

**P2: minimizar filtrado/decodificación por segmento** solo cuando el perfil muestre coste dominante e identificar rutas redundantes concretas, no extrapolar GOP selectivo (SATURNO-24 redujo ~40% bytes pero ~0.3% tiempo de export en caso controlado).

**P3: ajustar segment_workers y ffmpeg -threads** de forma adaptativa y **solo tras** un perfil de carga compartida, sin alterar defaults ni servicios; comparar calidad de imagen, sync, frames, CPU y wall time. No asociar la mejora de microbenchmarks monohilo al número de cores.

**No recomendar como nuevas optimizaciones:** caché básica de segmentos y frame-count metadata, selección de GOP para ahorro de render sin perfil, stream-copy en fixture 720p→1080p, ni aplicar índice de subtítulos para acelerar FFmpeg.

## Próximo paso operacional, de bajo riesgo
Recoger únicamente en lectura el `cadence.log` y el manifiesto existente de export Stage; registrar esquema y caminos precisos. No tocar `main`, engine, mixer, servicios ni usar ffmpeg. Si el E2E no conserva manifiesto, registrar ese límite y proponer instrumentación mínima de un próximo render de FOCUS A/C, no reproducir Stage por obtener métricas.

**Estado: AUDITORÍA PRIMARIA; candidato P1 perfil crítico antes de modificar código.**
