# MONTARA — Carta de navegación / transfusión de mando entre chats
**Fecha:** 2026-11-01 · **Barco:** laboratorio de Fernando (Júpiter) · **Destino:** continuidad técnica y colaboración con Chema

> Este es el documento de arranque para un nuevo chat ChatGPT. Léelo primero; usa GitHub como fuente de verdad y comprueba las novedades posteriores. El usuario puede mantener simultáneamente un chat principal y otro dedicado a encargos concretos: evitar editar lo mismo desde dos chats sin coordinarse.

## 0. Espíritu y forma de colaborar
- Conversación en **español**, tono amistoso y humor de **piratas, capitanes, ballenas, planetas y naves**: JÚPITER (nuestra VM/laboratorio), SATURNO (transferencia selectiva), FOCUS A/C (proxies→originales), barcos en expedición, otro barco Chema. Sin eclipsar rigor técnico.
- Fernando comprende producto/decisiones, no necesita jerga de ingeniería sin traducir. Explicar hipótesis, decisiones, beneficio, coste y limitaciones. Le gusta explorar e imaginar soluciones propias; no tratarlo como mero ejecutor.
- **No confundir PASS de una prueba sintética con producción ni atribuir causalidad a comparaciones incontroladas.** Separar observado, probable, pendiente.
- Respuestas accionables y ordenadas, **un bloque de terminal por paso**, idealmente copiar/pegar; no repetir verificaciones ya superadas. Evitar llamadas excesivas a GitHub y tokens consumidos; condensar lecturas, informar commits y evidencias.
- No lanzar renders en segundo plano ni pedir que aguarde a resultados futuros. Paradas naturales para ocio/novia, sin paternalismo.
- Al acabar una sesión: dejar log de resultados, commits, próximos pasos y alcance para el siguiente capitán.

## 1. Contexto de producto y mapa
Proyecto `amehcgracia-byte/Montara` (repositorio público); vídeo musical SaaS, Stage (YouTube multicámara), Push (Reels), Show y Mixer/jams. `main` lo desarrolla Chema/JM y sus agentes; Fernando investiga eficiencia, infraestructura, proxies, acceso local, transferencia selectiva, Companion Windows y render local.

**Ramas:** `main` Chema; `fernando/continuacion-montara` es nuestra rama experimental. Entregas por PR pequeñas desde rama corta, **nunca fusionar rama experimental entera**. Motor `engine/` submódulo ZuckerVideos, mixer `mixer/` submódulo ZuckerMixer. **Jamás editarlos directamente**. Cambios al motor en su repo y actualización de pin por PR separado. Riesgo actual: `main` ha cambiado el pin del mixer a la rama `claude/winds-synth-bass-lowpass` vinculada a ZuckerMixer PR #8 SIN fusionar en master según STATUS-JM 2026-11-01. No asumir pin antiguo al integrar.

Documentos vivos en `main`, leer en este orden:
1. `CLAUDE.md`; `docs/COLLABORATION.md`.
2. `docs/lab/STATUS-JM.md` y `docs/lab/STATUS-FER.md`.
3. `docs/lab/INVENTORY-FER.md` para evitar duplicidades; `docs/lab/RUNS.md`, `docs/lab/runs.jsonl` y `deploy/vm/manifest.sh` para benchmarks.
4. Issue **#34** `https://github.com/amehcgracia-byte/Montara/issues/34`: canal de comunicaciones **Chema→Fer**; leer los comentarios más recientes y las nuevas peticiones. Workflow `Lab digest` avisa rangos de commits. Puede haber novedades tras este documento.
5. Nuestros informes: `docs/LAB_CHEMA_CROSS_REVIEW_2026-10-30.md`, `docs/FOCUS_AC_SYNTHETIC_PHASE_CLOSURE_2026-10-30.md`, `docs/FOCUS_AC_REAL_TWO_CAMERA_MINI_RESULTS_2026-10-30.md`, `docs/FOCUS_AC_PROXY_EDIT_ORIGINAL_EXPORT_PASS_2026-10-30.md`; además `docs/FOCUS_AC_REAL_STAGE_01_RESULTS_2026-10-30.md`, `docs/FOCUS_A_C_MEDIA_IDENTITY_DEEP_DIVE_2026-10-28.md`.
6. `docs/HANDOFF_FERNANDO_038.md` histórico, ojo con hechos obsoletos.

