# Handoff — Montara 0.54 (2026-11-01) · laboratorio de Chema

Este documento resume el estado actual para quien retome Montara en una sesión nueva. Léelo después de `CLAUDE.md`. Contexto vivo en `docs/lab/STATUS-JM.md` (hecho/pendiente) y `docs/lab/STATUS-FER.md`.

## Personas y forma de trabajar
- **Chema** es el dueño del producto. Mergea a `main` o pide que se mergee cuando la CI está verde. Quiere respuestas en **español**, directas, con la verdad incómoda primero y etiquetas [Certain]/[Likely]/[Guessing]; código antes que explicaciones; informes cortos.
- **Chema no quiere probar a medias.** Prefiere un PR con todo lo pendiente, un `montara-update` y entonces prueba. Avisarle solo cuando esté completo.
- **Fer** (primo, GitHub `luccifer00`) trabaja en la rama `fernando/continuacion-montara` ("JÚPITER"): experimentos e informes, no código de producto. Se le escribe en el **issue #34** con tono pirata y en forma de prompt. Sus avisos llegan como issues (#53 FFmpeg, #54 disco, #56 EditStage).
- Repos públicos: nada de secretos ni rutas privadas en los commits.

## Infraestructura
- **VM** `montara-test` (GCP, proyecto `montara-pruebas-10292226`, zona `europe-west3-a`, e2-standard-8, disco de 96 GB). Usuario `jm` en `127.0.0.1:8101` (gunicorn 1 worker × 8 threads, servicio systemd de usuario) y `fer` en `:8102`, que no se toca. Se apaga sola: 60 min sin web o 120 min sin SSH.
- **Desde un contenedor no se puede hacer SSH a la VM** (desde una sesión en el Mac de Chema, sí). Chema ejecuta los comandos desde su Mac con las herramientas de `deploy/vm/mac-tools.sh`:
  - `montara-start`: enciende la VM y abre un túnel SSH a http://127.0.0.1:8101 que se reconecta solo. `--public` da una dirección de Cloudflare.
  - `montara-update`: pone la VM en `main`.
  - `montara-diagnose`: estado de la última sesión.
  - `montara-disk report` y `montara-disk clean … --apply`: espacio en disco y limpieza.
  - `montara-runs`, `montara-stop`, `montara-autostop`.
- **Companion** (`companion/companion.py`, versión 0.5.0) en el Mac de Chema, puerto 47820. Se instala con `curl -fsSL https://raw.githubusercontent.com/amehcgracia-byte/Montara/main/companion/install.sh | bash -s -- --mixer`. No se actualiza solo.
- **Submódulos**, nunca se editan dentro de Montara:
  - `engine/`: zucker_videos, rama `claude/recover-montara-engine`, ahora en `ff9baf4`.
  - `mixer/`: ZuckerMixer, rama `claude/winds-synth-bass-lowpass`, ahora en `2c0c07c`; su **PR #8 no está mergeado en master**.
  - Para mover un puntero, se cambia el repo propio y luego se hace un commit aparte en Montara que nombre el commit del submódulo.
- **CI de Montara**: e2e de stage, push, session y mix, más private-container (unos 50 min). En zucker_videos, los "fast tests" ya fallan en la base (13 tests de 360, landmarks y menú) y `test_wizard_orchestration_exports_tiny_media` falla de forma intermitente.

## Qué hace hoy la sesión completa (Stage → "Full session")
1. **Subida**
   - Con el companion, cada pista sube como copia ligera en Opus (`name.wav.opus`).
   - Cada pista lleva un menú de **tipo** (rellenado a partir del nombre; si la persona lo elige, la pista no se silencia como ruido) y otro de **Mono / Stereo L / Stereo R**.
   - Las **pistas vacías** se detectan y quedan fuera. Desde la revisión se pueden recuperar con "use it anyway".
2. **Detección**
   - Encuentra las canciones. La onda sale de las envolventes de la detección.
   - La copia de escucha (`listen-all.webm`) se genera durante la detección y la barra la espera (0.55): la revisión abre con el play listo. Antes tardaba 414 s frente a 79 s de la detección en una jam de 1h56 con 9 pistas; ahora, unos 100 s con la VM libre.
