# JÚPITER EX-14H — Evaluación científica del coste real de reproyección 360

**Fecha:** 2026-11-03. **Estado:** auditoría histórica, código actual y bibliografía verificada; SIN benchmark nuevo, SIN tocar motor ni servicios. Responsable: laboratorio FER.

## 1. Objetivo
Medir el peso en una exportación STAGE representativa de (i) decodificación del original HEVC, (ii) cálculo de mapa geométrico NumPy, (iii) remap OpenCV CPU/Metal, (iv) codificación y transporte pipe a FFmpeg, sin extrapolar microbenchmarks ajenos al pipeline. Se mantiene la ruta de revisión EX-06/07/13 en ZuckerVideos PR #51 frente a `claude/recover-montara-engine`; NO reensayar ni integrar unilateralmente.

## 2. Lo investigado ya — no duplicar
- `docs/lab/JUPITER_F4_REAL_360_FIRST_BENCHMARK_2026-11-01.md`: **v360 de FFmpeg estático**, HEVC real de 5 s, output1080, Lanczos media/mediana del estudio original 18.468s versus bilineal 15.5645s, diferencia 15.72% (LBBL, dos muestras cada variante). No es la ruta `native_remap` del engine.
- `docs/lab/JUPITER_F4_REAL_STAGE_FOUR_INTERPOLATIONS_2026-11-01.md`, `JUPITER_F4_REAL_360_CLOSURE_2026-11-01.md`: otro tramo HEVC real de 5s, v360 L-linear-cubic-spline16; medias Lanczos 14.90s, bilineal 9.17s (−38.46%), SSIM bilineal vs Lanczos 0.990657 y PSNR 45.640404 dB; solo dos repeticiones y visual a escala.
- `docs/JUPITER_19_V360_RESOLUTION_DURATION_MATRIX_2026-10-28.md`: 18 renders sintéticos 4/6/8K, 2/5/10s, mejoras 29–51% en filtro FFmpeg `v360`. No Stage ni cámara real.
- `docs/lab/JUPITER_FOCUS_EXPORT_EX05_REAL_OPENCV_RESULTS_2026-11-01.md`: `native_remap` CPU OpenCV real HEVC 3840x1920→960x540, 11 frames medidos, mapa ~35.394ms, remap cubic 29.193ms, lineal float 13.449ms, convertMaps 1.762ms + remap fixed 8.787ms. Excluye decode/encode; map generation supera el coste del remap cubic en esa muestra. No extrapolar a 1080.
- EX-06, EX-07, EX-13: ramas `fernando/ex06-engine-lab` **publicadas** con 4 commits en ZuckerVideos PR **#51 draft**, opt-in y sin modificación del default. EX-07 fast wrap, EX-13 smart unwrap, EX-06 bilineal opcional. Los experimentos de preparación fueron en rutas controladas; no es evidencia Stage completa.
- `docs/lab/JUPITER_EX14D_STAGE_EXPORT_STATIC_AUDIT_2026-11-03.md` y `docs/lab/JUPITER_EX14E_03_EXISTING_PERFORMANCE_FINDINGS_2026-11-03.md`: tres manifiestos Stage/YouTube con times de segmentos, uno de seis planos pero `projection=null`; no acreditan uso 360. Historic jam real 628s output, export1388.1s (8CPU) y otro 654s export4101.5s (4CPU): no comparables, `shots` no registrado.

## 3. Funcionamiento ACTUAL confirmado en ZuckerVideos `claude/recover-montara-engine`
`core/stages/export.py::_render_segment` comprueba `native_motion` cuando hay `spherical_shot`, proyección equirect y movimiento. Invoca `core.spherical_motion.run_reprojected_command` con el original y los comandos del codificador; por otro camino, los planos estáticos pueden pasar por filtros FFmpeg. Por defecto usa `SPHERICAL_EXPORT_MOTION_MODE="native_remap"`.
`core/spherical_motion.py::_run_reprojected_command` ejecuta:
1. FFmpeg proceso decodificador `-threads 2`, selecciona frames (FPS) y convierte a BGR24 vía stdout;
2. frame NumPy BGR leído por `readinto` (buffer reutilizado), mapa `reproject_maps` generado cuando cambia `pose`; usa grid cache LRU y una rejilla de 1/3 con `cv2.resize` cubic;
3. `cv2.remap(...INTER_CUBIC,BORDER_WRAP)` a 1920x1080, a menos que `try_remap` Metal resuelva en hardware;
4. flujo raw BGR a stdin de segundo FFmpeg para filtrado y codificación H.264.
Los dos FFmpeg **se solapan** con el bucle Python por pipe/buffers. El tiempo dedicado a lectura/escritura incluye posible bloqueo por backpressure; la suma de etapas CPU no es igual al wall ni debe interpretarse automáticamente como camino crítico.