Colaboración: Chema decide lo que entra en main. Cualquier investigación puede ser compartida; no escribir archivos de su laboratorio o servicios sin coordinar. STATUS de cada barco máx. 40 líneas, mantiene propio equipo. Inventario revisado familias F1–F8. Cada review de main responde A novedades, B duplicidades, C reutilización, D riesgos, E recomendaciones en una pantalla.

**Seguridad:** repos públicos, no publicar secretos, contraseñas, tokens ni rutas de usuarios; contraseñas de VM aparecidas por chat deben rotarse (STATUS-JM lo sigue marcando como pendiente). Ninguna cuenta ni recurso de pago sin autorización explícita.

## 2. Última lectura real de main (2026-11-01)
Leído directamente de `main:docs/lab/STATUS-JM.md`, actualizado **2026-11-01 tarde**:
- Montara **0.52**; PR **#36–38**: copias de escucha Opus en Full session, subir rangos originales de las canciones seleccionadas.
- PR **#39–45**: ondas por canción, tiradores, player, Mixer/Split/Remove, mix por canción.
- **#46–47**: Solo, EQ con high cut, nuevo diseño, no pausar mientras trabaja.
- **#48–50**: Confirm por canción, subida/mezcla en paralelo, waveform y escucha durante detección.
- **#51**: tipos de pista, selección/autorrelleno, Stereo L/R.
- **#52**: arreglo cola por rangos (split ya no vacía cola), estados e inmediatez, círculos, Opus «Rápido», exclusión pistas vacías, ajustes múltiples, L/R enlazadas, mixer ancho y diccionario de instrumentos con preset EQ/compresión/pan/volumen.
- Companion **0.4.0**; en Mac reinstalar ejecutando `companion/install.sh` cuando corresponda; no confundir con `montara-update` ni correr actualizaciones en VM apagada.
- El mixer referencia una rama de ZuckerMixer PR #8 aún no fusionada en master; probar compatibilidad antes de cualquier sync.
- PENDIENTES Chema: verificar canción cortada/vacía con `deploy/vm/audio_check.py`; cola de render para ~10 testers; caché Companion sin límite; historial no registra cámara por segmento; rotación de contraseñas.
- Registro de rendimientos de Chema en `RUNS.md`: con 4 vCPU / 2 cámaras export 4101.5 s para 654 s; con 8 vCPU / 3 cámaras export 1388.1 s para 628 s, ~98% tiempo en export; no comparar causalmente por cambio máquina/mezcla/rango. Subida originales 6.6GB en la sesión de vídeo previa sin Companion.

**Issue #34, comentarios recientes**:
- Contestación a nuestro mini-real: 219 s de `EditStage` pueden ser carga en frío/caché. Probar warm-start, separar `_with_director_quality` y `_load_or_analyze_beats`, y forzar plano iPhone 4K; nunca inferir que ya probamos render iPhone.
- Encargo de primera subida jam rápida: medir localizar/codificar/subir Opus y bitrates 96/48/32/24kbps con tolerancia ±1 s en cortes, streaming durante codificación, subida paralela por partes, diseño almacenamiento directo sin recursos de pago.
- **ÚLTIMO ENCARGO IMPORTANTE 2026-11-01**, comentario `https://github.com/amehcgracia-byte/Montara/issues/34#issuecomment-6558088838`: el cuello de botella en jam 12 canciones es **subida de audio**, VM CPU casi libre, proyección 140 minutos esperando archivos desde Mac. Con #52 rango de canción se sube por defecto Opus alta calidad 192 kbps mono / 256 kbps estéreo (FLAC/WavPack opción), piezas vacías excluidas. **Chema pide ESTUDIAR mezcla en Companion Mac para no subir originales**, subir solo MP3 final por canción. **NO IMPLEMENTAR AÚN**. Entregable: informe corto en `docs/lab/` sobre tamaño de distribución/paquete (numpy, scipy, soundfile, pyloudnorm etc.), tiempo para mezclar canción Mac normal (medir si posible), riesgos, plan incremental, servidor fallback, mismo mixer versionado local/remoto, interfaz sin cambios. Consultar `mixer_adapter/session.py`; cuidado con pinned mixer branch.
- PR #32/#33 de 30-10 figuraban cerradas; antes de afirmar merged, comprobar merge real.
- **NO se hizo merge de main actualizado en nuestra rama durante esta lectura**; solo inspección remota. Hay desfase importante; planear integración sin sobrescribir nuestra rama.

