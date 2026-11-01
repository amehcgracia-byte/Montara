# STATUS — laboratorio de Chema (main · claude/* · codex/*)

Actualizado: 2026-11-01 tarde · lo mantiene el equipo de Chema · 40 líneas como máximo, se sobrescribe.

## Referencias
- `mixer`: rama `claude/winds-synth-bass-lowpass` (ZuckerMixer PR #8, **sin mergear en master**); Montara apunta a su último commit
- VM: e2-standard-8, `jm` en `127.0.0.1:8101`, `fer` en `:8102`; apagado automático (60 min sin web, 120 min sin SSH)
- Companion **0.4.0** (rangos en Opus "Rápido"): se actualiza volviendo a ejecutar `companion/install.sh`

## Sesión completa (jam entera) — cómo va
| Pieza | PR |
|---|---|
| Copias ligeras en Opus para detectar y escuchar; originales solo de los rangos de canción | #36–#38 |
| Ondas por canción con tiradores, play, clic para saltar, Mixer/Split/Remove, mix por canción | #39–#45 |
| Solo, EQ (con high cut), tiras rediseñadas, sin pausa por inactividad mientras trabaja | #46–#47 |
| Confirm por canción; subida y mezcla en paralelo; onda y copia de escucha durante la detección | #48–#50 |
| Tipos de pista (menú por pista, rellenado por el nombre) + Stereo L/R | #51 |
| Motor: la puntuación de planos usa la copia ligera, no el original 4K de iPhone/Sony (hallazgo de Fer, #56; zucker_videos #49) | #58 |
| Rangos por ventana (un split ya no vacía la cola), estados de Confirm, mixer y Save al instante, círculo de carga, Opus "Rápido", pistas vacías fuera, "aplicar a todas", L/R enlazadas, mixer ancho, **diccionario de instrumentos** | #52 |

## Diccionario de instrumentos (ZuckerMixer `instrument_dictionary.py`)
- Cada tipo de Montara tiene una ficha: EQ, compresor, panorama, nivel y envíos, encima del rol. Valores de partida con fuentes (`SOURCES`): Samson (voz de podcast), iZotope (acústica), Music Guy Mixing (cuerdas, coros), Mixing a Band y Owsinski (metales, viento).
- Con ficha propia: percusión, guitarra acústica, trompeta, trombón, flauta, violín, cuerdas, coros, voz de podcast y narración. El resto usa el rol tal cual.
- Pendiente: detección por audio (hoy por nombre o por la elección de la persona); fichas para más instrumentos; afinarlas de oído con jams reales.

## Pendiente
- **Mezcla en el Mac (companion 0.5.0, opcional, #58)**: `install.sh --mixer` instala el mezclador del servidor en el Mac (unos 240 MB en Linux; falta medirlo en Mac); cada canción se mezcla allí y solo sube el MP3. Salida idéntica bit a bit a la del servidor en el test. Falta: medir tiempos en un Mac real. Informe de Fer: `JUPITER_COMPANION_MAC_LOCAL_MIX_FEASIBILITY_2026-11-01.md`.
- Licencias: Matchering (GPLv3, de terceros) solo se usa en el servidor; el mezclador del Mac no lo instala.
- Mergear ZuckerMixer PR #8 en master.
- El fallo de canciones cortadas o vacías del #48: arreglado el fallo de la cola (#52); falta confirmarlo con `deploy/vm/audio_check.py` en una sesión real.
- Cola de render para unos 10 testers (VM más grande y luego workers bajo demanda): sin empezar.
- La caché del companion crece sin límite.
- `run_history.py` no guarda qué cámara usa cada plano.
- Cambiar las contraseñas web de la VM que pasaron por chat (sin confirmar).