3. **Revisión**
   - Cada canción tiene su onda con tiradores, play (con un círculo de carga), clic para saltar, y botones Mixer, Split, Remove y **Confirm**.
   - Confirm pasa por Confirming… → Confirmed · sending n/m → ready.
4. **Mixer por canción**
   - Es una pantalla instantánea. Tiene Solo, EQ (low, mid, air y high cut), FX con "preparing…", tiras L/R enlazadas y "Apply this mix to all songs".
   - "Save mix" vuelve a la lista al momento.
5. **Exportar**
   - Con el **mezclador local** del companion, cada canción se mezcla en el Mac (`/local-plan` → companion `/mix-song` → `/local-result`) y solo sube el MP3. La salida es idéntica bit a bit a la del servidor en `tests/test_local_mix.py`.
   - Lo demás lo hace el servidor con los originales: rangos por ventana en Opus "Rápido" por defecto (o "Sin pérdida"), varias canciones en paralelo y "Download all".
6. **Diccionario de instrumentos** (`mixer/instrument_dictionary.py`): EQ, compresor, panorama, nivel y envíos por tipo, con fuentes. Montara lo pasa como `STEM_INSTRUMENTS`.

## PRs de esta etapa (todos en main)
- #35–#50: sesión completa, companion de audio, mixer por canción, Solo/EQ, Confirm, velocidad.
- #51: tipos de pista y L/R.
- #52 (0.53): rangos por ventana (un split ya no vacía la cola de subidas), Opus Rápido, pistas vacías, estados de Confirm, "aplicar a todas", L/R enlazadas, mixer ancho, diccionario de instrumentos.
- #55, #57: herramienta de disco (`deploy/vm/disk.py`).
- #59 (0.54): mezclador local en el companion. Además, el motor puntúa los planos con la copia ligera y no con el original 4K de iPhone/Sony (hallazgo de Fer en #56; zucker_videos #49).
- #60: `montara-start` en local.

## Pendiente, por prioridad
1. ~~Primera prueba real del mezclador local en el Mac de Chema.~~ Hecha el 2026-11-01 (sesión `6c332051e567`): 12 de 12 canciones con `local: true`, 47,5 min de música en 12,4 min, unos 16 s por minuto de canción. Los tiempos están en `local_results/*.json` de la sesión, en la VM.
2. **Confirmar con una jam real** que no se repite el fallo de canciones cortadas o vacías de la 0.48: `deploy/vm/audio_check.py`, enviado a Chema como comando de gcloud en base64.
3. **Retención automática del disco**: borrar sesiones viejas salvo la última y avisar cuando el disco se llene (issue #54). Hoy hay 39 GB libres, con un 60 % de uso.
4. **Mergear ZuckerMixer PR #8** en master.
5. **Usar Montara desde el móvil sin el ordenador.**
   - [Likely] Hace falta una dirección fija en la VM: Cloudflare como servicio, o un dominio con Cloudflare Tunnel y acceso con contraseña.
   - Sin el companion no hay copias ligeras ni mezcla local; desde el móvil se subirían los archivos tal cual.
   - Requiere la aprobación de Chema si cuesta dinero.
6. **Cola de render para unos 10 testers** (VM más grande y después workers bajo demanda): sin empezar.
7. **Afinar de oído el diccionario** y añadir detección por audio (hoy los tipos salen del nombre o de lo que elige la persona).
8. **Licencias**: ZuckerMixer es GPLv3 de Chema, que como autor decide su uso. Matchering (GPLv3, de terceros) solo se usa en el servidor; el mezclador del Mac no lo instala.
9. Menores:
   - la caché del companion crece sin límite;
   - `run_history.py` no guarda qué cámara usa cada plano;
   - hay que cambiar las contraseñas web de la VM.

## Comprobaciones habituales
- `python -m pytest -q tests`: 175 pasan. Los dos tests de yt_dlp fallan en este contenedor porque falta la dependencia.
- `python tests/e2e_session.py --output <dir>`. Con `MONTARA_E2E_COMPANION_HOME=<companion instalado con --mixer>` cubre también la mezcla local.
- `python tests/e2e_journey.py --output <dir> --mode mix|stage|push`. Necesita librosa.
- En ZuckerMixer (`mixer/`): `python -m pytest -q --ignore=test_menu.py` (242).