## 3. Infraestructura y reglas de operación
VM GCP **e2-standard-8**, Ubuntu, 8 vCPU / ~32 GB, nodo compartido `jm` y `fer`, servicios solo localhost `127.0.0.1:8101` y `:8102`. Usuario de VM a través de SSH: experimentos bajo Linux user `fer`; checkout `/home/fer/montara-jupiter`, Python `.venv/bin/python`. Las rutas exactas se usan solo en consola privada, no se publican si son sensibles.
- Cada trabajo costoso con `montara-bench <id> ...`, preflight CPU, límite de ejecución; no interrumpir el trabajo de Chema. No tocar HOME ajeno. `git pull --ff-only --no-recurse-submodules origin fernando/continuacion-montara` en nuestra copia, pero comprobar primero el HEAD y el pin actual por divergencias.
- Apagado automático: 60 min sin uso web / 120 min sin teclear SSH si no hay procesos protegidos. Si ambos fuera, **Detener** VM GCP, no eliminar; disco persiste, IP efímera puede cambiar. Verificar estado encendida antes de dar instrucciones.
- Si proyecto compartido sufre update de main, no mezclar sin evaluación de diff de submódulos y tests.
- E2E `tests/e2e_journey.py --output <dir>` pasa en Linux + capturas inspeccionadas = definición mínima de función integrada, no basta unit test.

## 4. Avances confirmados del laboratorio de Fer
### SATURNO — optimización de subida parcial
- SATURNO-24: con material controlado y fuentes largas artificiales **39.8% menos bytes** y MP4 A/B idéntico, 3007/3007 frames; SATURNO-25 transferencia HTTP loopback, no WAN ni producción.
- Con H.264/HEVC+B-frames, cortes stream-copy por `-ss -c copy` NO preservan exactamente serie de fotogramas. Método fiable potencial requiere **GOP enteros y dependencias**.
- `-fps_mode passthrough` en 360 mejora determinismo de decodificación; no parchear engine sin E2E.

### F4 — 360 reproyección
- Benchmarks sintéticos `v360 interp=linear` vs `lanczos`: mejora ~29–51% de coste de reproyección y SSIM ~0.999. Aún exige medición A/B real con original esférico y revisión visual, no declarar optimización de producción.

### FOCUS A/C — proxies editados, originales exportados
- Motor ZuckerVideos utilizado en los ensayos: pinned `c89e7791ff6200e29c4281b79e84307277f9527f` y Mixer `c7a46a6...` en antigua rama; **el main reciente puede tener otros pins**.
- Dos cámaras sintéticas 1280x720, proxies físicos 640x360, `EditStage.run` auténtico: 6 segmentos, invariantes de montaje comparadas 6/6 y 0 diferencias en campos controlados.
- `ExportStage.run` auténtico desde plan proxy: 6/6 `rendered_from=original`, `cached=false`, MP4 H264 1920x1080 AAC, 50,838,395 bytes, 45.325s. Duración total **40.2s** = montaje 20s + INTRO 10s + OUTRO 10.2s. La auditoría `REVIEW_REQUIRED` inicial era **falso negativo** al no contar los logos; script corregido en commit `d6d639d`, su reejecución aún no se registró. Sin escucha/calidad audiovisual A/B.
- Proxies **reales**: iPhone H264 3840x2160 ~987s rotación -180, Sony H264 1920x1080 ~90s, 360 HEVC 3840x1920 ~912s; 4s capturados desde offset 10s de cada original; 9 muestras con error de diferencia normalizada <=0.01634, identidad/relink 3/3 PASS. No es aún E2E con sincronía real.
- Mini-real iPhone+Sony en `experiments/media_optimization/focus_ac_real_two_camera_mini.py`: edit proxy auténtico + export original auténtico, estado `PASS_REAL_CAMERA_PROXY_EDIT_ORIGINAL_EXPORT_MECHANICS`; 231.567s, de ellos 218.846 hasta concluir EditStage; **plan eligió SOLO SONY** (4s desde 10s), FFmpeg 6.122s, `cached=false, rendered_from=original`; MP4 15,268,804 bytes. **NO se exportó iPhone**, NO se validó sync real ni audio completo. 219s posiblemente arranque en frío, sugerido por Chema; no diagnosticado.
- Carpetas/código temporal en VM ya usados: `/home/fer/montara-focus-ac-true-edit-01`, `/home/fer/montara-focus-real-mini-01`; originales en `/home/fer/lab-clips/originales`. Reusar resultados, no re-renderizar por defecto.

