# MONTARA · Primer Stage→Companion→MP4 real (validación humana, 2026-11-13)

**Estado:** Primer MP4 generado sin errores visibles en recorrido H4. *La reproducción detallada y la localización exacta del archivo todavía deben validarse por el usuario*. No asumir que main está integrado ni que la versión 0.6.12.0 está instalada.

## Evidencia

- Usuario ha entrado correctamente mediante Google OAuth a H4.
- Companion Windows SMART Beta existente iniciado directamente mediante Python local: GET `http://127.0.0.1:47820/health` respondió con `app=montara-companion`, versión `0.6.10`, `ffmpeg=true`, `local_video.engine=b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b`, `busy=false` después del render.
- El parche específico de `WinError 5` en el indicador de progreso del render ya estaba aplicado mediante Companion nativo MSIX de desarrollo. El instalador MSIX `0.6.11.1` **solo controlaba la bandeja**, no incluía servicio; el usuario lo cerró e inició el viejo servicio `smart_beta_launcher.py` desde `Desktop/Montara-SMART-Beta` usando Python en PowerShell **sin ejecutar** los scripts PowerShell antiguos de arranque oculto.
- Captura humana del render: `Rendering segment 95/122`, 31%, `Elapsed 7m 7s`, `36 of 36 started shots finished`. Se observan barras verdes por toma.
- Al terminar, interfaz muestra resultado sin errores y ofrece descarga mediante `http://127.0.0.1:47820/video-renders/<token>/file?download=1`. El token es privado y no debe publicarse en docs.
- El código confirma que `companion/video_jobs.py::VideoJobs.start` asigna el resultado a `project_folder / (sanitized_name + '.mp4')`; crea `project_folder/.montara-renders/<token>` para manifest, logs y progreso. Al finalizar `_save_completed` escribe índice `%LOCALAPPDATA%/MontaraSMARTBeta/video/completed-jobs.json`. `companion/companion.py::send_video` sirve ese mismo archivo local mediante lectura por bloques, con `Content-Disposition: attachment` en modo `download=1`. Por ello «Descargar» crea **una segunda copia** con el navegador; no obtiene el MP4 de Google Cloud y no borra la copia final en proyecto.
- El frontend `web/montara.js::showResult` marca exportación nativa `savedLocally=true`, de modo que evita el otro flujo de `saveInProject` para exportaciones no nativas. Estado de la arquitectura validado: los originales permanecen locales, el MP4 final también.

## UX inmediatamente derivada

- Resultado de exportación local: botón principal «Abrir carpeta del vídeo» / «Mostrar en el explorador» y nombre/ruta persistente; «Guardar otra copia…» como secundaria. No crear innecesariamente copias del MP4 en Downloads. Abrir Explorer desde Companion con acción autenticada y validación de proyecto/ruta; **no abrir rutas arbitrarias suministradas por cualquier sitio web**.
- El servidor HTTP local usa enlace con token de 32 caracteres hexadecimales. Por ser un token de capacidad en URL, mantenerlo privado, no registrarlo en telemetría pública, y estudiar caducidad de la capacidad y restricción segura de descarga sin romper el enlace local del navegador. Nunca publicar tokens reales de render en documentación.
- Evitar reinstalar el Engine ya corregido o borrar la salida final al actualizar el MSIX.

## Barras verdes y orden de render

- Código `web/montara.js::renderShotBars` crea **una barra CSS `<i>` por segmento**, lee `tasks segment-N` y cambia solo la variable `--p` de cada una. Se actualiza con el sondeo de estado (cada ~700 ms en `watchNativeVideo`). La UI es trabajo ligero del navegador, **no un transcode FFmpeg adicional**. El coste de CPU real de CSS/DOM no se ha perfilado; no prometer cifra exacta.
- El motor configurado en `companion/local_video.py` establece `segment_workers=2`; el Engine `core/stages/export.py` usa `ThreadPoolExecutor(max_workers=segment_workers)`. Las tomas no están visualizadas en orden de finalización porque dos tareas progresan en paralelo, pueden variar en complejidad/codec/efectos/duración, y las barras permanecen colocadas según su **posición definitiva en la línea de tiempo** (no en orden de finalización). El mensaje `Rendering segment N` identifica la tarea reportada, no garantiza que anteriores hayan acabado.
- Por encima, `web/montara.js::setProgress` muestra progreso global en anillo, diferente de progreso individual de segmentos.

## Rendimiento: estudiar después del primer MP4, sin introducir cambios hoy

Medir en Windows de desarrollo con la misma muestra y las mismas entradas:
- Tiempo de `ffprobe`, decodificación, filtros de encuadre/360, codificación, audio, concatenación y validación final.
- CPU lógico y físico, uso de RAM 8 GB, disco, temperatura y posibles `thermal throttling`. El 400% de CPU que menciona el usuario suele reflejar utilización agregada de cuatro hilos lógicos; no significa trabajo de la UI por barra.
- Matriz reproducible de `segment_workers=1/2` y FFmpeg `-threads` en el i5-6300U, con nivel de calidad, GOP/VBV, tamaño, audio y exactitud preservados. No subir originales, ni crear más de un render innecesario en beta personal.
- Priorizar **caché por segmento realmente inalterado** entre exportaciones/ediciones, revisión incremental de miniaturas (incidencia documentada en `H4_REVIEW_DELTA_AFTER_SHOT_SAVE_2026-11-13.md`) y posible aceleración hardware por perfil donde FFmpeg la soporte sin cambiar calidad inadvertidamente.
- No retirar la visualización de barras sin medirla: coste esperado pequeño, pero requiere perfilado real. En particular actualizar solo variables de CSS en barras modificadas y limitar repaints.

## Sesiones beta H4

Google OAuth y el almacén SQLite establecen sesiones con expiración para limitar duración de una cookie de acceso si se filtra, permitir caducidad/revocación y separar identidad/proyectos.
- Incidencia previa 3d: el flujo Google intentaba emitir sesiones de `3*86400` s, pero `SessionStore.issue` admitía solo `86400`; el error genérico sucedía tras seleccionar cuenta. Corregido y verificado.
- Por petición expresa del usuario, **H4** pasa a `ttl_seconds=10*86400` con límite idéntico en `SessionStore`. Default de `SessionStore.issue()` sigue 3600 s. CSRF rotativo, cookie `Secure`, `HttpOnly`, `SameSite=Lax`, y revocación por SQLite preservados.
- Las sesiones ya emitidas conservan su expiración original: se necesitan nuevas autenticaciones para obtener 10 días. Beta privada; producción debe definir política por riesgo/compartición de equipos y logout explícito.
- Validado en GCP: 3 pruebas (10d emitido y caduca exactamente, límite +1 rechazado, default 1h intacto). Servicio `montara-owner-h4-native.service` activo y health HTTPS 200. Backup `~/.config/montara-h4-native/rollback-google-10d-20261113`.
- No cambiar OAuth Google Cloud, no compartir URLs de callback, códigos ni tokens.

## Principal objetivo pendiente: llevar a main

No es un hito final; queda consolidar rama privada sin perder editor de Chema ni submódulos pinned. Gate de merge: Google/OAuth 10d probado, Companion Windows con servicio autónomo y firma estable, render export válido, arreglos incremental footage, validación multiusuario, rollback documentado y revisión de Chema. **No fusionar sin confirmar estos gates**.
