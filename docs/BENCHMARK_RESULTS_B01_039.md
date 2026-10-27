# Primera ejecución de benchmark de vídeo — 2026-10-27

## Prueba B01, CPU, sin RunPod

Se ejecutó una copia funcional del script de `experiments/media_optimization/benchmark.py` en el entorno de análisis de ChatGPT (FFmpeg nativo, x264, Python 3.13.5). El repositorio está actualizado con el script y con pruebas de las métricas. Los tests sobre las métricas **sí pasaron localmente** (3/3); el código en GitHub **todavía no se ha ejecutado en GitHub Actions**.

Se generó un vídeo artificial de 8 segundos (640×360, 24 fps, cuatro colores sólidos y tres cortes conocidos). Un proxy de 480×270 permitió una pequeña reducción, pero la sencillez del material hace que **no sea un benchmark válido de compresión real**.

| Métrica | Resultado observado |
| --- | ---: |
| Cortes esperados | 3 |
| Cortes detectados sin muestreo | 3 |
| Cortes detectados a 2 fps | 3 |
| Precisión y recall en esta prueba sintética | 1,00 ambos |
| Tiempo de análisis completo | 0,1237 s |
| Tiempo del análisis a 2 fps | 0,1231 s |
| Tamaño original | 8.344 bytes |
| Tamaño proxy | 7.219 bytes |
| Generación del proxy | 0,3205 s |

**Interpretación:** reducir fotogramas después de decodificar, mediante `fps=2`, no evitó el coste de decodificación y no mejoró apreciablemente el tiempo. Las escenas de colores sólidos son un caso irrealmente sencillo; ni la calidad ni la compresión se extrapolan a conciertos. La hipótesis siguiente a evaluar es cambiar el patrón de acceso al vídeo (keyframes, seeking por intervalos, caché de índices, proxies persistentes) para reducir realmente la decodificación.

## Reproducción

```bash
python experiments/media_optimization/benchmark.py --output /tmp/montara-b01.json
python -m pytest tests/test_media_benchmark_metrics.py -q
```

No se ha tocado el motor de Zucker, `main`, los despliegues ni los créditos RunPod.