**Limitación de telemetría:** `performance.segments[*].ffmpeg_sec` engloba render y potenciales reintentos: no desglosa decode/map/remap/pipe/encode ni captura el backend realmente usado. Los `spherical_shot` se encuentran en el edit plan; los manifiestos antiguos pueden no identificar por segmento. Para inferir impacto global se necesitan tiempo/peso por cada segmento esférico, número de cuadros y flags/método efectivo.

## 4. Bibliografía reciente verificada y aplicabilidad
1. ACM VRCAI 2026 `Efficient Projection of Panoramic Video onto Cube-Based Layouts for Immersive CAVE Visualization`, DOI **10.1145/3779232.3779286**. Demuestra proyección acelerada con CUDA/FFmpeg, layouts cubo 8K60, precomputación seam-aware y acceso a memoria optimizado; reporta <1ms de reproyección **solo en su GPU, pipeline y destino cubemap**. No es una métrica esperable de la VM GCP CPU ni del recorte perspectiva Stage. Uso: investigar coste potencial de transferencias y arquitectura GPU **solo tras medir**.
2. OpenCV documentación oficial `remap` / `convertMaps` https://docs.opencv.org/4.10.0/da/d54/group__imgproc__transform.html . Conversiones a mapas fijos suelen acelerar el remap; **ya experimentado en EX-05**; usar para contrastar compatibilidad y precisión, no anunciar speedup nuevo.
3. IEEE Signal Processing Letters 2025, `Viewport-Patch Extraction Enhanced 360° Video Quality Assessment`, DOI **10.1109/LSP.2025.3646129**. Motiva evaluar distorsiones con regiones del viewport en vez de confiar solo en imágenes ERP. **No propone acelerar la exportación**.
4. IEEE Transactions on Image Processing 2025, `Subjective and Objective Audio-Visual Quality Assessment for Omnidirectional Videos`, DOI **10.1109/TIP.2025.3613957**. Motiva medir calidad perceptual, motion y audio además de métricas agregadas; no ofrece un ajuste de encoder.
5. `NeRV360: Neural Representation for 360-Degree Videos with a Viewport Decoder`, arXiv **2512.20871** (dic2025). Integra viewport en decodificación desde una representación neural; **incompatible directamente con HEVC de cámara existente**, no prometer que acelere los originales de Montara.
6. 2024 `Remote expert viewing, laboratory tests or objective metrics: which one(s) to trust?`, DOI **10.1186/s13640-024-00630-7**. Recomienda métricas objetivas más pruebas visuales en casos ambiguos. Aplica a política de aceptación, no a velocidad.

## 5. Hipótesis ordenadas por valor informativo
- **H0 / GATE 1:** el peso del 360 en los proyectos es desconocido. Antes de benchmark, cruzar `edit_plan.segments[*].spherical_shot` con `export_manifest.performance.segments[*].ffmpeg_sec` por índice y sumar duración de planos clasificados. Medir participación en *tiempo de vídeo*, por separado de wall solapado. Si no hay muestra 360 previa, documentar ausencia y diseñar un fixture real mínimo.
- **H1 / GATE 2:** en motion activo, la generación de mapas es cuello importante de CPU; EX-05 sugiere map 35.39ms/frame a 960x540. Revalidar en 1080 solo si Stage real tiene porcentaje 360 material.
- **H2:** la decodificación HEVC 4K o la transferencia BGR24 por pipes limita fps, pese a que remap por sí solo sea rápido; hay que medir bloqueo y subprocesos para no achacar a una función la latencia global.
- **H3:** EX-07/13 reducen coste del mapa preservando output en escenarios seleccionados; verificar impacto de fase/E2E con flags opt-in y variante baseline contra mismo commit, una sola variable. La comparación está preparada en PR #51; **no duplicar bench** antes de revisión de Chema.
- **H4:** en CPU vs Metal la asignación de costes cambia. Mac/RunPod es estrato separado; GPU no se presupone disponible.

