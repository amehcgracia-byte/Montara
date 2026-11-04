# JÚPITER · EX-14H-21–24 — Cierre: optimización 360, cronómetros y branding Stage

**Fecha:** 2026-11-04 · **Laboratorio:** FER · **Estado:** investigación acotada CERRADA, pendiente revisión técnica de JM. **No** integrado en producción. Este informe complementa [EX-14H-17/18](JUPITER_EX14H17_18_REAL_MULTICAM_CLOSURE_2026-11-04.md).

## 1. Alcance y trazabilidad

- Motor de referencia 0.61 de ZuckerVideos: `3ff470ee`; worktree experimental opt-in `f305961` (base más tres commits locales de EX-07/13, adaptador por proyecto y auditoría). **No se cambió el motor fijado por Montara, ni `main`, ni los servicios de JM.**
- Linux, GCP VM FER, CPU, remapeo 360 con original HEVC equirectangular 3840×1920 y salida H.264 1920×1080 a 30 fps. Montaje multicámara de prueba: 12 s, seis cortes/tomas alternando 360 e iPhone; las exportaciones completas se realizaron con cuatro workers efectivos.
- Configuración experimental por proyecto: `settings.export.ex14h11_fast_wrap` y `ex14h11_smart_unwrap`; **ambas desactivadas por defecto**. EX-06 no incluido: requiere auditoría visual aparte.
- Evidencia cruda: JSON de resultados EX-14H-20H, 21C, 21D, 24F y 24L y vídeos en laboratorio privado FER; no adjuntar originales, datos sensibles ni rutas absolutas al repositorio público. EX-14H-21E quedó documentado localmente. Las cifras que siguen proceden de salidas conservadas de ejecución; **no son un nuevo benchmark tras la publicación**.

## 2. EX-14H-20/21/22 — Cuándo sí y cuándo no aceleran EX-07/EX-13

### Política editorial de planos cortos

El motor aplica `SPHERICAL_SHORT_SEGMENT_STATIC_SEC = 2.0` en `_v360_motion_at`: tomas de menos de dos segundos mantienen pose estática. Los tres cortes 360 del plan (1.200, 1.500, 1.967 s) produjeron **una pose distinta cada uno**, aunque sus etiquetas fueran `pull_out`, `pan_left` y `pan_right`. En un escenario experimental de 3 s, `pull_out` y `pan_right` sí cambian de pose, mientras `pan_left` permanece estático debido a sus parámetros de movimiento. **No es un bug ni una petición de alterar la política editorial.**

EX-14H-20H, render nativo estático: doce renders alternados, MP4 iguales dentro de cada escena; tiempos agregados A=20.9573 s y B=21.2023 s (**B 1.17 % más lento**). En 20/21A, un segmento de 36 frames usó **un solo mapa de reproyección**: apenas hay trabajo geométrico que ahorrar. Una microprueba de nueve poses artificiales había mejorado mapas 53.54 %, pero no representaba el movimiento real de Stage.

### Renders reales con movimiento efectivo: comparación A–B–B–A

Dos escenas de laboratorio de **3 s, 90 fotogramas/90 poses**, procedentes del mismo original, con reproducción nativa de reproyección CPU, FFmpeg H.264 `veryfast`, CRF 18, `threads=2`, y ambos flags activos únicamente en B.

| Experimento | Movimiento | A original (media de 2) | B EX-07+13 (media de 2) | Ahorro render wall | Ahorro mapas | MP4 A/B |
|---|---|---:|---:|---:|---:|---|
| EX-14H-21C | `pull_out` | 8.8762 s | 6.7992 s | **23.40 %** | **50.79 %** | SHA-256 idéntico en las cuatro ejecuciones |
| EX-14H-21D | `pan_right` | 8.4719 s | 6.8384 s | **19.28 %** | **50.53 %** | SHA-256 idéntico en las cuatro ejecuciones |

Combinación sobre medias de ambos movimientos: **21.39 % menos tiempo de render** (A=17.3481 s frente B=13.6376 s sumando ambas medias). No extrapolar a un Stage completo, Mac, GPU, otros originales o escenas inmóviles.

EX-14H-22A separó los flags, con dos rondas de 90 poses y comparación exacta de coordenadas:

| Configuración | Media para 90 mapas | Ahorro respecto a A | Mapas idénticos |
|---|---:|---:|---|
| A, sin flags | 4.088 s | — | Sí |
| Solo EX-07 (`fast_wrap`) | 2.781 s | 31.96 % | Sí |
| Solo EX-13 (`smart_unwrap`) | 3.019 s | 26.13 % | Sí |
| Ambas | 2.177 s | 46.74 % | Sí |

**Interpretación:** ambas aportan beneficio en este caso; no sumar porcentajes individuales. La prueba 22A retiene numerosos mapas en memoria y no debe confundirse con un render audiovisual. La evidencia audiovisual relevante son 21C/21D. 35 tests focalizados del worktree experimental: PASS.

## 3. EX-14H-23 — Cronómetros y caché de color

- `ExportStage.run()` incluye preparación previa y cierre. `_render_plan()` inicia su reloj interno **después** de `_color_profiles_for_segments()`; por ello `performance.total_wall_sec` omite el análisis previo de color.
- Histórico EX-14H-17B: ExportStage externo **43.768 s** frente reloj interno **34.382 s** (9.386 s de diferencia). La causa exacta en **aquella** ejecución no fue instrumentada; no asignarla retrospectivamente.
- `performance.phases.assembly = "direct_concat_audio"` es **etiqueta textual**, no segundos. Para EX-17B quedan 3.815 s residuales dentro del reloj calculados por resta entre tiempos conocidos; no deducir que sean desperdicio.
- Caché de color: `cached_or_measure_clip_color` consulta entradas globales versionadas; `COLOR_PROFILE_VERSION` pasó **6 → 7** en commit `4dee4a6` de 2026-11-02, con cambios de recuperación de luz y tratamiento por cámara. Ocho entradas globales existentes eran v6 y no válidas para el motor v7. **Invalidación coherente, no fallo probado de caché.**
- El `RLock` serializa el acceso a mediciones de color entre llamadas del mismo proceso; **no** se demostró contención real. La clave de caché incluye identidad de proyecto: no asumir reutilización entre proyectos.
- Observación incidental: `cache/logs/export.log` contenía secuencias literales `\\n` en vez de saltos de línea (observado en tres proyectos). Incidencia de legibilidad de logs, no causa demostrada de lentitud.

