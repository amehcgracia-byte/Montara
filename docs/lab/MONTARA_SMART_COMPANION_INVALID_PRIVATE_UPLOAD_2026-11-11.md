# SMART — Diagnóstico de Invalid private upload (11-11-2026)

## Evidencia
En Windows, Companion conectado prepara proxies locales. El navegador mostró `Private media upload rejected: Invalid private upload`, un vídeo en transferencia y otros elementos `ERROR` con `Ready · lossless`. No equivale a entrega confirmada al Engine.

## Causa delimitada
- El texto `Invalid private upload` procede de la admisión Owner antes de reenviar esa petición al Engine.
- El importador original de Chema acepta MP3 sintético (HTTP 200, clase master).
- Se reprodujeron las formas de metadatos generadas por Chema y Companion para Slow_Playalong_in_A.mp3.flac y Bebop_LICK_tutorial.small.mp4; para tamaños modestos, ambas pasan el validador.
- Se detectó discrepancia: la beta anuncia 2048 MiB de proxy máximo, pero ciertos audios lossless sin flag de preview conservan un límite de 256 MiB. Sin tamaño exacto no se confirma que esa fuera la causa del archivo humano. No se ha relajado la seguridad.

## Corrección ya desplegada
- first_valid_upload_gate.py ofrece códigos limitados de rechazo: tipo de petición, nombre, extensión, tamaño, límite o fingerprint. Nunca revela nombres, rutas ni huellas del usuario.
- owner_original_jm_rpc.py responde con error estructurado y código específico, preservando HTTP 400 y todos los límites.
- Dos nuevas pruebas simulan metadatos de proxy de audio y vídeo y confirman respuesta diferenciada ante audio de 300 MiB.
- 20 pruebas Python PASS, 30 subpruebas PASS, dos pruebas omitidas. Beta health 200, guest 401, inicio OAuth 302; servicios activos.
- Copia reversible: ~/.config/montara-owner-beta/rollback-media-policy-reason-20261111/.

## Pendiente
La siguiente petición fallida podrá discriminar el motivo concreto. Si es exceso de tamaño, implementar transferencia lossless delimitada/atestada por Companion; si es otro metadato, corregir el contrato concreto. No subir originales de vídeo automáticamente ni borrar archivos. Los archivos de muestra de Chema no se exponen automáticamente en la beta Owner; no se afirma E2E Windows MP4.