# MONTARA SMART — Audio lossless: corrección coordinada Owner/JM y candidato reversible
**Fecha:** 2026-11-11 · **Rama:** `fernando/integracion` · **Estado:** candidato comprobado, **no activado en broker**.

## Bloqueo y causa delimitada
- En una prueba humana, Companion prepara proxies locales de vídeo y audio y la API privada responde `Invalid private upload`. No se capturó tamaño ni código exacto de aquella petición, así que **no se afirma que el límite sea la causa definitiva de esa transferencia**.
- `web/companion.js` de Chema crea vídeo `nombre.small.mp4` y audios lossless con sufijo original, p. ej. `nombre.mp3.flac` o `nombre.wav.wv`. `web/resumable-upload.js` crea metadatos JSON, fragmentos de 4 MiB y finaliza. El Engine remoto no lee el disco de Windows.
- La beta anuncia `MONTARA_PRIVATE_PREVIEW_LIMIT_MIB=2048`, pero el validador Owner y el `resumable_upload.py` original I56 limitan ciertos lossless a 256 MiB. Una ejecución real, con las mismas variables de sesión del worker, reprodujo `413` para `nombre.mp3.flac` de tamaño declarado 300 MiB. Por contraste, audio pequeño completó `201 → 200 → 200` y se clasificó como `master`.

## Solución sin desproteger los originales
- `urano/first_valid_upload_gate.py`: la regla de tamaño admite hasta la cuota privada configurada únicamente para sufijos de audio derivados reconocibles (`.mp3.flac`, `.wav.flac`, `.wav.wv`, etc.), previews compactos de audio y `.small.mp4` identificado como proxy de vídeo. Cargas originales de vídeo, archivos genéricos y formatos falsos conservan el límite menor; nombre, extensión, fingerprint, CSRF, propietario y generación del Engine continúan verificándose.
- `urano/jm_private_proxy_overlay.py`: el constructor original I55 ahora emite la misma política, y la función `patched_reviewed_private_audio_overlay` permite actualizar por copia un bundle I56 ya revisado mediante anclas exactas, **sin reescribir el editor original ni el bundle activo**. Falla si la versión difiere.
- `scripts/stage_owner_lossless_jm_candidate.py`: copia recursos en un directorio candidato independiente, omite objetos internos Git de permisos root y pycache, actualiza solo `resumable_upload.py` y el SHA-256 del manifiesto y verifica ambos. No cambia ni reinicia services.
- `tests/test_urano_owner_original_jm_rpc.py` y `tests/test_urano_jm_private_proxy_overlay.py`: regresiones de media metadata, cuota, nombres de audios, fichero original de vídeo no consentido y versión de bundle fail-closed.

## Resultado real de laboratorio, sin tocar los proyectos
- Candidato en VM: `/tmp/montara-lossless-audio-release-20261111/jm-14cce126137a0ef30a987351ff35b750f54473bd`.
- Tupla fijada: Chema JM `14cce126137a0ef30a987351ff35b750f54473bd`, Engine `b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b`, Mixer `f15ff91c1b80fc5f157099dcd9451d958d553ae6`, cuota privada 2048 MiB.
- SHA de uploader antiguo `264285f26a3106b7be55cb2d46b2769f7c3f9cbad7d484c5ddd7301c6c36073d`; nuevo candidato `0baa371327231474ebbbda7f0a0710b6da9bac3c6806a62f50983469b8593128`.
- `verify_pinned_chema_manifest` y `verify_jm_bundle_files` PASS. El bundle original permanece intacto.
- Importador JM real con el **uploader exacto del candidato**: apertura HTTP 200, creación de audio pequeño HTTP 201, fragmento HTTP 200, finish HTTP 200, clasificación `master`; metadata de audio lossless 300 MiB HTTP 201; metadata de original MOV 300 MiB HTTP 413; `.flac` genérico 300 MiB HTTP 413; `video_preview=true` sobre `camera.mp4` sin nombre `.small.mp4` HTTP 413.
- Regresiones agrupadas: **42 pruebas Python PASS, 74 subpruebas PASS, 2 pruebas omitidas**. Incluye RPC Owner, gate, broker privado y política de orígenes.

## Precauciones antes de activar en la beta
- El servicio root `montara-i26-broker.service` apunta al bundle antiguo en `/opt/montara/bundles/jm-14cce126...`. Cambiarlo exige instalar un directorio inmutable nuevo de propietario root, modificar el drop-in y reiniciar el broker. Hay workers de propietario activos; por eso **NO se realizó** esta operación ni se apagó ninguno.
- El candidato temporal contiene un enlace `engine -> /opt/montara-engine/engine` que solo se resuelve dentro del namespace de worker que configura el broker. Los ensayos nativos aislaron el Engine fijado en un directorio temporal; no hay PASS root broker con bundle candidato. El manifiesto está comprobado, pero no debe confundirse con despliegue.
- Cuando exista una ventana sin trabajo, instalar el candidato root-owned en ruta nueva, verificar servicio broker y workers previos, cambiar el puntero con rollback del drop-in y comprobar un primer proyecto/carga sintética. Mantener enlace antiguo y manifiesto como reversión.
- No se ha resuelto ni reproducido el upload concreto del navegador de Fernando, ni se ha validado MP4 E2E. El nuevo código de diagnóstico deja un motivo específico en futuras peticiones. No subir originales ni pedir más pruebas humanas sin aislar la causa.

## Siguiente paso prioritario
Activación segura del candidato en el broker tras comprobar trabajos activos, y flujo real navegador → gateway privado → carga reanudable → importador JM → Stage → Companion local → MP4. Mantener `main` de Chema, Cloudflare preview y todos los proyectos intactos.