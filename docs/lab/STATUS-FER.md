# STATUS — laboratorio de Fernando
Actualizado: **2026-11-04** · Rama `fernando/continuacion-montara` · laboratorio / investigación; **no producción**.


## Companion Windows W1–W3E + Linux W2 · 04-11
- [PR #74](https://github.com/amehcgracia-byte/Montara/pull/74) **draft sin merge**. W1: 4 tests focalizados PASS y CI Linux reparado `fe3e70e` **success**; Windows W3B abrió selector gráfico, cancelación observada; aceptación y USB aún pendientes.
- **W2 Linux PASS focalizado:** Companion 0.6.2 main `4f96af9`, API `/health`, `/locate`, `/proxies` + descarga H.264 BT.709, `/projects` y `/save` bytes idénticos. [Informe W2](JUPITER_COMPANION_W2_LINUX_HTTP_PROXY_PASS_2026-11-04.md).
- **W3C Windows parcial:** `/health` y `/locate` HTTP 200, pero `/proxies` timeout 100 s; **W3D** confirma comando FFmpeg directo exit 0 y `make_proxy` bloqueado 20 s por lectura secuencial de stdout/stderr. Fix `7964645` y test regresión `d92c5e8`. **W3E Windows PASS**: test saturación 0,707 s; `make_proxy` real `ready` en 0,31 s, proxy 169.608 bytes (36 % de original sintético), limpieza OK. [Informe W3](JUPITER_COMPANION_WINDOWS_W3B_W3E_2026-11-04.md).
- **W3F–W3H Windows PASS (04-11):** tras fix pipe, API HTTP completa 200/202/ready/descarga. W3F detectó falta de transfer/primaries BT.709; W3G confirmó que FFmpeg `setparams` las añade; patch `6858afa` y tests `cca1bce` en PR draft. W3H nativo desde `cca1bce`: proxy HTTP **159.816 bytes**, 0,2 s, H.264 640×360 30 fps, **las tres etiquetas BT.709 presentes**, Companion detenido, laboratorio limpio. [Evidencia ampliada](JUPITER_COMPANION_WINDOWS_W3B_W3E_2026-11-04.md). CI del último commit pendiente de confirmación.\n- **Siguiente:** selector Windows «Aceptar» y comprobación de raíces; después prototipo de arranque de un clic e instalación mínima. Quedan USB, HDR/GPU/Stage, integración cliente real; sin merge.

## Windows W3I–W3K · selector y bandeja · 04-11
- W3I PASS: 10 raíces, 5 existentes, 1 unidad; selector Windows con «Aceptar» y carpeta válida.
- W3J PASS: lanzador CMD y `/health` Companion 0.6.2, FFmpeg disponible; local_video/local_mix no habilitados.
- W3K PASS local comunicado: arranque sin consola, icono de bandeja, estado y salida operativos. **Prototipo PowerShell dependiente de Python 3.11 y FFmpeg instalados; no instalador independiente**. [Informe W3I–W3K](JUPITER_COMPANION_WINDOWS_W3I_W3K_2026-11-04.md).
- Siguiente: empaquetado one-folder sin requerir Python de usuario, revisión de gestión de procesos y licencias FFmpeg; PR #74 sigue draft, sin merge.

## Hito de cierre 04-11 · JÚPITER EX-14H-21–24
- **CERRADA y publicada** la investigación sobre EX-07/EX-13, tiempos de Stage, caché de color y branding: [informe reproducible](JUPITER_EX14H21_24_CLOSURE_2026-11-04.md). No se solicita merge.
- Motor de referencia JM 0.61 `3ff470ee`; worktree opt-in de pruebas `f305961` aislado, **sin tocar `main`, pin de motor ni servicios JM**. 35 tests focalizados PASS.
- EX21C/21D: renders móviles 360 de 3 s, 90 poses cada uno, cuatro ejecuciones A–B–B–A por escena: ahorro wall **23.40 %** (`pull_out`) y **19.28 %** (`pan_right`) con MP4 byte a byte idénticos. Cortes 360 reales inferiores a 2 s: estáticos por política editorial, sin speedup E2E demostrado.
- EX22A: mapas con EX-07 solo **31.96 %** menos tiempo; EX-13 solo **26.13 %**; ambas **46.74 %** (dos rondas, equivalencia exacta en 90 poses). Prueba solo geométrica, no render.
- EX24F: Stage 114.7103 s; reloj interno 95.611 s; análisis color 19.0875 s fuera del interno. EX24L: 84.1019 s y salida 12.0 s usando branding integrado y caché de segmentos privada; EX24F con bookends externos duró 32.2 s y los dos bookends costaron 27.817 s. **Comparación exploratoria**, no prometer mejora general. Branding integrado ya existía en motor JM.
- Caché de color v6→v7 deliberada en `4dee4a6`; no fallo demostrado. EX24F escribió en caché global de segmentos FER por referencia importada; EX24L corrigió aislamiento de las rutas utilizadas. `export.log` muestra saltos de línea literales `\\n`. No modificar caché histórica ni tocar el motor sin PR selectiva.
- **Siguiente fase:** retomar prioridades globales con Chema (Companion Windows, propuesta relink/local y F4 según estado vigente), sin encadenar nuevas pruebas EX-24 por inercia. El render local opcional Mac ya existe; no duplicarlo.

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

## Criterios acordados con Fernando (03-11)
- «main de ZuckerVideos» en conversación significa **motor más actualizado en uso efectivo**, no obligatoriamente la rama llamada `main`; contrastar `main`, rama activa de desarrollo y submódulo fijado en Montara.
- Integraciones: PR pequeñas desde commit reciente + pruebas E2E/capturas para no revertir avances visuales; no merge de rama laboratorio completa. Avisado Chema en Montara #34.
- **Capacidad objetivo futura**: 2, 5 y 10 usuarios simultáneos; el orden es medir primero E2E de un proyecto real con CPU/RAM/disco/cachés y costes, después pruebas de carga 2/5/10, sin prometer escalado lineal.
- Auditoría histórica: índice `docs/lab/INVENTORY-FER.md` F1–F8 y revisión focal de SATURNO 24–25, recursos cgroup, seguridad Mixer y arquitectura esférica. **No afirmar que se han leído íntegramente los 177 documentos Markdown archivados**; ampliar la lectura y registrar hallazgos sin repetir experimentos.

## Próximos objetivos
1. **Corto:** cerrar documentación de EX14H-08, control comparativo del motor actualizado y perfil de Stage representativo con EX07/13, misma fuente/máquina/pin, sin duplicar pruebas ya validadas.
2. **Corto:** revisar PR #51 contra rama activa y preparar integración selectiva en rama CORTA de ZuckerVideos desde la revisión actual; no activar defaults ni forzar merge. Mantener EX06 separado.
3. **Medio:** estudiar tiempo E2E real de 360, eficiencia CPU, buffers e infraestructura sin sacrificar imagen, audio, sincronía, reproducibilidad ni cancelación; investigar arquitectura local/híbrida y futuro Companion Windows tras priorización JM.
4. **Coordinación:** palabra clave «surcar con la escafandra espacial» = revisar main Montara, rama activa/pin motor, ambos repos, submódulos, issues/comentarios/PR/CI; comparar cambios y detener experimentos obsoletos. Revisar antes de incorporar actualizaciones, no hacer merge amplio sin tests.

Informes detallados: `docs/lab/JUPITER_EX14H_360_PIPELINE_SCIENTIFIC_REVIEW_2026-11-03.md` y `docs/lab/JUPITER_EX14F_PARALLELISM_RESEARCH_2026-11-03.md`. No afirmar validación productiva sin E2E.
