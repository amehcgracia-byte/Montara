# JÚPITER · EX-14H-17/18 — Cierre experimental multicámara real y decisiones de arquitectura
Fecha: 2026-11-04 · Laboratorio FER · Informe para revisión de Chema/JM y su IA.
**Estado:** PASS técnico en un montaje real de 12 s, revisión visual humana positiva con observaciones; **no** validación completa de producto ni de rendimiento comparativo. Sin cambios al motor ni a producción. Evidencias y artefactos ejecutados en VM experimental FER; rutas locales no portables.

## 1. Propósito y alcance
Confirmar con originales reales iPhone + 360 que el motor Stage puede editar/exportar alternando cámaras, reutilizar sincronización acústica y producir MP4 verificable. Perfilar CPU, RAM y tiempo para decidir futuras optimizaciones; no cambiar la lógica editorial de Chema.
La línea de investigación macro de JÚPITER es **portabilidad, tráfico mínimo, cálculo cerca de los datos y GPU solo cuando su coste/beneficio se mida**. No presupone migración de proveedor ni un Stage distribuido ya existente.

## 2. Preparación y referencia acústica
- Originales propios del laboratorio: iPhone H.264 3840x2160 y 360 HEVC equirect 3840x1920; no se publican originales.
- EX-14H-15T: desfase 360 relativo a máster iPhone **−19.040362811791397 s**; referencia independiente **−19.0369 s**, diferencia 3.5 ms, confianza 66.276, verificación 3/3 segmentos, sin fallo de estabilidad. Estudio documentado en `JUPITER_EX14H15T_NATIVE_SYNC_PASS_2026-11-04.md`.
- EX-14H-17A: proxies sincronizados de 12 s, máster real iPhone 12 s; 6 segmentos consecutivos, **3 cam360 y 3 iPhone**, 5 cambios de cámara, segmentos de duración entre **1.2 y 4.6 s**. Originales referenciados a través de enlaces simbólicos por cámara para respetar el validador nativo de identidad; sin cambiar motor.
- EX-14H-17A PASS_MULTICAMERA_EDIT. Medidas: proxy iPhone **2.938 s**, proxy360 **3.848 s**, audio máster **0.165 s**, EditStage **2.706 s**, ensayo total **9.666 s**. No confundir suma de fases con coste general de cualquier proyecto.

## 3. Exportación EX-14H-17B/C/D
- `ExportStage` nativo; **6 segmentos desde originales** (`rendered_from=original`, `cached=false` comprobados), alternancia iPhone/360; audio `master`.
- **PASS_MULTICAMERA_EXPORT_TECHNICAL**: salida H.264 1920x1080, AAC, duración **32.200 s** (12 s contenido + 20.2 s introducción/cierre), tamaño **32,764,435 bytes** (~31.25 MiB); decodificación completa con FFmpeg `-xerror`: PASS. El PASS de decodificación no garantiza ausencia de fallos perceptuales.
- Medidas externas: ExportStage wall **43.768 s**; CPU user **246.582 s**, CPU system **14.174 s** (acumulados, **no interpretar como núcleos reales usados sin auditar medición**); RSS máximo Python **364256 KiB**, RSS máximo hijo **1008556 KiB** (máximo individual observado, NO suma simultánea); verificación/decodificación final **1.519 s**; ensayo de export completo **45.353 s**.
- 17A + 17B ensayo completo **55.019 s** (9.666 + 45.353; son ejecuciones sucesivas y distintas, no un cronómetro monolítico).
- Tiempo acumulado por segmento **92.072 s**, FFmpeg acumulado **86.502 s**. Por cámara según emparejamiento ordenado del reporte EX-14H-17C (verificar correspondencia por índice si se reanaliza):
  - 360: contenido **4.667 s**, tiempo render acumulado **38.143 s**, FFmpeg **35.264 s**; **8.17 s render/s contenido**.
  - iPhone: contenido **7.333 s**, render acumulado **53.929 s**, FFmpeg **51.238 s**; **7.35 s/s**.
  - Relación 360/iPhone ~**1.11** en este ensayo; **NO** equivale a sobrecoste causal de native_remap aislado ni extrapolable a un proyecto completo.
- Telemetría interna export `performance.phases`: `assembly=direct_concat_audio`, `cadence_sec=2.147`, `concat_sec=0.0`, `intro_sec=0.002`, `mux_sec=0.706`, `outro_sec=0.002`, `source_prepare_sec=0.0`, `source_proxy_count=0`; `performance.total_wall_sec=34.382`, `performance.wall_sec=27.71`. La medida externa ExportStage es **43.768 s**; diferencia **9.386 s** sin causa demostrada. La suma de tiempos de renders no es wall debido al solape.
- **Revisión humana (Fernando)** de MP4: alternancia correcta, panorámica del público conseguida, sincronización musical percibida buena, un golpe de manos audible identificable; fundidos/intro/outro y algunos planos parecieron largos/cortos según preferencia. **Solo observación editorial; no petición de modificar lógica creativa de Chema.** No se ha realizado auditoría perceptual automatizada completa.

