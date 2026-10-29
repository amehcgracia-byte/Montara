# SATURNO-22 — resultado de eliminación adicional de GOP

2026-10-29. GitHub Actions [40922499640](https://github.com/amehcgracia-byte/Montara/actions/runs/40922499640), job 123619201877, éxito operacional. Script `experiments/saturno_22/gop_deletion_audit.py`.

**Resultado:** `GREEDY_GOP_EXACT`. Fuente sintética H.264 90 segundos, 45 GOP, sin audio; ventana [20,26) y [50,56), hash BGR A/B exacto en ambas.

| Variante | GOP retenidos | MP4 bytes | Ventanas A/B |
|---|---:|---:|---|
| Fuente original | 45 | 19756759 | Referencia |
| SATURNO-20 selección inicial | 10 | 4383338 | Ambas exactas |
| SATURNO-22 selección greedy | 8 | 3503672 | Ambas exactas |

Se eliminan **879666 bytes adicionales** sobre la selección previa. Frente al original, ahorro de **16253087 bytes**, aproximadamente **82.27 %**. GOP 13 y 28 fueron excluidos con las dos ventanas exactas. Intentos individuales de suprimir GOP 10,11,12,25,26,27 fallaron la comparación de su ventana correspondiente. El script mantiene por restricción GOP inicial y final.

**Limitación:** resultado de eliminación greedy probado con hashes; no certifica mínimo global ni todas las posibles combinaciones, no demuestra que las ventanas puedan exportarse como montaje Stage completo con audio, color y aislamiento del original. El render 360 nativo exacto de SATURNO-21 se realizó con **10**, no 8 GOP. La evaluación de los 8 GOP en reproyección Zucker permanece pendiente.

Registros de prueba: `SATURNO22_VARIANT`, `SATURNO22_SUMMARY`, `SATURNO22_PRESERVED`. No se ha cambiado engine/main/mixer ni ejecutado nube de pago.

**Próximo gate:** comprobar reproyección real de Zucker con el subconjunto optimizado de 8 GOP (A/A/B), y después integrar en exportación Stage con audio, color y aislamiento físico; no confundir ambos niveles.
