# JÚPITER · EX-06 — implementación opt-in y render A/B (2026-11-02)

**Estado:** implementación experimental en la rama Fernando. Sin cambios en los submódulos ni en main; no PR lista para producción.

## Código
- `experiments/media_optimization/jupiter_cpu_linear_optin.py` (commit `1db43b8`): adaptador reversible y acotado a `core.spherical_motion.cv2.remap` que cambia `INTER_CUBIC` por `INTER_LINEAR`. Solo para procesos de laboratorio aislados; no thread-safe y no apto para instalación global.
- `experiments/media_optimization/jupiter_ex06_render_ab.py` (commit `b8271f6`): render A/B usando `run_reprojected_command` real, 30 frames, 960×540, fixture `cam-360.mp4` (640×320), libx264 ultrafast CRF 18. Sin E2E ni original 4K.
- Autoprueba `PYTHONPATH=engine .venv/bin/python experiments/media_optimization/jupiter_cpu_linear_optin.py`: `EX06_OPTIN_SELFTEST_OK`. Verifica sustitución y restauración tras salida normal y excepción.

## A/B real del motor (informado por Fernando)
Motor `ff9baf4`. Los dos vídeos tienen 30 frames; el adaptador intervino 30 veces en bilineal; 0 hashes de frames codificados idénticos entre métodos (esperable). Árbol Git limpio.

| Orden | Bicúbica s | Bilineal s | Ahorro calculado |
|---|---:|---:|---:|
| Bicúbica → bilineal | 1.590 | 0.694 | 56.4 % |
| Bilineal → bicúbica | 0.891 | 0.772 | 13.4 % |

**Interpretación:** ambos órdenes favorecen bilineal, pero la diferencia entre ensayos muestra influencia de calentamiento/entorno. Solo dos observaciones y resolución 540p; NO extrapolar la ganancia al render de producción.

**Calidad:** medición `ffmpeg psnr` sobre MP4 codificados; para los fotogramas 23–30 se observaron valores `psnr_avg` ~43.51–43.71 dB. No es promedio de los 30 frames ni revisión perceptual. No hay revisión visual a resolución nativa.

## Relación con EX-06 anterior
Microbenchmark sobre original HEVC 3840×1920 y reproyección a 1920×1080: mapas+bicúbico 95.31 ms/frame; mapas+bilineal 78.55 ms/frame (−17.59 % del subproceso). PSNR 47.597 dB relativo a bicúbico y MAE 0.430/255. Excluye decodificación, codificación, mux, concurrencia y ruta Metal.

## Decisión e integración
- JÚPITER **sí ha implementado** una variante funcional y reversible, sin editar `engine/`.
- **Cerrar benchmarks repetitivos** de esta fase. No declarar una aceleración E2E.
- Para producto, Chema debe valorar un cambio explícito y thread-safe en `zucker_videos`, no integrar el adaptador por monkeypatch, y aprobarlo solo tras revisión visual full-res y E2E mismo proyecto/maquina.
- Seguir el contrato `docs/COLLABORATION.md`: Chema decide; PR corta desde main del repo correspondiente; documentar pruebas y SHA de engine/mixer.

## Infraestructura
Tras reinicio de VM faltaba `/var/lock/montara`; se creó con permisos 1777 de forma provisional. Restaurar configuración permanente con administración autorizada, sin retirar el control `flock`.
