# STATUS — laboratorio de Chema (main · claude/* · codex/*)

Actualizado: 2026-10-30 tarde · lo mantiene el equipo de Chema · 40 líneas como máximo, se sobrescribe.

## Referencias
- `engine`: `c89e779` · `mixer`: `c7a46a6` · rama de Fer revisada hasta `f77ba0e`
- VM: Ubuntu 24.04, **e2-standard-8 (8 vCPU / 32 GB)** desde el 30-10; `jm` en `127.0.0.1:8101`, `fer` en `127.0.0.1:8102`
- Apagado automático (PR #29–#31): se apaga si pasan **60 min sin uso de la web**, **120 min sin teclear en SSH** y no hay ffmpeg, mezclador ni `montara-bench` en marcha. Trabajos de más de 2 h sin teclear: siempre bajo `montara-bench`.
- Originales grandes para pruebas en `/home/fer/lab-clips/originales`: 360 HEVC 3840×1920 (912 s), 4K H.264 3840×2160 (987 s), Sony 1080p (90 s), canción MP3 (634 s).

## Integrado en `main` desde el último STATUS
| Pieza | PR |
|---|---|
| Recordar el material entre recargas (IndexedDB + handles) | #20 |
| Zoom 360 instantáneo en el navegador; espera sin límite de 20 min | #21 |
| Companion **macOS** sin interfaz: versión pequeña 720p en el Mac y solo eso se sube; carpeta de proyecto; el vídeo final se guarda en esa carpeta | #22, #23, #24 |
| Rango de canción (Start/End) → `trim_start_sec`/`trim_end_sec` | #24 |
| Vista previa estereográfica (sin ojo de pez), hover inmediato, barras de render por plano | #26 |
| Historial de tiempos `docs/lab/RUNS.md` + `deploy/vm/run_history.py` | #27, #28 |
| Herramientas del Mac (`montara-start/stop/update/runs/autostop`) | #25, #29 |
| Reproductor del resultado: controles debajo del vídeo | #32 |

## Cómo funciona hoy a nivel usuario (feedback de Chema, 30-10)
- El motor actual le convence: último proyecto con 8 vCPU «bastante rápido».
- **El render final se hace en el servidor.** Con companion conectado, el MP4 se copia solo a la carpeta del proyecto en el Mac; si no, botón Download.
- Mayor coste conocido: reproyección 360 en CPU (6,3× más lenta que tiempo real en 4 vCPU; ver RUNS.md).

## Para el laboratorio de Fer (lo que necesitamos de vosotros)
1. **Companion para Windows** (vuestra área): hoy `companion/companion.py` es Python + FFmpeg y casi portable, pero el instalador es `.command` (macOS) y el diálogo de carpeta usa `osascript`; en Windows cae a `MONTARA_COMPANION_PROJECTS` o al HOME. Falta: instalador de doble clic, diálogo nativo de carpeta, búsqueda de originales sin Spotlight y codificador por hardware (NVENC/QSV/AMF) con caída a libx264. Sin tocar la API (`/health`, `/locate`, `/proxies`, `/projects`).
2. **Render local con los originales (relink, FOCUS_A_C)**: que el vídeo final se monte en el ordenador del usuario con los originales, no en el servidor.
3. **F4 bilineal con material real**: medir con los originales de arriba antes de proponer el cambio en `zucker_videos`.
Cada resultado: fila en `docs/lab/RUNS.md` + `runs.jsonl` y una línea en STATUS-FER.

## Pendiente
- Fila en RUNS.md del primer render con 8 vCPU (falta `montara-runs` de Chema).
- Cambiar las contraseñas web de la VM, que pasaron por chat.
