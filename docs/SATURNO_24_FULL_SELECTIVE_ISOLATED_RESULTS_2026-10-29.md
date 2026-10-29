# SATURNO-24 — Integración completa Stage con vídeo GOP selectivo: resultado

Fecha: 2026-10-29. Rama `fernando/continuacion-montara`. Motor y mixer sin cambios. Script `experiments/saturno_24/full_selective_isolated.py`.

## Ejecuciones verificadas

- [40925286207](https://github.com/amehcgracia-byte/Montara/actions/runs/40925286207), job 123629019656: **failure operacional de QA preliminar**, `AssertionError: concat manifest must use newline escape`. La validación comprobaba una representación textual demasiado específica del script; no se ejecutó el montaje completo. No constituye fallo científico.
- [40925340228](https://github.com/amehcgracia-byte/Montara/actions/runs/40925340228), job 123629220030: **success**, `SATURNO24_SUMMARY.status=PASS_FULL_SELECTIVE_ISOLATED_AB`. Preflight `SATURNO24_CONCAT_PREFLIGHT_OK`.

## Evidencia de éxito

A, A_repeat, B: **3007 fotogramas cada uno**, 7 llamadas nativas 360 y 14 intervenciones QA de decodificación cada uno. Igualdad A/A y A/B: video_exact, audio_exact, timeline_exact, file_exact **true**; 3007/3007 fotogramas idénticos, cero diferencias. MP4 SHA-256 común:

`e53b268f5406a5df5b16c1b1ed43d56c849777224c4d2482b0ec4a517dc66a90`

Exportación A: **543.080539039 s**, A_repeat: **542.121059199 s**, B: **541.4727045300001 s**. Estas son duraciones **de procesamiento**, no duraciones del medio final. La salida de 3007 frames a 30fps dura nominalmente **100.233333 s** para cada variante. B tarda 1.607834509 s menos que A (~0.296%), no hay acortamiento del contenido. Igualdad de hashes de MP4 y cronología confirma identidad completa entre los tres archivos exportados en este entorno.

Entradas de cámara extendidas + master: **9549037 bytes**. Medios de paquete selectivo + master: **5744051 bytes**. Diferencia: **3804986 bytes** (39.85% de los bytes de medios del caso controlado). No incluye el coste adicional de plan/manifest, transporte, red, infraestructura y tiempo de preparación. No extrapolar a tráfico de usuarios ni a grabaciones reales.

## Alcance de la prueba

Se reutilizó el plan Stage con 19 segmentos y 7 llamadas 360, audio master del fixture y fuentes de vídeo **alargadas por concatenación de contenido repetido** mediante stream-copy. El paquete B elimina realmente GOP de partes no utilizadas, preservando dependencias conservadoras, las ventanas y muestras de color. El proceso B ocultó los originales, la fuente extendida y las carpetas A/A_repeat con namespace de montaje privado/tmpfs y se ejecutó con caché inicial vacía. Se mantuvieron `-fps_mode passthrough` QA en el decodificador y `-threads:v 1` QA en el encoder. No se tocaron engine, mixer ni main.

La prueba certifica la **integración selectiva completa y aislada en este caso controlado**, no implementación generalizada para GOP abiertos, metrajes reales variados o arquitectura de producción. No se han medido transferencias remotas ni coste/tiempo extremo a extremo; el hito D sigue pendiente.

## Próximo hito

Medir bytes efectivos transferidos, tiempo de empaquetado, subida y reconstrucción y coste comparable A/B en un trayecto remoto real y reproducible, o una prueba de red claramente etiquetada como simulada si todavía no hay servidor disponible. Separar coste fijo del render y ahorro en transferencia. Después validar múltiples códecs/estructuras de GOP con fuentes reales antes de Júpiter.
