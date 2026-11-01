# JÚPITER F4 — Cuatro interpolaciones 360 sobre escenario real (2026-11-01)

**Estado:** benchmark aislado completado, pendiente A/B calidad y confirmación de engine E2E. No integrado en Montara.

Fuente original: `VID_20260824_204524_00_004.mp4` (HEVC 360), t=840 s, 5 s, v360 yaw=180 pitch=-30, h_fov=100 v_fov=62, salida 1920×1080 H.264 CRF23 veryfast 2 threads, sin audio. Experimento manual `montara-bench FER-F4-FOUR-METHODS-01`. Salidas VM `/home/fer/montara-f4-cuatro-metodos-01/`. Orden L, linear, cubic, spline16, spline16, cubic, linear, L.

| Método | run 0 (s) | run 1 (s) | media (s) |
|---|---:|---:|---:|
| lanczos | 16.17 | 13.63 | 14.90 |
| linear | 9.10 | 9.24 | 9.17 |
| cubic | 13.72 | 16.28 | 15.00 |
| spline16 | 13.00 | 14.60 | 13.80 |

Ahorro bilineal vs Lanczos: **38.46 %** por medias. En comparación anterior, sobre encuadre oscuro yaw35 pitch12 en t=10 s, bilineal ahorró 15.72 % en dos ejecuciones (ambas pruebas con diferente contenido, posición y posible estado de VM).

Observaciones: bilineal gana en ambas ejecuciones. Spline16 es intermedio; bicúbica no gana a Lanczos en promedio. **Solo 2 repeticiones** por método; posible carga de laboratorio compartido, cachés, estado térmico y fluctuación de máquina. Estas cifras cubren decodificación, reproyección, codificación y escritura, no export completo del engine. **No se ha medido la calidad ni se han visto fotogramas de estos nuevos ocho MP4**, ni comparado cortes con cámara móvil o salida de compositor. No sustituir Lanczos por defecto.

Siguiente paso: inspección de fotogramas exactamente emparejados de los 4 MP4; comparar SSIM/PSNR por método contra Lanczos bajo alineamiento temporal controlado, y revisar cortes, pelo, instrumentos, cables, texturas y luces. Probar varios offsets y composición con movimiento antes de PR. 
