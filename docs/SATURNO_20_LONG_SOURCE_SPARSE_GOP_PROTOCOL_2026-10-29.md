# SATURNO-20 — preflight de selección parcial real de GOP

Fecha: 2026-10-29. Rama: `fernando/continuacion-montara`. Estado: **experimento preparado y workflow publicado; resultado pendiente de ejecución/verificación**.

## Hipótesis delimitada

SATURNO-19 confirmó que las tres cámaras de la fixture Stage utilizan todos sus GOP. Para demostrar *ahorro selectivo real de vídeo*, este ensayo construye un clip sintético reproducible de 90 segundos, 640×320 a 30 fps, codificado H.264 con GOP cerrados cada 60 frames (2 s), sin fotogramas B, y dos ventanas de montaje en los segundos [20,26) y [50,56).

Se aplica el mismo selector `choose_gops` y el mismo remux selectivo `copy_sparse` de `experiments/saturno_10/packet_preflight.py`. Se conservan los GOP primero y último para metadatos de extremo, como en el ensayo histórico. Se miden **bytes reales** del contenedor y de payload de paquetes originales/retenidos, número y selección de GOP, SHA-256 de paquetes y PTS/DTS, y decodificación de las ventanas BGR usando `-fps_mode passthrough`.

**Criterio de éxito:** se eliminan múltiples GOP y disminuye el tamaño real del contenedor, los paquetes retenidos mantienen hash/PTS/DTS, y las dos ventanas decodificadas A/B son idénticas. En caso contrario registrar fallo separado de éxito operacional de Actions.

## Reproducibilidad

- Script `experiments/saturno_20/long_sparse_gop.py`
- Workflow `.github/workflows/saturno20-sparse-gop.yml` (disparo por cambio de YAML, rama única, lectura solamente, Ubuntu 24.04, FFmpeg, no servicios de pago).
- Informe compacto `SATURNO20_SUMMARY=` en logs y `REPORT.json` temporal. El mecanismo de persistencia autónoma en la rama sigue pendiente de integración.

## Límites

La fuente sintética no contiene audio, ni metadatos de color ni re-proyección real de Zucker, ni plan Stage multimodal. Tampoco demuestra transporte remoto, costes o compresión sobre grabaciones reales. Una victoria establecería la factibilidad de descartar payload de vídeo selectivamente preservando las ventanas decodificadas en este caso controlado; **no** certificaría todavía los hitos B y D en producción.

El motor principal, `main` y `mixer` no se alteran. No se repite el render completo de SATURNO-18.