## 6. Protocolo propuesto, no ejecutado
**Etapa A, cero render:** inventariar manifiestos ya existentes SOLO en proyectos de FER; extraer datos minimizados (proyecto identificador neutro, segmento índice, duración, si spherical_shot, movimiento activo, fps, ffmpeg_sec, cached, backend disponible) sin mostrar nombres de medios/rutas. No clasificar por campo `projection` solamente: puede ser null cuando exista `spherical_shot`.
**Etapa B, si falta telemetría:** instrumentación opt-in en laboratorio aislado (no mutar globales CV2 ni código producción), contadores con `perf_counter_ns` para readinto/decode_wait, map, remap, encoder_write_wait, total; CPU de ffmpeg separado si viable. Logs solo acumulados, sin un registro por fotograma. No tratar write_wait como tiempo CPU encoder, puede bloquear por buffering.
**Etapa C, con consentimiento VM libre:** segmento 360 real HEVC 3840x1920 de 2–5s, 1080p30, movimiento congelado y/o dinámico en grupos distintos, caché controlada, al menos tres pares alternados baseline/instrumented; al mismo tiempo verificar frames, PTS, duración, calidad visual, audio cuando procede. Para identificar sobrecoste del propio perfilador, comparar instrumental ON/OFF en A/A.
**Etapa D:** intervenir una sola variable por vez con código de rama propia/revisión de Chema; medir mediana/dispersión y probar QA visual y audio; no comparar tiempos de prueba v360 con native_remap.
**Condición de STOP:** fase no es material para tiempo total, mejora no robusta o no supera coste de complejidad/cambio visual.

## 7. Decisión
**PRIORIDAD INMEDIATA: clasificación read-only de planos 360 en manifiestos existentes.** Ningún benchmark autorizado todavía y ningún parche a engine, mixer, main o submódulos. Informar a Fernando antes de ocupar recursos compartidos. Investigar GPU solo si la distribución de costes demuestra que la reproyección domina y que el presupuesto/infraestructura la justifican.

## EX-14H-01 — Inventario efectivo de manifiestos existentes (operador, 2026-11-03)
Se ejecutó un script read-only que cruza `artifacts/edit_plan.json` y `artifacts/export_manifest.json` de cuatro proyectos FER, clasificando estrictamente como 360 cuando el objeto `spherical_shot` es un diccionario no vacío. Resultado total: **14 entradas de segmentos, 0 con `spherical_shot`**, ningún segmento con etiqueta 360; cuatro proyectos pero solo tres patrones de montaje (dos comparten seis cortes de duración idéntica). No deducir ausencia universal de 360 en Montara ni cuantificar coste de 360 desde estas muestras.

| Proyecto | Segmentos | 360 | Duración editada | Wall segmentos s | Wall export s |
|---|---:|---:|---:|---:|---:|
| montara-focus-iphone-original-03 | 1 | 0 | 4.0 | 11.134 | 15.485 |
| montara-focus-real-mini-01 | 1 | 0 | 4.0 | 6.593 | 9.628 |
| montara-focus-ac-true-edit-01 | 6 | 0 | 20.0 | 18.079 | 43.365 |
| E2E stage.zuckervid | 6 | 0 | 20.0 | 109.354 | 186.427 |

**Resultado:** sin observación Stage real de `native_remap` 360 con desglose de tiempo. Los tiempos muy distintos de los dos montajes de seis cortes NO son prueba de velocidad por CPU ni diferencia de codec, dada concurrencia y configuraciones distintas. `projection` puede ser nulo incluso en planos esféricos; para clasificar un render futuro comprobar `spherical_shot`, probe de fuente, `runtime_motion_enabled` y condiciones reales de `_render_segment` (no solo etiqueta del plan).

**Siguiente puerta, cero render:** inventariar únicamente carpetas de proyecto FER con `artifacts/edit_plan.json` y manifiestos que tengan `spherical_shot`; no escanear datos `jm`, no volcar rutas de medios, no hacer `rglob` de todo el HOME sobre grandes originales. Si no hay pareja plan+export 360, optar por un único fixture real de 2-5 s e instrumentación de etapa bajo laboratorio aislado, previo aviso y preflight VM compartida. 

