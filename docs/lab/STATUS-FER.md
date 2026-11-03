# STATUS — laboratorio de Fernando
Actualizado: **2026-11-03** · Rama `fernando/continuacion-montara` · laboratorio / investigación; **no producción**.

## Bases verificadas (escafandra 2026-11-03)
- Montara `main=8c7b54f` (versión JM 0.60 instalada en `5a65f50`); fija `engine=affe97a4`, `mixer=f15ff91`. Nuestro laboratorio sigue con `engine=ff9baf4` para ensayos controlados.
- ZuckerVideos `main=321fdb4` (antiguo); **rama activa JM** `claude/recover-montara-engine=74c16f9`. La futura base funcional es la rama activa/pin de Montara, NO `zucker_videos/main`.
- Rama FER de Montara divergida de main: 327 ahead / 55 behind (merge-base `f91dbac`). Zucker FER `fernando/ex06-engine-lab=e7b070e`: 4 ahead / 10 behind de la rama activa JM. **No fusionar ramas completas ni mover pines sin revisión.**
- GitHub `docs/COLLABORATION.md`: entregas en PRs pequeñas sobre bases recientes, con pruebas, Chema integra producto; `STATUS-FER` antes estaba anticuado desde 30-10.

## Últimos hallazgos y aceptación
- EX-14G-02: Linux intentaba `h264_videotoolbox` fallido (~70.6 ms microbench). **Chema integró corrección selectiva** ZuckerVideos PR #52, ahora Linux elige libx264; Mac preservado.
- EX-14H-06: original HEVC 360 real 3840x1920 → 1080p30, 60 frames, 8.565s wall; mapa 3.874s/mediana 64.121ms, read 2.241s (espera+transferencia), remap 1.469s, write 0.584s. Solo pipeline independiente, NO Stage E2E.
- **EX-14H-08 PASS:** 60 poses × 3 rondas, mapas 1080p exactos entre variantes, 0 mismatches. Mediana base 28.917ms, EX07 19.956ms (−30.99%), EX13 26.212ms (−9.36%), ambas 16.487ms (**−42.99%**). Es solo geometría, no mejora de Stage; entorno limpio 0.1% CPU preflight.
- PR ZuckerVideos #51 **draft no integrada**: revisión Chema aceptó compatibilidad parcial (36 tests propios, 66 en integración temporal), opt-in desactivado. EX07/13 son candidatas prioritarias, EX06 variación visual requiere QA separada. Actions Fast: 22 fallos preexistentes comprobados contra base (1320 passed, 10 skipped, 16 deselected); Slow PASS.
- Montara 0.59/0.60: luz per-shot y native export desde originales, cancelación y progreso restablecidos, mezclas locales Companion; E2E Linux de JM reportado OK. No duplicar pruebas.
- Issues abiertas: Montara #58 sync global-consenso no corregido; #56 duration `-t` todavía falta; #54 disco subió a ~73% y retención automática pendiente; #53 FFmpeg global sigue 6.1.1. #34 canal de coordinación, #13 digests de main.

## Próximos objetivos
1. **Corto:** cerrar documentación de EX14H-08, control comparativo del motor actualizado y perfil de Stage representativo con EX07/13, misma fuente/máquina/pin, sin duplicar pruebas ya validadas.
2. **Corto:** revisar PR #51 contra rama activa y preparar integración selectiva en rama CORTA de ZuckerVideos desde la revisión actual; no activar defaults ni forzar merge. Mantener EX06 separado.
3. **Medio:** estudiar tiempo E2E real de 360, eficiencia CPU, buffers e infraestructura sin sacrificar imagen, audio, sincronía, reproducibilidad ni cancelación; investigar arquitectura local/híbrida y futuro Companion Windows tras priorización JM.
4. **Coordinación:** palabra clave «surcar con la escafandra espacial» = revisar main Montara, rama activa/pin motor, ambos repos, submódulos, issues/comentarios/PR/CI; comparar cambios y detener experimentos obsoletos. Revisar antes de incorporar actualizaciones, no hacer merge amplio sin tests.

Informes detallados: `docs/lab/JUPITER_EX14H_360_PIPELINE_SCIENTIFIC_REVIEW_2026-11-03.md` y `docs/lab/JUPITER_EX14F_PARALLELISM_RESEARCH_2026-11-03.md`. No afirmar validación productiva sin E2E.
