# JÚPITER-A2 — Companion 0.5.3: flujo navegador → Mac → servidor

Fecha 2026-11-03. **Auditoría estática solamente**: no hay nueva ejecución en Mac/VM ni verificación E2E. Main revisado: `b718470c7d6ffb3a029a02a56785a1c489bc6890`. Complementa la auditoría JUPITER_COMPANION_053_STATIC_AUDIT.

## Trazabilidad de código
- `web/full-session.js`, `exportSession()`: guarda cortes, llama `mixSongsLocally(selected, per_song)`, después `/render` y encola rangos originales para canciones que quedan en server.
- `web/full-session.js`, `mixSongsLocally()`: exige previews y `montaraCompanion.localMixer()`; excluye canciones con mastering reference; pide `/local-plan`; valida `plan.mixer` frente a local; mezcla vía Companion y sube MP3 por resumable-upload; registra `/local-result`. Si fallo de mezcla o subida/registro, añade canción al conjunto `left` que seguirá al servidor. Las subidas de MP3 se solapan con la siguiente mezcla, pero su `catch` puede producir fallback remoto incluso tras una transferencia parcial.
- `web/companion.js`, `mixSong()`: `POST /mix-song` retorna blob MP3, mientras polling `GET /mix-progress/<id>` consulta progreso. La llamada de mezcla no lleva timeout explícito; su vida está vinculada a conexión HTTP.
- `companion/companion.py`, `mix_song()`: valida plan y original, versión del mixer, crea archivos temporales en caché; limita paralelismo con semáforo (1 por defecto); lanza `local_mix.py` en subprocess con timeout 3600s; envía MP3 y elimina temporales/progreso en `finally`. No se observó endpoint de cancelación específico para mezcla.
- `companion/local_mix.py`: extrae los rangos originales con `mixer_adapter.extract.window_command` y llama `SingleSongMix.render`, limpiando trabajo temporal. Sin control de cancelación por canción confirmado.
- `mixer_adapter/session.py`, `local_mix_signature()`/`local_results()`: servidor comprueba mixer SHA, selección de pistas y settings al reutilizar un master local. Esto reduce riesgo de resultados obsoletos, aunque falta revisar el endpoint HTTP de recepción `/local-result` para confirmar validación de propiedad, checksum, ventana y metadatos.

## Hallazgos con precisión de evidencia

**H1 Confirm anticipado:** `confirmSong()` en `web/full-session.js` llama `queueSongOriginals(song)` y `runUploader()`, mientras que la exportación intenta después mezcla local. Por tanto puede iniciarse subida de rangos originales **antes** del intento local. Si ocurre, el ahorro de tráfico puede ser inferior al pretendido. No se ha medido duplicación de bytes; depende de secuencia del usuario/estado, no afirmar que suceda siempre. Candidato a ensayo no destructivo con red instrumentada y dos escenarios (Confirm anticipado vs Export directo).

**H2 fallback y trabajo duplicado:** errores en `mixSong` o en subida/registro de MP3 pasan a mezcla remota. Si se interrumpe una conexión HTTP mientras `subprocess.run` sigue vivo, el servidor podría comenzar a mezclar lo mismo en paralelo. Hipótesis razonable, **no verificada en runtime**. Ensayo con desconexión inducida en entorno aislado y métricas de procesos CPU, duplicación, interfaz y cancelación.

**H3 consistencia temporal/UI:** `mixSongsLocally` termina las mezclas locales antes del `POST /render` remoto, aunque uploads se solapan, y los eventos `/local-result` llegan antes del inicio del render. Hay que comprobar que el servidor persiste y reidentifica canciones aunque se renumeren/cambien ventanas. Riesgo mitigado por `local_mix_signature` y window keys, aún no validado E2E en este informe.

**H4 seguridad local:** `companion.py` verifica Origin para POST y usa `127.0.0.1`, pero no identificamos token de sesión en esta ruta. La regex predeterminada admite dominios `trycloudflare.com` y `vercel.app` de patrones amplios. Analizar autorización exacta y Host/DNS rebinding con casos controlados, sin afirmar explotación.

## Comprobaciones prioritarias sin tocar producción
1. Localizar y leer handler de `/local-plan`, `/local-result`, `/render`; confirmar propietario de sesión, SHA/checksum, validaciones `window`, transacciones, idempotencia y condición de render.
2. Test de coste de red con dos caminos de usuario: Confirm previo y Export sin Confirm, con 2 canciones y stems, bytes por ruta, transmisión de originals y estado del resultado.
3. Interrumpir petición `/mix-song` durante procesado en Mac aislado; comprobar continuidad/cancelación de CPU, limpieza y fallback sin trabajo doble.
4. Reintento de `/local-result` tras registrar el MP3 y simular respuesta HTTP perdida; verificar ausencia de duplicados y asociación por ventana.
5. En instalación aislada, comprobar versión concurrente/rollback; fijar dependencias y medir caché. Sólo tras esta batería decidir correcciones mínimas coordinadas con Chema.

## Cierre
Se han identificado **riesgos específicos y trazables**, no bugs E2E certificados. No modificar `main`, `engine/`, `mixer/`, ni rama local de ZuckerVideos a la espera de permiso de Chema. Priorizar una pequeña validación del flujo real; después continuar Stage EX-14D, sin prolongar indefinidamente el diagnóstico Companion.
