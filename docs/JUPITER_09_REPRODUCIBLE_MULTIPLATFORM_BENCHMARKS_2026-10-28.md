# JÚPITER-09 — Campaña reproducible de benchmarks multiplataforma
Fecha 2026-10-28. Rama `fernando/continuacion-montara`. **Propuesta experimental, sin ejecutar renders ni cambiar motores, sin desplegar ni consumir créditos**.

## Dictamen
No necesitamos crear otro sistema de benchmarks desde cero. Montara main ya contiene un E2E real de navegador y motor, pruebas sintéticas de media y herramientas CPU de caché. ZuckerVideos (pin `60a7b7e9a39077b36f45057811abd6a833a168ef`) contiene un A/B de render completo y un perfilador de segmentos. El riesgo es comparar mediciones distintas como si fueran iguales. La futura campaña debe asegurar **el mismo plan, la misma entrada y equivalencia de salida** en todos los entornos.

## Inventario comprobado
| Herramienta existente | Qué prueba | Qué NO prueba |
|---|---|---|
| Montara `tests/e2e_journey.py` | Navegador real → servidor → edición → motor → descarga; modes Stage/Push/Mix; `--synthetic` opcional; `--base-url` remoto **destructivo** contra proyecto actual | No es un benchmark aislado de render; esperas, instalación de fixtures y descarga integradas |
| Montara `deploy/preflight.py` | dependencia, ffmpeg, ffprobe, font, ruta /data, auth privado, límites cgroup y smoke AV de 1s | No acredita video 4K/30GB ni rendimiento real |
| Montara `experiments/media_optimization/benchmark.py` | creación de muestra sintética, proxy/scene detection con JSON | No refleja costes de concierto multicámara |
| Montara B03 `benchmark_b03_proxy_cache.py` | `local_media.proxies.prepare` frío y reuso caliente del MISMO proxy, tamaño de salida y ausencia de regeneración | No procesa fotogramas ni mide latencia de navegación en caso caliente |
| Montara B05/B06/B07/B08/B10 | PTS, A/V, receta referida al original, carpeta/inventario, varias regresiones | No sustituyen export E2E ni bench de GPU |
| ZuckerVideos `tools/benchmarks/render_ab.py` | A/B de export por plan congelado, caché privada de segmentos y métricas memoria/I/O | **Mac-specific:** `vm_stat`, `ps`, `pgrep`, `git show` commits Mac. NO ejecutar directamente como comparador arm64/linux |
| ZuckerVideos `tools/benchmarks/segment_costs.py` | descompone costes de decodificar, remap, codificar y verificar | Instrumenta código por sustituciones de texto y commit `8653b4e`; es un perfilador histórico Mac, no genérico |
| PR #6 `docs/BENCHMARKS_HISTORICOS.md` | referencia histórica auditable con N/D | No reemplaza ejecución nueva; sigue en rama PR abierta |

## Contrato de ensayo: antes de gastar un dólar
1. **Identidad:** sha Montara, sha engine, sha mixer, git diff/estado, ffmpeg build/configuración, Python, OS y arquitectura; SHA256 del plan congelado y de fuentes (o firma privada autorizada). Nada de rutas privadas en informes públicos.
2. **Mismo proyecto/plan:** Stage `much-to-me` cuando pueda utilizarse legalmente en cada máquina, misma salida 1920×1080/30 fps, parámetros/segmentos/transiciones/audio, misma versión de modelo y caché declarada. Alternativa pública: fixture sintético **idéntico** distribuible; nunca comparar planes con 16 vs 19 cortes como speedup.
3. **Cuatro fases independientes:** build + cold setup; ingesta/sync/análisis; **render/export aislado**; E2E de navegador con transferencias. Medir cada fase sin sustituir la suma por un valor de otra herramienta.
4. **Cold vs warm explícitos:** sólo limpiar un directorio de cache QA **privado, nuevo, desechable**, jamás cache global/productiva. Cold significa caché privada de segmentos vacía, no OS caches vacías. Warm debe reutilizar exactamente el mismo plan; medir cache hit count.
5. **Repeticiones:** tres ejecuciones por configuración como mínimo si coste/tiempo lo permiten, alternar el orden de las configuraciones; declarar número real, mediana y dispersión. Una corrida sigue siendo evidencia exploratoria, no promesa comercial.
6. **Métricas:** wall CPU por fase, P50/P95 si hay repeticiones suficientes, CPU uso, peak cgroup memory.current/memory.peak y RSS árbol (no sumarlos), disco libre mínimo/pico temporales, bytes de I/O lógico, proxy/final bytes, caché reutilizada, subida/descarga y colas, costes facturados reales, errores/watchdog/cancelaciones.
7. **Calidad:** output full decode, n_frames/fps/duración, SHA si se exige bit-exactitud (no aplicable indiscriminadamente a distinto encoder), SSIM/VMAF sólo con referencia espacial/temporal alineada, offsets y drift AV, proyección y color HDR/SDR, preservación de originales y decisiones manuales. Diferencia visual entre GPU/CPU requiere revisión independiente.
8. **Privacidad y aislamiento:** `tests/e2e_journey.py --base-url` modifica el proyecto actual: NUNCA lanzar sobre datos del propietario ni servidor productivo; instancia y volumen dedicados `montara-qa`, contraseña privada y acceso local/túnel. No subir fixtures privados ni outputs a GitHub. Comprobar cuota de artifacts antes de subir multimedia.