## 4. ★ STELLAR FINDING — Concurrencia: `1` y `2` significan modo automático
EX-14H-18A (lectura de `engine/core/stages/export.py::_segment_worker_count`) y 18B (cálculo en VM):
- `os.cpu_count() = 8`; afinidad CPU = **8**. El dato histórico de hardware de alguna ejecución anterior (4 vCPU) **no debe reutilizarse como si describiera esta ejecución**. No se capturó en 18B cuota efectiva de cgroup `cpu.max` (ausente o sin salida): queda por verificar asignación/telemetría.
- `segment_workers=1 → 4 efectivos`; `2 → 4`; `3 → 3`; `4 → 4`; `6 → 6`; `8 → 6` con seis segmentos.
- La función: si configuración **>2**, usa `min(configurado, segmentos, 8)`; si **<=2**, selecciona automático por mitad de CPUs visibles, limitado por RAM y otros topes. `ThreadPoolExecutor(max_workers=segment_workers)`; segmentos largos primero. `performance.segment_workers=4` registrado.
- **Consecuencia:** nuestra configuración experimental solicitada de 1 no fue un benchmark monohilo/mono-worker. No proponer escalado ni speedup basándonos en ello. Antes de ensayos A/B, diseñar control verdaderamente explícito de 1/2 workers por vía aislada u opt-in, sujeto a revisión; NO modificar comportamiento global sin Chema.
- `27.78%` de CPU fue cifra observada por usuario en interfaz; denominador/ventana/scope **desconocidos**, no traducir a núcleos usados.

## 5. ★ STELLAR FINDING — Concurrencia distribuida no es suma de CPUs
`_segment_worker_count` observa los recursos del **proceso que ejecuta ExportStage**. Ejecutado en Companion mide cliente; en VM mide VM. No suma CPU local + remota. Un render distribuido requeriría contrato de partición, datos, agenda, resultados y validación. No afirmar que ya existe.
**Contexto ya documentado y NO duplicar:** Companion 0.5.3 mezcla música local con ZuckerMixer y transmite MP3; el servidor valida/puede hacer fallback. Auditorías: `JUPITER_COMPANION_053_STATIC_AUDIT_2026-11-03.md`, `JUPITER_COMPANION_A2_FLOW_FALLBACK_2026-11-03.md`, `JUPITER_COMPANION_A3_SERVER_RECEIPT_2026-11-03.md`. En main JM ha continuado versiones posteriores (0.6.x); no extrapolar la auditoría 0.5.3 sin comparar commits/pins. Existe riesgo estático de **subida anticipada de originales al confirmar canción** pese a mezcla local futura (`JUPITER_COMPANION_CONFIRM_TRAFFIC_GATE_2026-11-03.md`), bytes reales NO medidos.

## 6. Melones aparcados para fases siguientes
### URANO — Web, dominio, correo, hosting y portabilidad
Separar conceptualmente: dominio/DNS, frontend estático/CDN, API-orquestador, almacenamiento, workers de vídeo y correo. No fijar proveedor todavía. Medir **ingress, egress, egress entre regiones/proveedores, archivos repetidos, almacenamiento y latencia**, además de CPU. Dominio e identidad pueden mantenerse al migrar backend; estrategia multi-proveedor debe evitar transferencias inútiles. Presupuestos y tarifas a verificar al decidir, no fijar cifra de coste en este documento.

### PLUTÓN — GPU, RunPod y procesamiento híbrido
Solo después de medir el coste y la fidelidad de decodificación HEVC, native_remap 360, encode, pipes, costes de red y colas. Aprovechar estudios `JUPITER_EX14H_360_PIPELINE_SCIENTIFIC_REVIEW_2026-11-03.md` y PR ZuckerVideos #51; **no activar EX-06/07/13 ni tocar defaults** sin revisión de Chema.

### Audio-first (hipótesis, no funcionalidad certificada)
Auditar qué detección de límites de canción/ritmo, onset/sync y metadatos acústicos tiene el motor actual y qué ya reutiliza. Estudiar si Companion puede enviar primero mapa temporal/receta ligera para reducir procesamiento y transferencia de vídeo. El audio no sustituye scoring visual; **no duplicar detección ya implementada**. Validar el flujo real antes de implementar.

## 7. Solicitudes concretas a Chema y su IA
1. **Revisión informativa, sin merge:** confirmar qué capacidades Stage y Companion son nativas hoy y los commits/pines actuales; no confundir laboratorio FER con producción JM.
2. Revisar semántica de `segment_workers <=2`: ¿auto intencionado? ¿Interesa un modo explícito de 1–2 workers para benchmarks/hosts limitados sin romper interfaz?
3. Indicar si existe instrumentación más granular de decode / generación de mapa / remap / pipe / encode y cuál es el origen de diferencia de temporizadores interno/externo; no inventar causas.
4. Identificar qué mecanismo actual reconoce inicio/fin de canciones y alimenta Cut/Edit; compartir referencia de código/documento antes de diseñar audio-first.
5. Mantener como decisiones de arquitectura: **portabilidad, tráfico mínimo, procesar cerca de los datos, GPU solo con ROI demostrado**. Web/hosting corresponde al futuro planeta URANO; GPU al planeta PLUTÓN. Hoy JÚPITER sigue midiendo Stage.
6. No enviar vídeos originales ni credenciales a Issues. No solicitar nuevo render largo; preservar producción y ramas.

## 8. Estado de cierre
**CERRADO** EX-14H-17A/B/C/D y 18A/B como ensayos documentados. **ABIERTOS**: reconciliación de clocks, cuotas reales CPU, A/B controlado de concurrencia, análisis de costes por fase 360, auditoría audio-first y plan infra (etapas futuras). **No hay cambios de código de producto ni afirmación de integración en main.**
