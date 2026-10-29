# SATURNO-25 — resultado certificado: preparación, ZIP, transferencia HTTP local y escenarios

Fecha 2026-10-29. Ejecución GitHub Actions [40936888087](https://github.com/amehcgracia-byte/Montara/actions/runs/40936888087), job 123669674447: **success**. Rama `fernando/continuacion-montara`. Script `experiments/saturno_25/transfer_economics.py`; workflow `.github/workflows/saturno25-transfer.yml`. No se repite exportación/render Stage.

Estado de programa: `CONTROLLED_PREPARE_TRANSFER_ECONOMICS_MEASURED`.

## Métricas de medios (mismas categorías A/B)

Tiempo total de preparación en el caso de laboratorio: **2.60121013 segundos**. **Este tiempo incluye generar los vídeos extendidos artificiales, no solo seleccionar GOP en una fuente original.**

| Cámara | Original extendido (bytes) | Selectivo (bytes) | GOP originales | GOP conservados |
|---|---:|---:|---:|---:|
| cam-sony.mp4 | 4785373 | 2700516 | 30 | 17 |
| cam-fixed.mp4 | 1798879 | 916864 | 30 | 16 |
| cam-360.mp4 | 1363349 | 525235 | 30 | 12 |

Medios de entrada con master: **9549037 bytes** (A) frente a **5744051 bytes** (B); ahorro **3804986 bytes**, o **39.8468034%**.

## Archivos ZIP y transporte

ZIP original de medios: **9260068 bytes**, construcción **0.220936951 s**. SHA256 `103e0be851ac40a1fb11c4510b1818e0482772282c62a8b7497250e1c0fa11c7`.

ZIP selectivo: **5682115 bytes**, construcción **0.142354518 s**. SHA256 `025169a1428dcf624fe7233b2b2270ab6f8cae0794639f95b4adb8437ae6dc3b`.

El ZIP selectivo incluye **project.json y plan.json**; el ZIP original agrupa los medios originales y master, por lo que la comparación incluye metadatos solo de B. Ahorro del archivo: **3577953 bytes**, aprox. **38.6385%**.

Transferencia HTTP al servidor receptor **127.0.0.1 del mismo runner**, tres repeticiones, hashes recibidos verificados:

- Original: **0.008562197 / 0.008231668 / 0.008111917 s**; mediana **0.008231668 s**.
- Paquete: **0.005104013 / 0.005477547 / 0.005054988 s**; mediana **0.005104013 s**.

Estos tiempos **NO representan transferencia WAN real ni ancho de banda usuario-servidor**. Una sola medición de preparación por variante; tres transferencias locales no establecen significancia estadística ni escalabilidad.

## Escenarios monetarios (NO tarifas contratadas)

Tarifas hipotéticas de salida `0.02, 0.05, 0.10 EUR/GB` decimal para 10000 envíos: **0.715591 / 1.788977 / 3.577953 EUR** de ahorro respectivamente.

Son cálculos aritméticos de bytes * tarifa únicamente. No incluyen CPU, tráfico de entrada, almacenamiento, distribución, costes de render, operación ni concurrencia.

## Conclusión y límite

El hito experimental D está **medido y aprobado exclusivamente en transporte local/controlado**, con un paquete selectivo genuinamente menor y hashes de recepción exactos. Unido a SATURNO-24, hay prueba separada de que el mismo planteamiento de selección permite render Stage completo exacto con aislamiento de originales. **No hay transferencia real entre servidores**, ni demostración de ahorro porcentual universal en metraje real, ni matriz de múltiples códecs/GOP abiertos. SATURNO puede considerarse cerrado como **fase de factibilidad de laboratorio**, no como sistema de producción certificado.

Recomendación: transición conceptual a Júpiter para arquitectura de despliegue, validación WAN, pruebas de distintas grabaciones/códecs y presupuestos operativos con costes reales. No modificar motor, mixer o main sin revisión del propietario.