## Campaña en escalera y gates
- **Gate A (sin gasto):** README exacto de comandos, ejecutar `deploy.preflight` y B03/B06/B07 **solo** en entorno local adecuado y QA desechable; revisar que paquete rueda de arm64 existe para cada pin. Historial: contenedor x86 2 CPU/8GiB, Stage output ~100.234s, export ~329.192s, peak cgroup ~1.84GiB, E2E ~811s; valores *solo referencia*, con 16 cortes.
- **Gate B (compatibilidad arm64):** lock ARM64 separado sin tocar `requirements-linux.lock` x86, build `linux/arm64`, preflight y warmup en ARM nativo o contenedor emulado para **compatibilidad solamente**. No hacer benchmark de rendimiento bajo QEMU. Si incompatibilidad nativa, lista exacta paquete/versión/platform; no forzar cambios masivos.
- **Gate C (CPU comparables):** misma arquitectura x86_64 y plan en Google 2 vCPU/8 GB y 4 vCPU/16 GB; 8 vCPU/32 GB si se observa saturación CPU o mejora que justifique costo. CPU real y su cuota deben registrarse. Evaluar si aumentar RAM sin utilizarla aporta algo.
- **Gate D (Oracle ARM):** ejecutar mismo fixture y receta en A1 ARM validado, a un editor/instancia, registrar espacio disponible, cgroup, latencia y resultados. La arquitectura no tiene GPU NVIDIA incluida.
- **Gate E (RunPod GPU):** solo tras baseline, GPU compatible y acceso explícito a las fuentes; A/B `T_e2e = T_paquete + T_upload + T_cola + T_cold_start + T_proc + T_download + T_verify`, medir VRAM y facturación; no basta tiempos de encoder.
- **Gate F (decisión):** costo/resultado por minuto de fuente y por proyecto completo, con control de calidad y privacidad; después plantear scheduler, no antes.

## Comandos que ya existen — sin ejecutarlos aquí
```bash
# PRECAUCIÓN: usar carpeta temporal y host de pruebas aislados; NO producción
python -m deploy.preflight --server --data /data --smoke --output /data/preflight.json
python experiments/media_optimization/benchmark_b03_proxy_cache.py --output /tmp/montara-b03.json
python experiments/media_optimization/benchmark_b06_av_pts.py
python experiments/media_optimization/benchmark_b07_original_export.py
# E2E contra QA vacía; modifica el proyecto activo:
python tests/e2e_journey.py --mode stage --base-url http://127.0.0.1:8091 --output /tmp/montara-qa-stage
```
Revisar previamente variables de auth, volumen y dependencias según `deploy/README.md`. No guardar secretos ni rutas privadas en los resultados.

## Entregable siguiente de ingeniería, solo si José Manuel aprueba
Adaptador Linux para `render_ab.py`: no reescribir render; aislar `vm_stat` y procesos Mac detrás de colector de recursos portable, parametrizar referencia y outputs evitando reutilizar versiones Mac, guardar manifiesto de inputs y añadir comprobación de salida. Alternativa más ligera: extraer sólo el congelado del plan y recopilar por `tests/e2e_journey.py` + manifests actuales. Elegir tras revisar el A/B contra el motor del pin actual y la VM disponible.

## Decisión propuesta
**No activar aún créditos cloud:** primero validar fixture congelado, script, identidad y política de caché. Una vez listo, Google x86 CPU para baseline, Oracle ARM para viabilidad permanente y RunPod para GPU con traslado de datos contabilizado. No introducir Entire ni cambios a main.
