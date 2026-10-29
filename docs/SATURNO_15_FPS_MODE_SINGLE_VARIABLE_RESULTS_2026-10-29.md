# SATURNO-15 — control de una sola variable: fps_mode passthrough

Fecha: 2026-10-29. Rama: `fernando/continuacion-montara`.

## Pregunta

¿Añadir **únicamente** `-fps_mode passthrough` al comando exacto de decodificación CPU del segmento 360 0003 elimina la divergencia de fotogramas A/B detectada en SATURNO-14?

## Procedencia y alcance

- Workflow: https://github.com/amehcgracia-byte/Montara/actions/runs/40907875229
- Job: 123567504733. Resultado operacional: `success`.
- Script: `experiments/saturno_15/decoder_fps_mode.py`.
- Código de la prueba: commit `b401afe9879446afb503709fec99d97b72074241`.
- Engine fijado: `60a7b7e9a39077b36f45057811abd6a833a168ef` (sin modificar).
- FFmpeg: `6.1.1-3ubuntu5`.
- Ventana real del segmento 0003: inicio `21.76784580498866` s; 278 fotogramas; 640×320 BGR24; 30 fps.
- Receta y hashes de original/paquete verificados frente a la evidencia anterior; se mantienen todos los GOP. No hubo reproyección 360, codificación de segmentos ni export completo.
- Los dos comandos son iguales salvo la inserción de `-fps_mode passthrough` entre `-frames:v 278` y `-f rawvideo pipe:1`. El script ejecuta cinco decodificaciones (A y B original, A y repetición A con passthrough, B con passthrough).

## Resultado recuperado de SATURNO15_SUMMARY

| Comparación | Fotogramas iguales | Primera diferencia |
| --- | ---: | ---: |
| A_exact / B_exact | 47/278 | índice 1 |
| A_passthrough / A_repeat_passthrough | 278/278 | ninguna |
| A_passthrough / B_passthrough | **278/278** | ninguna |
| A_exact / A_passthrough | 47/278 | índice 1 |
| B_exact / B_passthrough | 278/278 | ninguna |

`status=PASSTHROUGH_AB_EXACT`; `previous_exact_reproduced=true`; `all_requested_counts=true`; `error=null`.

## Conclusión y límites

**Resultado positivo para esta ventana**: añadir solamente `-fps_mode passthrough` al decodificador CPU elimina aquí las diferencias A/B por hashes BGR; la repetición de A con la opción también es idéntica. El resultado anterior sin esa opción queda reproducido.

Esto aísla un factor causal **en esta comparación de comandos**; no determina todavía qué mecanismo de FFmpeg (duplicación, descarte, PTS o política de sincronización) explica el efecto, ni certifica los otros seis segmentos, la reproyección, el MP4 final o la sincronización completa. No es autorización para alterar el motor.

## Próximo bloque propuesto (no ejecutado)

Comprobar el mismo control en **los seis segmentos 360 divergentes de SATURNO-12**, únicamente decodificando sus ventanas. Comparar A/B, A/A de control y número de cuadros, con el plan y las mismas fuentes verificadas. No ejecutar los tres exports completos todavía. Cerrar con evidencia antes de decidir si procede un control QA integrado en un nuevo A/B completo.

## Uso de herramientas

Consulta del job y un acceso a sus logs mediante conector GitHub; el log completo tenía 165657 caracteres, pero únicamente se emitieron fragmentos y el resumen. Una lectura de HEAD antes de documentar. Los tokens exactos de la sesión no están disponibles. Sin navegador, RunPod, Oracle ni renders completos. Se documenta en commit separado para no iniciar otro experimento por accidente.
