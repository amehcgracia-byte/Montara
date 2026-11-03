# JÚPITER — Gate de tráfico «Confirm» y cierre parcial Companion
Fecha 2026-11-03. Estado: **causa de duplicación potencial confirmada estáticamente, volumen NO medido**.

## Evidencia y causalidad
- `web/full-session.js:confirmSong` ejecuta `await queueSongOriginals(song)` y marca confirmada la canción.
- `queueSongOriginals` consulta `/originals`, añade ventanas pendientes y llama `runUploader()`; dicho uploader transmite segmentos de originales (Opus/FLAC/WavPack), no el MP3 final.
- `exportSession` llama después `mixSongsLocally` sobre seleccionadas; con Companion compatible produce MP3 y lo registra mediante `/local-result`, y únicamente encola los originales de `serverSongs` tras `/render`.
- `full_session.py:/local-result` verifica ventana guardada, upload completo, archivo MP3, y persiste firma de mezcla; `mixer_adapter/session.py:local_results` verifica SHA del mixer y firma de ajustes antes de omitir render servidor.
- Con **Confirm anticipado** el uploader puede comenzar a enviar audio que luego **no es necesario** si la mezcla local tiene éxito. Sin Confirm anticipado el código de export evita esta ruta para canciones locales. No afirmamos bytes concretos, ni que la subida llegue siempre a completarse.

## Ensayo A/B mínimo pendiente (NO ejecutado)
Utilizar Mac con Companion 0.5.3 y sesión desechable de dos pistas de 30–60 s, dos canciones, `uses_previews=true`, mismo mixer SHA, sin reference, misma red. Dos sesiones limpias: A pulsar Confirm de ambas y esperar a que salte transferencia, luego Export; B export directo. Medir **bytes de transferencias de rangos originales vs MP3 final** (Network browser / logs), latencia al primer resultado, estado de resultados `local`, cantidad de subidas. Evitar meter música privada en logs. Repetir una vez para comprobar caché. No probar en la VM solamente: `/mix-song` corre en el ordenador cliente.

## Plan de modificación candidato (sujeto a Chema)
Conservando interfaz: si mixer local disponible y SHA válido, Confirm puede retener sus ventanas sin transferir hasta que falle o se descarte mezcla local. Mantener posibilidad de subida anticipada para Mac sin mixer o canciones con reference y restaurar fallback. Una decisión sobre UX es necesaria: Confirm hoy cumple también la función de empezar a transferir; retrasarla puede empeorar algunas rutas. Verificar métricas antes de cambiar.

## Próximo frente EX-14D
Fuente primaria `amehcgracia-byte/zucker_videos:core/stages/export.py` en main: gran exportador, emplea `ThreadPoolExecutor`, `SPHERICAL_EXPORT_MOTION_MODE = "native_remap"`; `core/stages/edit.py` prepara los segmentos. Procede auditoría granular de colas, cachés, dependencia de fases, tiempos y tipo de cámara sin render largo. No confundir mejoras de filtro v360 con native_remap.

Sin código de producto, sin benchmarks reales nuevos. Esperando permiso de Chema para publicar ramas experimentales de ZuckerVideos.