## EX-14H-02 — Búsqueda ampliada de renders Stage 360 (operador)
Ejecución de inventario read-only en carpetas de laboratorio FER: **6 planes examinados, 0 con segmentos `spherical_shot` no vacío**. La búsqueda incluyó proyectos montara-/jupiter- y subárboles E2E bajo datos FER, sin entrar al home de JM. No demuestra ausencia de grabaciones 360 históricas ni excluye otras codificaciones del plan, únicamente que el selector inspeccionado no encontró planes Stage 360. Se **cierra** el rastreo repetitivo de manifiestos FER conocidos.

**Gate siguiente:** EX-14H-03, perfil de pipeline **real de native_remap** sobre una muestra HEVC 360 ya usada en F4/FOCUS, sin tocar el motor original. Instrumentar tiempos readinto, reproject_maps, cv2.remap, stdin.write, cierre/espera del codificador y wall total con misma geometría/size/fps que export (1080p30), registrando distribución y coste propio del profiler. Deben conservarse outputs y verificar fps/frames, duración, color, movimiento y calidad. **No medir** si JM está renderizando; coordinar con FER y abortar si preflight muestra actividad. Sin pruebas de otras interpolaciones: EX-05/F4 ya las cubren. La fuente de 2 segundos no constituye Stage E2E ni muestra distribución de planos de una jam real.

## EX-14H-04/05 — Inventario real y verificación de versión (operador, 03-11-2026)
Carpeta compartida FER con 3 originales, 6.188 GiB en total. Mediante `ffprobe -select_streams v:0` y `git status --porcelain`:

| Fuente anónima | Formato | GiB | Codec | Resolución | avg_frame_rate | Duración (s) | PixFmt | Color |
|---|---|---:|---|---|---|---:|---|---|
| A | MP4 | 0.531 | H.264 | 1920x1080 | 25/1 | 89.760000 | yuv420p | bt709 primaries/transfer/space |
| B | MOV | 3.308 | H.264 | 3840x2160 | 2218725/74012 (~29.978) | 986.825011 | yuv420p | bt709 primaries/transfer/space |
| C | MP4 | 2.349 | HEVC | 3840x1920 | 25/1 | 911.640000 | yuvj420p | bt709 primaries/transfer/space |

Motor local en checkout `ff9baf4`, worktree limpio. Archivo `engine/core/spherical_motion.py` SHA256 **2b8d165172aa09308d442e0e8f1c5859dcd227cc07f6f35e0473a78a9a6e4bcf**; código del mismo ref inspeccionado en GitHub con `readinto`, `reproject_maps`, `cv2.remap` y pipe de salida. OpenCV **4.11.0** disponible en Python virtual verificado. CPU en último preflight: ningún ffmpeg ni ffprobe activo, load1 0.12 (valores de 5/15min 3.54/11.15); el estado es instantáneo y exige preflight inmediatamente antes de cualquier render.

Interpretación: original C es fuente idónea ya probada en los experimentos F4; el hecho de que el MOV B tenga `avg_frame_rate` ~29.978 **no demuestra VFR** ni se debe etiquetar como tal sin mirar `r_frame_rate` / PTS. `yuvj420p` para HEVC C requiere preservar rango/color al interpretar cambios; no modificar tratamiento de pixfmt ni interpolación para el primer perfil.

**Siguiente gate:** perfilador Stage-native-remap de duración limitada, con checkpoints de metadatos y registro agregado, 1080p30, mismo `shot` y movimiento que usaría el motor, sin alterar `engine/` ni tocar originales. Priorizar medir `readinto`, `reproject_maps`, `cv2.remap`, `stdin.write`, `wait`; separar costes de bloqueo/arranque y no atribuir CPU sin medición adicional. Comparar contra invocación sin instrumentar para estimar overhead. No ejecutar hasta confirmación de VM libre.

## EX-14H-06 — Primer perfil instrumentado de pipeline real (operador, 03-11-2026)
**Se ejecutó una sola muestra exploratoria de la arquitectura de reproyección, sin editar el motor.** Versión local reportada `ff9baf4`, OpenCV `4.11.0`. Original HEVC 360 real 3840x1920, t=840s durante 2s, salida1920x1080 30fps (60 frames) H.264 libx264 `-preset veryfast -crf 23 -threads 2`. Movimiento artificial de yaw +0.3°/frame, pitch −30°, fov100°, llamada al `reproject_maps` original del motor, `cv2.remap INTER_CUBIC BORDER_WRAP`, pipes con FFmpeg. **No Stage completo, ni receta de movimiento exacta generada por `motion_pose`, ni experimento de producto.** Preflight load1 1.67, 0 ffmpeg/ffprobe detectados; Chema indicó VM libre.