## 4. EX-14H-24 — Perfil instrumentado Stage y coste de branding

Los ensayos cargan una copia aislada del plan de seis segmentos, con originales accesibles de solo lectura, cuatro workers y flags EX-07/13 OFF. Se llamó **directamente `ExportStage.run()`** y se instrumentaron funciones temporalmente en memoria; NO mide los costes de `PipelineEngine.run_sync` ni el pipeline completo. Los proyectos históricos tenían metadatos de otra ejecución E2E (p.ej. `export elapsed_seconds=195.097`), que no se usaron para estos tiempos.

| Medición | EX-14H-24F · bookends externos | EX-14H-24L · branding `within-content` |
|---|---:|---:|
| Duración vídeo resultante | 32.2 s | 12.0 s |
| ExportStage completo | **114.7103 s** | **84.1019 s** |
| Tiempo interno `_render_plan` | 95.611 s | 65.043 s |
| Análisis color, **fuera del reloj interno** | 19.0875 s | 19.0499 s |
| Render paralelo de seis segmentos | 55.840 s | 55.230 s |
| Intro | 19.350 s | no generada |
| Outro | 8.467 s | no generada |
| Cadencia | 3.710 s | 8.136 s |
| Mux final | 1.279 s | 1.518 s |
| Residual interno tras fases numéricas conocidas* | 6.965 s | 0.159 s |

*Resta aritmética, no perfil causal de una función. Los tiempos de trabajadores individuales se solapan: **no sumar sus duraciones como tiempo de pared**.

Hallazgo de reloj en **EX-24F**: diferencia externo-interno = **19.0993 s**, análisis de color = **19.0875 s**, residual = **0.0118 s**; **99.94 %** del desfase externo de **esa ejecución** está explicado por la función de color. En EX-24L la diferencia es 19.0589 s y color 19.0499 s (residual ~0.009 s). No confundir con los 9.386 s del experimento histórico.

**Branding integrado:** EX-24L terminó **30.6084 s antes** que EX-24F (**26.68 %** de reducción calculada sobre 114.7103 s). Esto es una **comparación exploratoria de dos ejecuciones**, no un A/B repetido ni una atribución causal completa: cambiaron política de branding, duración final, configuración global/caché y condiciones temporales. La generación de intro+outro externas costó 27.817 s en EX-24F; la duración aumentó 20.2 s. El render de contenido prácticamente no varió (55.84 → 55.23 s). **`within-content` es funcionalidad del motor de JM, no creación de FER.** No hay en estos registros prueba de equivalencia visual entre modos.

## 5. Aislamiento y límites

- EX-24F redirigió color a raíz privada, **pero el render de segmentos escribió también en la caché global del usuario FER**, porque `export.py` importa `global_segment_path` directamente desde `core.normalization`. No se ha certificado si sobrescribió entradas anteriores; **no eliminar archivos** de esa caché por intuición.
- EX-24J confirmó en memoria que redirigir `normalization.data_root` y `export.data_root/global_cache_root` hace resolver caché de color, segmentos y logos a la misma raíz privada. EX-24L verificó la configuración global privada `branding.bookends=within-content` y creó **dos perfiles de color y seis segmentos en caché privada**. Es aislamiento verificado para esas rutas, no una auditoría exhaustiva de cualquier dependencia.
- Los originales de ambos renders 360 móviles son el **mismo vídeo fuente**; las duraciones móviles de 3 s se ampliaron en laboratorio, porque los tres cortes reales del montaje son inferiores a 2 s y estáticos por diseño.
- No hay verificación de comportamiento en Mac/Windows, GPU, sesiones largas o 2/5/10 usuarios. Evitar porcentajes de velocidad global de Montara y afirmaciones de mejora comercial general.

## 6. Decisión y solicitud a Chema

**Cerrar EX-14H-21–24 como investigación.** No más benchmarks sobre esta hipótesis por inercia. Mantener EX-07/13 como **candidatas opt-in** para revisión selectiva del motor actual, defaults sin alterar. EX-06 sigue separado. No integrar directamente ni actualizar submódulos; cualquier PR de producto debe ser corta, sobre la rama/pin vigentes y superar test + QA visual + macOS/Windows según alcance.

Para JM:
1. Revisar si interesa una integración opt-in de EX-07/13, especialmente para **tomas 360 móviles de 2+ s**, no esperar mejora en cortes estáticos.
2. Conservar/usar `export_manifest.performance` y mediciones externas para reportar **color previo**, **segmentos**, **montaje**, **mux** y **cierre** con límites explícitos.
3. Tener presentes la importación directa de la caché global y el formato de `export.log` al diseñar herramientas de laboratorio; **no se pide modificar producción ahora**.
4. Mantener la separación entre investigación y la hoja de ruta de Companion Windows, render local existente de Mac, audio-first ya implementado en parte, arquitectura de mínimo tráfico y fases futuras URANO/PLUTÓN.

**No solicita merge ni despliegue.** Solo documentación FER para revisión de Chema y su IA. No originales ni credenciales en GitHub.
