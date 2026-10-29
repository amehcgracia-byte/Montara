# SATURNO-20 — Resultado medido del empaquetado selectivo de GOP

Fecha: 2026-10-29. Fuente primaria: [run 40920415722](https://github.com/amehcgracia-byte/Montara/actions/runs/40920415722), job 123611799653 (`success`). Script: `experiments/saturno_20/long_sparse_gop.py`. Estado experimental: `SPARSE_GOP_WINDOWS_EXACT`.

## Cifras reales de la prueba

| Métrica | Original A | Paquete selectivo B |
|---|---:|---:|
| Tamaño contenedor MP4, bytes | 19756759 | 4383338 |
| Payload de paquetes de vídeo, bytes | 19744655 | 4379938 |
| Paquetes de vídeo | 2700 | 600 |
| GOP conservados | 45 | 10 |

Se descartaron **35 de 45 GOP**, **2100 paquetes** y **15373421 bytes del contenedor**; ahorro de contenedor del **77.81 %**, calculado sobre el archivo A. Ahorro de payload de vídeo: **15364717 bytes**.

En el remux selectivo de los paquetes conservados, hash de payload y PTS/DTS coincidieron con sus correspondientes originales. Las ventanas 20–26 s y 50–56 s se decodificaron a BGR con control `-fps_mode passthrough`. Sus SHA-256 A/B fueron idénticos:
- 20–26 s: `d6335976a2bc07ce9bc8b00b3ae726ba3191ce1d83605f30962c21f253774733`.
- 50–56 s: `5e4d83133d8520be997b453e385daf664b345cd9eed69d6c0dcc38294200913a`.
Cada ventana produjo 110592000 bytes BGR por variante.

## Interpretación

En fuente sintética de 90 s, H.264 con GOP cerrados de 2 s, sin B-frames, se consigue reducción física real del contenedor conservando íntegros los dos intervalos utilizados por el montaje. Supera el gate de preflight selectivo de GOP **solo para esta fuente**.

**No demuestra** por sí solo un montaje final Zucker A/B, reproyección 360, conservación de audio, interacción con las muestras de color o la selección óptima de un caso real con GOP abiertos/B-frames. No hay transferencia remota o coste medido, ni afirmación de que un hash regenere información ausente. El paquete no es una reconstrucción del original completo: preserva el contenido necesario para dos ventanas seleccionadas.

## Próximo gate

Construir un montaje real de Zucker con esta fuente larga y selección de dos ventanas, verificar color/seek/segmentos y generar exportación A y B con cachés aisladas. Si se pretende mantener cobertura 360 del experimento, introducir reproyección nativa y comparar fotogramas finales, audio y PTS; no usar la igualdad de ventanas como sustituto de render final. Diseñar primero la prueba de alcance mínimo para ahorrar CI.
