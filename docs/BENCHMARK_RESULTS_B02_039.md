# B02 — Coste real de localizar fotogramas y reutilizar proxies

## Medición exploratoria 2026-10-27

Se ejecutó una versión equivalente del experimento en un entorno Linux con FFmpeg 7.1.5, CPU y vídeo sintético `testsrc2` de 36 s, 640×360, 30 fps, H.264 con GOP 120. **Medición preliminar de una ejecución; no hay todavía repetición estadística ni CI confirmado para el commit remoto.**

| Método | Tiempo observado |
| --- | ---: |
| Recorrido del original con `fps=0.2` | **0,3436 s** |
| Siete búsquedas individuales con `-ss` y un nuevo proceso FFmpeg por muestra | **0,7143 s** |
| Crear proxy 320×180, 2 fps | **0,4483 s** |
| Recorrer el proxy ya creado con `fps=0.2` | **0,0781 s** |
| Crear proxy y analizarlo por primera vez | **0,5264 s** |

Original: 3.352.642 bytes. Proxy: 138.439 bytes (4,13 % del original). **No extrapolar la reducción al vídeo 4K de una jam:** la compresión, el muestreo y el contenido de la fuente no son equivalentes, y todavía no se ha evaluado la calidad visual ni la fidelidad de los instantes elegidos.

### Hallazgos

1. Siete `-ss` separados resultaron más lentos que un recorrido del original: abrir múltiples procesos FFmpeg introduce una sobrecarga apreciable.
2. Analizar el proxy una vez creado fue ≈4,4 veces más rápido que el recorrido del original en este escenario. Su **generación inicial no se amortizó en una sola lectura**.
3. El punto de equilibrio de reutilización depende de cuántas consultas se hacen, cuánto cuesta la creación y del tamaño/calidad/GOP del original. Evitar recodificación repetida, y usar una caché verificable con identidad del archivo, tiene sentido.
4. La prueba de análisis sobre el original usa `fps=0.2` y las búsquedas individuales usan tiempos 2,7,…32 s: **no se ha comparado aún la precisión para una misma lista de marcas temporales**. B03 deberá igualar esos tiempos y contrastar los fotogramas realmente obtenidos.
5. El benchmark aún no incluye VFR, transiciones difíciles, multistream, varios discos, rango 4K, montaje final ni calidad perceptual. El resultado es un baseline técnico, no una promesa de rendimiento.

### Reproducir

```bash
python experiments/media_optimization/benchmark_b02.py
python -m pytest tests/test_benchmark_b02.py -q
```

## Registros históricos de José Manuel

Sería útil consultar sus logs y métricas previas, **pero no recomendamos subir registros completos de cientos de ejecuciones al repositorio**. Mejor:

- Un pequeño índice Markdown/CSV: fecha, commit, máquina, sistema operativo, versión FFmpeg, vídeo usado (sin datos privados), duración, resolución, codec, tamaño, tarea, tiempo, RAM, resultado y errores.
- Un conjunto de 5–10 ejecuciones representativas, limpiando rutas locales, claves, tokens, cookies, enlaces de acceso, datos de personas e identificadores privados.
- Mantener logs brutos y vídeo real fuera de Git (almacenamiento personal o artefactos caducos). `git-lfs` y GitHub no deben convertirse en almacén permanente de cientos de GB.
- Separar `tests passed` de benchmarks de rendimiento y de opiniones subjetivas de calidad de mezcla.
- Idealmente comparar la misma base de vídeo/audio y FFmpeg con la misma máquina antes/después del cambio.

El objetivo no es duplicar su trabajo sino aprovecharlo como baseline existente, detectar regresiones y concentrar pruebas en las optimizaciones realmente prometedoras.
