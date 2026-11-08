# URANO · A/B corto Engine antes/después de cambios Stage · 2026-11-08

**Estado:** ensayo ejecutado sobre el servidor GCP FER, **no** aceptación Stage E2E ni benchmark completo de Companion. Sin cambios en `main`, `/home/fer/montara`, `/home/jm`, servicios o originales.

## Referencias exactas
- Montara `main` actual verificado: `beb11d8ea`, Engine `98bce068bfdf931cc153c41aa9b440f9d3c183af`.
- Base anterior a PR #116–#120 (Montara `5becd9e`): Engine `841f4ed55e70c8478f1f9413ac77e548e99f7097`.
- Dos worktrees separados del repositorio de Engine, bajo `/home/fgardel00/urano-ab-20261108/{old,new}`; no se alteró ningún checkout de FER/JM.
- Máquina en esta ejecución: GCP 8 CPU, 31 GiB RAM, FFmpeg 6.1.1, Python del venv ya existente (sin instalar dependencias). Disco: ~70 GiB libre antes y después.
- Originales **solo lectura**, sin subir material: `/home/fer/lab-clips/originales/C0188.MP4` (Sony 1080p25), `IMG_0044.MOV` (iPhone 4K VFR). Master local de laboratorio listado pero esta prueba _render_segment no mezcla audio_.

## Diseño
Se llamó la función **real** `core.stages.export._render_segment` por separado en cada Engine. Se renderizó una ventana de 2 s empezando en t=10 s de cada original, 1920×1080, salida H.264 a 30 fps, bitrate objetivo 4 Mbps, sin branding ni añadidos, sin forzar proxy. Se usaron proyecto y carpetas privadas por ejecución; se comprobó MP4 con ffprobe, decodificación completa ffmpeg -xerror y SHA-256. Se invirtió el orden de ejecución en la segunda ronda Sony. No hubo cachés globales limpiadas; no es una prueba de caché fría de SO. No hubo ejecución concurrente de otros benchmarks conocida; se utilizó lock local propio, aunque **el lock compartido `/var/lock/montara/bench.lock` no estaba instalado**.

## Tiempos medidos (wall segundos)

| Caso | Engine anterior | Engine actual | Diferencia actual/anterior |
| --- | ---: | ---: | ---: |
| Sony 2 s, ronda 1 (anterior → actual) | 2.559 | 2.438 | −4.73% |
| Sony 2 s, ronda 2 (actual → anterior) | 2.476 | 2.461 | −0.61% |
| iPhone 2 s, ronda 1 (actual → anterior) | 3.008 | 2.988 | −0.66% |

Todos 60 frames / 2.000 s / H.264 1920×1080, decodificación correcta, fuente original. El tamaño en bytes y el SHA difieren. La comparación PSNR de los MP4 Sony de rondas distintas (anterior/actual) dio **58.52 dB**; la comparación de dos renders Sony de **la propia versión anterior** dio **58.87 dB**. iPhone anterior/actual **60.39 dB**. Hay variación de codificación incluso entre rondas del mismo Engine: **no inferir una regresión visual del cambio de código** sin una comparación con control y condiciones idénticas; el PSNR no equivale a juicio humano ni verificación de sincronía.

## Interpretación y límites
- **No se confirma mejora de rendimiento significativa** en esta pequeña exportación de planos sin funciones nuevas; el primer −4.7% se reduce a −0.6% al invertir el orden. Pocas muestras, variación de máquina/OS, sin intervalos de confianza ni métricas CPU/RAM por proceso.
- Los cambios entre Engine `841f4ed` y `98bce06` incluyen nuevas **funciones/correcciones**: velocidad de plano, 360 de alta resolución opcional, tolerancia de originales/insertos opcionales y validaciones. No deben evaluarse solo por tiempo de una exportación común.
- **No se ha ejecutado** Stage completo (ingest→sync→edit→export), selección automática correcta, sincronía, Companion, recuperación de proyecto, 360 con reproyección, ni concurrencia multiusuario. Los originales iPhone/Sony/360 no tienen sincronía acreditada con el máster de prueba: no inventar aceptación.
- Todos los outputs pequeños de este ensayo permanecen aislados bajo `/home/fgardel00/urano-ab-20261108/results` (~5.1 MiB en la última medición). No se han eliminado archivos históricos.
- Siguiente prioridad acordada: **cerrar mini-benchmark y regresar al E2E funcional U13E2C sobre una fuente realmente sincronizada**, comparando con el main actual y la PR #112. Si se ensaya 360, debe ser un caso separado con la misma receta y calidad en ambos Engines; no confundir “high” con un speedup.

## Nota reproducibilidad
Las pruebas se ejecutaron con Python/FFmpeg directamente en la VM; la función export._render_segment usó `create_project` y `file_record` del Engine de cada commit, con registro de cámara y duración/probe explícitos, `master_start_sec=10`, `clip_start_sec=10` y `duration_sec=2`. Resultados por ronda guardados en JSON en el directorio del ensayo, junto a MP4. Para repetir, preservar las carpetas, crear una nueva raíz de ejecución y no sobrescribir artefactos.
