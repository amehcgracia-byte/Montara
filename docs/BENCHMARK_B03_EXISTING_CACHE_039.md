# B03 — Existing local proxy cache: verification and cost model

## Confirmed from Montara 0.39 code

`local_media/proxies.py` is present in the latest branch. Its `prepare()`:
- Uses an opaque source ID derived from the absolute local path, file size, nanosecond mtime, sphere flag and proxy version.
- Probes the original via ffprobe **before** checking its cache. A warm cache call still incurs a probe, although it does not re-encode the proxy when the cache record and MP4 exist.
- Converts originals to H.264 proxies (nominal width capped at 960 pixels except 360 format), veryfast preset, CRF 28; keeps the selected audio stream at 96 kbps AAC.
- Verifies approximate duration and stores a private original-to-proxy mapping, while publishing metadata without absolute paths.
- Validates the original stamp again when resolving a recipe for final export.

`tests/test_local_proxies.py` already checks proxy duration, privacy of public metadata, warm reuse of the same `source_id` and rejection when the original changes. This existing test was discovered **after** the B03 benchmark was added; do not duplicate it.

## New experiment

```bash
python experiments/media_optimization/benchmark_b03_proxy_cache.py
```

Creates a synthetic 12-second 1280×720 H.264 input and measures:
1. `prepare()` on a cold cache, including ffprobe + transcoding + verification.
2. `prepare()` again on a warm cache, including the repeated original ffprobe.
3. Proxy/original byte ratio and verification that warm reuse did not modify the cached proxy.

**Status:** experiment committed, actual B03 measurements not yet recorded or CI-certified.

## What this means for Montara

The product already implements **file-level proxy caching**. Optimisation efforts should focus on when proxies are prepared, their generation latency on large files, retained disk space, cache invalidation and integration into the web preview/editor. Do not claim a 97% universal reduction or that frame analysis is already using these local proxies.

Potential inexpensive follow-up: check trusted `stat()`-based cache metadata before the expensive `ffprobe` step, but first confirm rotation, timestamps and source identity requirements. Stat-only identity is not cryptographic integrity and can miss content changes preserving size/mtime.

## Break-even thought experiment

Let `G` be one-time proxy-generation time, `O` time per repeat original read and `P` per repeat proxy read. For `N` repeated operations, a proxy wins on total elapsed processing time when:

```
G + N*P < N*O
N > G/(O-P)
```

This is not a quality or storage result. It only applies to operations that can be performed on proxies, and excludes the requirement to use original frames for final export.


## Primera ejecución real — 27 octubre 2026

Prueba con el algoritmo `local_media.proxies.prepare` de Montara 0.39 reproducido sin modificar en Linux, Python 3.13 y FFmpeg instalado. Vídeo sintético `testsrc2`, 12 segundos, 1280×720, 30 fps, H.264, x264 ultrafast CRF 24. Se ejecutó una sola medición por modalidad.

| Indicador | Medición |
| --- | ---: |
| Original | 10.565.743 bytes |
| Proxy | 704.320 bytes |
| Proporción proxy/original | 6,67 % |
| Preparación inicial (caché fría) | 1,4655 s |
| Preparación con caché caliente | 0,0760 s |
| Cociente fría/caliente | ≈19,3× |
| Coincidencia de ID en reapertura | Sí |

**Interpretación correcta:** esta prueba valida la reutilización sin transcodificar y cuantifica el coste evitado de `prepare()`. No mide la velocidad de previsualización completa ni demuestra que un concierto de 800 GB pueda editarse 19 veces más rápido. Falta repetir sobre fuentes largas y variadas, recopilar varias ejecuciones y medir precisión temporal.

**Próxima hipótesis:** comprobar si `ffprobe` antes de mirar el manifiesto de caché es un coste evitable y si la edición web utiliza realmente ese proxy. Cualquier cambio de identidad debe preservar la invalidación al modificarse el original, la información temporal y la seguridad de rutas.
