# FOCUS A/C — correspondencia temporal real: 9/9 muestras (2026-10-30)

## Resultado del operador
`experiments/media_optimization/focus_ac_temporal_frame_gate.py` ejecutado bajo `montara-bench FER-FOCUS-AC-TIMING-01` con report local `/home/fer/montara-focus-ac-timing-01.json`. Estado `PASS_SAMPLED_TIMING`, preflight CPU 0.1%, git limpio.

Para cada original se comparó el frame en `t_original=10+t_proxy` contra el proxy de 4 segundos, para `t_proxy=0.5,2.0,3.5`. Medida: media del error absoluto de los canales RGB / 255 después de escalado. No es SSIM.

| Cámara | Error en 0.5 s | 2.0 s | 3.5 s | Máx |
| --- | ---: | ---: | ---: | ---: |
| iPhone | 0.010201 | 0.010976 | 0.010431 | 0.010976 |
| Sony | 0.015363 | 0.015404 | 0.016340 | 0.016340 |
| 360 HEVC | 0.011563 | 0.011220 | 0.010847 | 0.011563 |

**Interpretación:** coincidencia aproximada en las nueve muestras; no se aprecia un error grueso de offset u orientación en ellas. Límite de aceptación del script 0.20: **muy permisivo** (puede dejar pasar desajustes menores), por lo que el PASS no prueba identidad exacta, precisión frame-a-frame, totalidad temporal, calidad visual de un render ni audio. No confundir error visual bajo con verificación VFR en todo el iPhone.

## Próximo gate decisivo
Obtener un plan **creado realmente desde proxies** con la etapa edit de Zucker, conservar rutas/timeline originales y realizar un render corto desde originales; comparar audio, cuadros y decisiones. El actual handoff proviene de segmentos de laboratorio construidos a mano: `true_proxy_authored_edit_plan=false`, `render_from_originals=false`. No ejecutar Stage 15 min por inercia. Coordinar CPU y mantener `montara-bench`.