Resultado observado `ffprobe`: 60/60 frames, 1920x1080, 30/1fps y 2.000000s, 711815 bytes. Wall 8.565s, rendimiento efectivo 7.01 fps. Los originales no se modificaron; MP4 y logs temporales eliminados.

| Instrumentación | Mediana ms/frame | Suma s / 60 frames | Máximo ms/frame | Cociente suma/wall |
|---|---:|---:|---:|---:|
| `decoder.stdout.readinto` con espera | 24.532 | 2.241 | 441.231 | 26.2% |
| `reproject_maps` NumPy+resize | **64.121** | **3.874** | 84.093 | **45.2%** |
| `cv2.remap` cubic | 24.022 | 1.469 | 34.090 | 17.2% |
| `encoder.stdin.write` con espera | 8.404 | 0.584 | 21.473 | 6.8% |
| **Wall** | — | **8.565** | — | 100% |

Las cuatro sumas dan **8.168s**, quedando ~0.397s fuera del cronometraje explícito (incluye arranque/cierre, overhead Python/sondeo y espera final), sin afirmar que ese resto sea exclusivamente codificación. `read_ms` y `write_ms` son tiempos transcurridos bloqueantes de transferencia y esperas en tubería, **no** CPU propia de decodificador/codificador. Los procesos FFmpeg trabajan solapados; cocientes no son fracciones de CPU ni efecto causal de sustituir un algoritmo.

**Lectura científica:** `reproject_maps` es la operación individual instrumentada más costosa (**3.874s, ~45.2% del wall**); cuello candidato de CPU, **no cuello crítico E2E probado**. Confirma dirección de EX-05 en 960x540 (map ~35.394ms/frame promedio excluyendo primer frame), pero **no es comparación A/B** por distinta resolución, estadístico, cargas y receta. La mediana de `read_ms` oculta un pico de arranque de hasta 441ms. No extrapolar a jam, metraje largo, Mac/Metal, HDR, todos los movimientos o escalado de concurrencia.

**Siguientes gates mínimos (sin duplicar):**
1. Validar la carga observada y overhead del perfilador con una repetición idéntica acotada (si VM sigue libre) y considerar control ON/OFF para cuantificar intrusividad; registrar entorno, variación y CPU/mem si se dispone. Solo después declarar línea base estable.
2. Determinar sin ejecutar pruebas repetidas si EX-07/13 de la rama experimental PR #51 ya incluyen resultados sobre generación de mapa a 1080p con input real. Recuperar sus resultados y diffs primero; **no volver a probar lo ya validado**.
3. Si los resultados EX-07/13 no cubren el pipeline 1080p E2E, A/B opt-in de **una sola variante** sobre idéntico segmento y movimiento, manteniendo SHA, codec y caché. Comparar tiempo map y wall, junto con QA frames/PTS/geometry/color; no asumir bit-identidad para EX-06 bilineal.
4. Para aislar decodificación/encoder, distinguir espera sobre pipe del trabajo real de FFmpeg y medir procesos con observabilidad externa; no asignar 2.241s exclusivamente a decode CPU.

**Decisión:** EX-14H-06 es una señal prometedora; **NO autoriza cambio al motor ni promesa de aceleración productiva**. Priorizar mapa geométrico y recuperar evidencia de PR #51 frente a nuevas propuestas algorítmicas.

## EX-14H-07 — Auditoría documental de optimizaciones EX-07/13 SIN CPU/VM (03-11-2026)
Comparación remota de GitHub `amehcgracia-byte/zucker_videos`, base **ff9baf45aef07f0e9f16c489cf5cbd15acbd1b2f** y head `fernando/ex06-engine-lab`: `ahead_by=4`, `behind_by=0`; solo `core/spherical_motion.py` (+54/-10) y tres módulos de tests añadidos: `tests/test_ex06_cpu_interpolation.py` (61), `tests/test_ex07_fast_wrap.py` (69), `tests/test_ex13_smart_unwrap.py` (90). Frente a `claude/recover-montara-engine` actual, ramas **divergidas** (`ahead_by=4, behind_by=7`), de modo que no comparar directamente rendimiento entre heads como si solo difiriesen por el experimento. La base común es `ff9baf4`, igual al motor local medido en EX-14H-06.

