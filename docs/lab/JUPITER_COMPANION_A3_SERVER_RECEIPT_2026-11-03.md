# JÚPITER-A3 — Auditoría de recepción local en servidor
Fecha 2026-11-03 · Solo lectura de `main`, sin pruebas runtime ni cambios de producto.

## Código inspeccionado
- `app.py`: registra `full_session.register_full_session`.
- `full_session.py`: `folder` exige id de sesión de 12 caracteres hex y `session.json` existente; `/local-plan` genera plan por ventana, versión del mixer Git; `/local-result` verifica ventana/canción guardada, settings válidos, identificador de upload, `upload.json.complete`, ruta bajo carpeta Uploads, existencia y sufijo MP3. Mueve MP3 a `exports/local-<window>.mp3`, limpia etiquetas y registra `local_results/<window>.json` con firma. Actualiza `session.json.results` bajo `request.lock`.
- `mixer_adapter/session.py`: `local_results` valida SHA mixer Git, `mix_signature`, existencia física; `render` reinicializa results y reintroduce los locales válidos antes de procesar los pendientes. No se mezclan en servidor los que ya tienen resultado local reconocido.
- `web/full-session.js`: `mixSongsLocally` hace peticiones de plan, mezcla, subida reanudable y POST /local-result antes de POST /render; mantiene servidor como fallback de cada canción fallida. `confirmSong` inicia `queueSongOriginals` **sin comprobar si una mezcla local futura hará innecesarios esos originales**.

## Conclusión y límites
**Confirmado estáticamente:** controles sustantivos de ventana/subida/versionado/firma, reuso del MP3 local, fallback remoto, y riesgo de que Confirm anticipe subidas redundantes. **No demostrado:** explotación de una debilidad de autorización, pérdidas/corrupción de audio, duplicados reales, cuántos bytes sobran, bloqueo E2E en la VM. `folder(job_id)` comprueba formato/existencia, no por sí sola autorización por usuario; la autorización global queda fuera de este análisis y requiere auditar middleware real de `app.py`. No confundir `upload.json.complete` con validación de contenido acústico o checksum de MP3: no está demostrado aquí.

## Riesgos prioritarios y mitigación propuesta para revisión de Chema
1. `Confirm` no debería iniciar rangos originales **si se prevé mezclar localmente**, salvo fallback o elección explícita; requiere verificar UX porque Confirm hoy garantiza transferencia anticipada mientras usuario sigue editando.
2. Interrupción de HTTP: probar si el proceso Mac continúa y si se dispara a la vez fallback remoto; observar CPU y recursos, no asumir bug antes de prueba.
3. Reintento de `/local-result` con confirmación perdida: evaluar idempotencia, target por ventana y relación upload-consumido; comprobar seguridad bajo solicitudes concurrentes.
4. Distinción entre `/local-result` de una sesión y su propietario, validez del archivo, checksum/decodificación y límites de tamaño: revisar autenticación global y upload middleware con un especialista antes de lanzamiento público.

## Test mínimo propuesto en laboratorio, si Chema lo aprueba
Un proyecto de dos canciones cortas con 2 pistas sintéticas en una sesión separada: escenario A `Confirm` temprano, B export directo con mezcla local, C caída HTTP simulada. Registrar solo bytes subidos por tipo, estados, CPU, duración y duplicados, sin música privada ni render largo; mismo commit/build. No ejecutar mientras el otro laboratorio use la misma sesión. Validar primero que nuestra VM puede simular Companion Mac o realizarlo en Mac aislado: **no prometer prueba macOS desde Linux**.

**Decisión:** no implementar cambios; trasladar H1 (Confirm) como candidato útil, luego retomar Stage EX-14D si no hay nueva prioridad de Chema.
