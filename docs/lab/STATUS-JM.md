# STATUS — laboratorio de Chema (main · claude/* · codex/*)

Actualizado: 2026-11-03 · lo mantiene el equipo de Chema · 40 líneas como máximo, se sobrescribe.

- `mixer`: rama `claude/winds-synth-bass-lowpass` (ZuckerMixer PR #8, **sin mergear en master**); Montara fija `f15ff91` (limitador suave, PR Mixer #9)
- VM: e2-standard-8, `jm` en `127.0.0.1:8101`, `fer` en `:8102`; apagado automático (60 min sin web, 120 min sin SSH)
- Companion **0.6.1 instalado en el Mac**: mixer `f15ff91` conservado y renderizador Stage opcional `affe97a`; sin modelos de IA.

## Sesión completa (jam entera) — cómo va
| Pieza | PR |
|---|---|
| Copias ligeras en Opus para detectar y escuchar; originales solo de los rangos de canción | #36–#38 |
| Ondas por canción con tiradores, play, clic para saltar, Mixer/Split/Remove, mix por canción | #39–#45 |
| Solo, EQ (con high cut), tiras rediseñadas, sin pausa por inactividad mientras trabaja | #46–#47 |
| Confirm por canción; subida y mezcla en paralelo; onda y copia de escucha durante la detección | #48–#50 |
| Tipos de pista (menú por pista, rellenado por el nombre) + Stereo L/R | #51 |
| Motor: la puntuación de planos usa la copia ligera, no el original 4K de iPhone/Sony (hallazgo de Fer, #56; zucker_videos #49) | #59 |
| Progreso por canción y pista en mezcla local/servidor; MP3 completo antes de activar Play, resultados a medida que terminan; Fast fijo;  limitador estéreo suave y objetivo automático −15 LUFS | 0.56–0.57 |
| MP3 sin etiquetas internas ni carátulas heredadas: el nombre es el del archivo; también se limpian descargas individuales y ZIP de sesiones anteriores, sin recodificar audio | 0.58 |
| Primer play sin espera: copia de escucha de 414 s a unos 100 s con la VM libre en una jam de 1h56 (un decodificador por pista, suma en numpy) y la barra de carga la incluye; `montara-start` no abre una segunda conexión | 0.55 |
| Rangos por ventana (un split ya no vacía la cola), estados de Confirm, mixer y Save al instante, círculo de carga, Opus "Rápido", pistas vacías fuera, "aplicar a todas", L/R enlazadas, mixer ancho, **diccionario de instrumentos** | #52 |
## Vídeos en discos externos (companion 0.5.1)
- Fallo: `/Volumes/Macintosh HD` enlaza a `/`; la búsqueda se gastaba los 25 s ahí y no llegaba a los discos siguientes, y la página subía el original sin avisar.
- Ahora: un recorrido por disco a la vez, 180 s de margen, carpetas recordadas en `places.json`, y un archivo de más de 200 MB no encontrado pregunta antes de subirse entero.
- Versión pequeña por el chip gráfico (`scale_vt`, `transpose_vt`), con software de reserva. En el Mac de Chema: 5 veces menos CPU; 4K de 1,0x a entre 1,3x y 1,9x; 1080p, parecido (2,2x-3,1x). El techo es el decodificador del chip.
## Diccionario de instrumentos (ZuckerMixer `instrument_dictionary.py`)
- Cada tipo de Montara tiene una ficha: EQ, compresor, panorama, nivel y envíos, encima del rol. Valores de partida con fuentes (`SOURCES`): Samson (voz de podcast), iZotope (acústica), Music Guy Mixing (cuerdas, coros), Mixing a Band y Owsinski (metales, viento).
- Con ficha propia: percusión, guitarra acústica, trompeta, trombón, flauta, violín, cuerdas, coros, voz de podcast y narración. El resto usa el rol tal cual.
- Pendiente: detección por audio (hoy por nombre o por la elección de la persona); fichas para más instrumentos; afinarlas de oído con jams reales.
## Pendiente
- **0.60 instalada JM (`5a65f50`)**: cancelación confirmada (servidor/local/cola), cuadrados por plano desde originales y descarga con nombre de proyecto (#70, Editor #52). Luz, originales y Atrás/Adelante de 0.59 conservados. Cinco recorridos Linux aprobados en `41620201927`, capturas revisadas; reproducción H.264 aceptada con Chrome oficial. Ver `docs/CANCEL_AND_PROGRESS_060.md`.
- Vídeos por lote para canciones ya mezcladas y dos cámaras iguales con zoom según encuadre: revisión y aceptación pendientes en `docs/PENDIENTES_CAMARAS_Y_LOTES.md`.
- **Mezcla en el Mac (companion 0.5.1, opcional, #59)**: `install.sh --mixer` instala el mezclador del servidor en el Mac (171 MB); cada canción se mezcla allí y solo sube el MP3. Salida idéntica bit a bit a la del servidor en el test. **Medido el 01-11 en el Mac de Chema (MacBook Pro 13" Intel i7, 4 núcleos), jam de 1h56 con 9 pistas: 12 de 12 canciones con `local: true`, 47,5 min de música en 12,4 min (entre 32 y 91 s por canción, unos 16 s por minuto), frente a la estimación de 140 min subiendo los originales al servidor.** Una canción a la vez (`MONTARA_COMPANION_MIX_SLOTS=1`); falta probar con 2 y confirmar por oído. Informe de Fer: `JUPITER_COMPANION_MAC_LOCAL_MIX_FEASIBILITY_2026-11-01.md`.
- Licencias: Matchering (GPLv3, de terceros) solo se usa en el servidor; el mezclador del Mac no lo instala.
- Mergear ZuckerMixer PR #8 en master.
- El fallo de canciones cortadas o vacías del #48: arreglado el fallo de la cola (#52); falta confirmarlo con `deploy/vm/audio_check.py` en una sesión real.
- Cola de render para unos 10 testers (VM más grande y luego workers bajo demanda): sin empezar.
- Caché del companion sin límite; barras locales ya disponibles en el 0.6.0 instalado.
- `run_history.py` ya registra reparto por cámara y segundos 360 (`5fe4880`); falta el manifest del ensayo histórico de 628,2 s, no recuperable de la fila antigua.
- Cambiar las contraseñas web de la VM que pasaron por chat (sin confirmar).