**EX-07 fast_wrap:** añadido `_fast_wrap_x_inplace(mx, sw)`: si x ya está [0,sw) evita operación; rango [−sw,2sw) aplica restar/sumar con máscaras; en casos generales y no finitos vuelve al módulo original. Parámetro `fast_wrap=False` por defecto propagado hasta `run_reprojected_command`. Test compara exactitud de mapas x/y `np.testing.assert_array_equal` con dimensiones **960x540**, FOV/presets/yaws parametrizados, y verifica helper en casos extremos.

**EX-13 smart_unwrap:** `_smart_unwrap_if_safe(a, axis)` comprueba finitud y magnitudes de saltos; solo omite `np.unwrap` cuando no se requiere corrección; para proyección estereográfica `sg` usa unwrap tradicional. Parámetro `smart_unwrap=False` por defecto. Test arrays especiales y mapas exactos a **960x540** para presets linear/dewarp/tiny_planet y orientaciones seleccionadas, también con fast_wrap combinado.

**EX-06** `cpu_interpolation='cubic'` por defecto; `linear` solo opt-in, no es bit-exact respecto a cubic (por definición), con tests de selección y preservación del modo en fallback de decoder hardware. No confundir ahorro del remap con ahorro de mapa.

**Lo NO demostrado en esta auditoría:** no se ha encontrado aquí una cifra de mejora EX-07/13 en mapa a **1920x1080** para los 60 fotogramas HEVC del EX-14H-06; los tests de exactitud inspeccionados están a 960x540. Que haya pruebas implementadas no demuestra ejecución CI actual ni rendimiento; no atribuir aceleración observada sin A/B. No se miraron comentarios/reviews de PR #51 ni issue #34, respetando la fase experimental acordada.

**Siguiente gate** con Chema utilizando VM: cero CPU, revisar el protocolo de A/B y riesgos. Al liberar VM, una única comparación controlada (base, fast_wrap, smart_unwrap y ambas si justificado) con funciones remotas sobre el **mismo** `ff9baf4`, resolución 1080 y poses del EX-14H-06; test de igualdad de matrices `np.array_equal`, tiempo de generación mediana/dispersión y end-to-end solo si reducción real del mapa. Emplear diseño alternado y controles de contaminación; **no** activar flags por defecto ni cambiar producción.

## EX-14H-08 — Harness A/B preparado (SIN EJECUTAR), 03-11-2026
Implementación **solo en rama FER**: `experiments/media_optimization/ex14h08_native_map_ab.py`, commit `4732bd3`. No cambios en ZuckerVideos, `engine/`, `main` ni vídeos. Al ejecutar `--execute` (NO hacerlo mientras JM ocupa la VM): comprueba que el engine local es exactamente `ff9baf4`, que el worktree experimental `fernando/ex06-engine-lab` desciende de ese commit y modifica exclusivamente `spherical_motion.py` más tres tests, y que ambos worktrees no tienen modificaciones trackeadas. Comprueba load1 y procesos `ffmpeg/ffprobe`. Importa el baseline como `core.spherical_motion` y el módulo experimental con un alias de `importlib.util` sin alterar ninguno. 
Genera 60 poses dinámicas (yaw 180+0.3°/frame, pitch -30°, FOV100) del experimento EX-14H-06; calcula mapas de `3840x1920` a `1920x1080`, comparando A baseline con B fast_wrap, C smart_unwrap, D ambos. Una ronda de calentamiento por variante y **tres pasadas** completas (180 mapas/variante), rotando orden, con igualdad exacta de ambos arrays `np.array_equal` para cada pose/pasada, medianas y percentil95 y porcentaje sobre mediana A. No procesa fuentes HEVC, no ejecuta FFmpeg y no crea salidas. 
**IMPORTANTE:** estos tiempos son SOLO generación de mapas y por tanto no demuestran mejora E2E; también hay contaminación posible por caché y temperatura (3 pasadas y orden rotatorio atenúan, no eliminan). La forma de las poses es sintética, aunque procede del ensayo EX-14H-06 sobre vídeo real; la geometría no depende del contenido de píxeles. Si falla el guard por cambios del lab, revisar antes de ejecutar: nunca eludir restricciones. **No ejecutar** hasta aviso de FER de VM libre. 
