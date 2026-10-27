# B04 — Reapertura de proxies sin ffprobe

## Hipótesis

Montara ya conserva proxies y manifiestos privados por fuente, pero `local_media.proxies.prepare()` ejecutaba un `ffprobe` antes de comprobar la existencia de una caché válida. En reaperturas frecuentes, podemos evitar ese proceso si el original conserva su sello (bytes + mtime_ns), el manifiesto corresponde a la fuente solicitada y existe un proxy no vacío.

## Medición inicial (2026-10-27)

Experimento local con el código de Montara 0.39, FFmpeg del entorno Linux, vídeo H.264 sintético de 3 segundos a 640×360 y 24 fps. Se generó una vez el proxy y se midió la mediana de 8 reaperturas por modalidad.

| Operación | Mediana medida |
| --- | ---: |
| `prepare()` original, caché existente y ffprobe | 68,519 ms |
| `prepare()` optimizado, caché existente sin ffprobe | 0,083 ms |

La diferencia es la sobrecarga de la preparación **con caché caliente**, no la reproducción del vídeo ni la generación de proxies 4K. Prueba sintética y corta, realizada fuera de GitHub CI; repetir en distintos sistemas y con los fixtures reales.

## Cuatro comprobaciones del flujo rápido

1. Caché válida → devuelve el mismo registro sin llamar a ffprobe.
2. Archivo original modificado (mtime) → no reutiliza el registro anterior.
3. Proxy vacío o ausente → no reutiliza el registro.
4. Manifiesto corrupto o que indica otra fuente → no reutiliza el registro.

Las cuatro comprobaciones se ejecutaron correctamente contra un prototipo equivalente y también se añadieron regresiones al repositorio (`tests/test_proxy_cache_fastpath.py`). **El estado de CI del código exacto en GitHub sigue sin verificarse.**

## Implementación

Se cambió solamente `local_media/proxies.py`, manteniendo el mismo formato `proxy019`, el algoritmo para generar el `source_id`, la lógica de transcodificación, los metadatos públicos y `resolve_recipe()`.

El nuevo acceso rápido comprueba el sello del archivo, ruta de origen y proxy, ID de caché, proyección y presencia de un MP4 no vacío. Solo si falla vuelve al análisis original con ffprobe.

## Riesgos y próximos pasos

- El sello `size+mtime` no es una prueba criptográfica de integridad (igual que en la implementación anterior); archivos modificados preservando ambos atributos pueden reutilizar una caché antigua. Requiere evaluar huellas de contenido incrementales sin leer 800 GB.
- La existencia y tamaño del MP4 no certifican la decodificación correcta; una corrupción posterior con tamaño positivo requiere validación adicional o política de verificación periódica.
- En proyectos con múltiples procesos generando el mismo proxy simultáneamente se necesitará bloqueo por fuente y escritura atómica del manifiesto. La prueba actual cubre reutilización secuencial.
- Este optimizador no sustituye la integración real de proxies en el editor web.
- Próxima tanda: medir códec, GOP, VFR, sincronización con audio y costes reales de creación/reutilización en ficheros largos.

## Reproducir

```bash
python -m pytest tests/test_proxy_cache_fastpath.py tests/test_local_proxies.py -q
python experiments/media_optimization/benchmark_b03_proxy_cache.py
```