### Otros
- OPT-08: fallback codificador Linux para h264_videotoolbox no disponible; pruebas propuestas PASS, **no se cambió engine**. Prioridad menor, fuera de FOCUS.
- Previos E2E Stage sintético 313s (4 vCPU compartida), no comparar directamente con benchmarks reales.

## 5. Hoja de ruta macro (norte)
Construir MONTARA comercial con mínimo tráfico y espera: entrada local y Companion multiplataforma → análisis/edición sobre proxies → acceso seguro a originales SOLO cuando hace falta → export local o render híbrido (CPU/GPU) → calidad con cámaras 360, continuidad entre sesiones y experiencia fluida. Chema desarrolla producto; nuestro barco **investiga, mide, documenta y propone**.
- Audio: estudiar desplazar **mezcla entera al Companion Mac** para subir solo MP3 final; **informe primero, ninguna implementación sin aprobación**.
- Vídeo: FOCUS A/C camino a render original local, aún no validado como flujo integral multicámara real.
- F4 y SATURNO son optimizaciones subordinadas a evidencia, no distracciones sin fin.
- Informes a Chema consolidados cuando valen, pero incidencias relevantes por issue #34 de forma puntual.

## 6. Hoja micro: opciones para iniciar **segundo chat en paralelo**
La tarea más útil y acotada sin bloquear este chat ni necesitar VM:
**«Analiza la viabilidad del MIXER LOCAL en el Companion Mac (encargo Chema issue #34), SOLO INFORME. Revisa main actual, `companion/companion.py`, `mixer_adapter/session.py`, `mixer/` pin y riesgos de empaquetado; produce informe `docs/lab/` en nuestra rama tras coordinar rutas, indicando lo que no está medido. Nunca implementes ni crees recursos de pago.»**
Alternativa: auditoría de compatibilidad Companion Windows **sin código** (API y dependencias) o instrumento de distribución por cámara del plan real solo como diseño.

En el **chat actual principal**, si sigue activo: centrarse en revisión granular de cambios `main` 2026-11-01, estrategia de sincronización de nuestra rama (no fusionar automáticamente), y validar objetivos de FOCUS/F4 sin pisar el trabajo del segundo chat.

## 7. Reglas de handoff activo
- Verificar estado actualizado antes de actuar; este documento es instantánea, no autoridad superior a latest GitHub.
- Desglosar tiempo real y recursos consumidos; evitar benchmarks sesgados. Registrar resultados en `docs/lab/RUNS.md` y `runs.jsonl` conforme a protocolo, con motor/host.
- No publicar toda una conversación ni logs con datos privados.
- Al trabajar en paralelo, asignar **documentos/experimentos distintos a cada chat**; comunicar commits entre ambos, no hacer `git push --force`, resolver integración por merge normal o cherry-pick con inspección.
- Preferencia del capitán: avanzar de verdad, explotar resultados existentes, terminar fases con honestidad, **poco texto de relleno y buen humor**.
