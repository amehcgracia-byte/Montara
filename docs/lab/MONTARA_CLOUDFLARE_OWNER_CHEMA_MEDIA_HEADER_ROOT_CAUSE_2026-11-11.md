# MONTARA — Auditoría real GitHub × Cloudflare × GCP: cabeceras multimedia
**Fecha:** 2026-11-11. **Repositorio:** `amehcgracia-byte/Montara`. **Trabajo exclusivo:** `fernando/integracion`. **Estado:** Worker Cloudflare corregido en producción privada; E2E Windows pendiente.

## 1. Diagnóstico demostrado en el sistema real
- Se inspeccionaron `main@5d65ec3`, nuestra rama, el bundle JM desplegado, `owner_browser_bridge.js`, `owner_original_jm_rpc.py`, el Worker `montara-owner` recuperado mediante la API Cloudflare y la configuración del túnel.
- Cloudflare tenía túnel `montara-owner-fg` healthy y binding `OWNER_PRIVATE_API` de tipo `vpc_service`, con backend GCP privado.
- **Causa crítica confirmada:** el Worker público de Cloudflare mantenía la lista `REQUEST_HEADERS` sin `x-zucker-filename`, `upload-offset` ni `x-montara-engine-generation`. En GCP, Chema usa `X-Zucker-Filename` para POST directo; `web/resumable-upload.js` usa `Upload-Offset` en PUT; Owner exige `X-Montara-Engine-Generation` en transferencias fragmentadas, status y recuperación.
- Al eliminar `X-Zucker-Filename` del tramo navegador→Cloudflare→GCP, el validador no podía leer el nombre aunque fuese válido en Windows, explicando el rechazo de audio y otros fallos de identidad/generación. La ausencia de `Upload-Offset` hacía fallar la carga por partes. El fallo no requería actualizar FFmpeg ni Companion.
- Los anteriores tests directos Flask/Engine omitían ese tramo; por eso daban PASS pero no detectaban el fallo público.

## 2. Cambio mínimo y reversible en Cloudflare
- Respaldo exacto del módulo desplegado antes del cambio: `infra/cloudflare/montara-owner-worker-2026-11-10-original.mjs`.
- Nuevo código bajo control de versiones: `infra/cloudflare/montara-owner-worker.mjs`.
- Única modificación lógica: añadir al `REQUEST_HEADERS` cerrado `x-zucker-filename`, `upload-offset`, `x-montara-engine-generation` y `range`. Se conservaron comprobación de host/origen, denegación de rutas globales, ninguna identidad inyectada, VPC privado y headers originales.
- Despliegue mediante `PUT /accounts/{account_id}/workers/scripts/montara-owner/content`, que reemplaza solo contenido, **no configuración ni bindings**. Respuesta `success=true`, deployment `d0f9eea705404c6ea8f2ebc94b2c441e`.
- Verificación posterior: las cuatro cabeceras siguen presentes en el script efectivo de Cloudflare; el binding `OWNER_PRIVATE_API` sigue siendo `vpc_service` y el túnel permanece healthy.

## 3. Pruebas cruzadas
- Nuevo `tests/test_cloudflare_owner_media_headers.cjs` compara fuentes de Chema (`web/montara.js`, `web/resumable-upload.js`) y puente Owner con allowlist del Worker. Ejercita el Worker en Node con VPC simulado y confirma transferencia de cabeceras, cuerpo, POST/PUT, rechazo de cabeceras no permitidas, URLs globales y orígenes ajenos.
- **5 pruebas Node PASS** en conjunto con regresiones de Owner, resumable y aislamiento de pestañas.
- Comprobación pública desde GCP después del despliegue: `/healthz` 200; entrada sin sesión 401; inicio de Google OAuth 302; ruta global `/api/v1/wizard/upload` 404; assets Owner sin sesión 401; POST multimedia sin cookie 401. Portal, túnel y broker activos.
- La prueba pública anterior no utiliza sesión ni archivos personales. **No se afirma PASS de subida autenticada desde Windows** hasta completar el siguiente gate. No se han reiniciado Engine/Mixer/Companion ni tocado proyectos.

## 4. Comparación real del proyecto
- `main@5d65ec3` está incluido en `fernando/integracion`: **0 commits detrás**, alrededor de 408 ahead (mayoría de laboratorio Owner). El editor web principal procede de Chema; nuestra rama conserva sus originales y añade una capa aislada `urano/` + empaquetado Companion Windows. La integración no debe consistir en enviar los ~408 commits íntegros a main.
- Runtime todavía usa JM `14cce126` y Engine `b867b3c`, mientras `main` fija Engine `92c7bc3`. No equiparar git merge con runtime actualizado.
- El inventario de APIs Chema revela rutas Stage ya admitidas (wizard upload/status/prepare/start, preview/review, edit timeline/shot, resumable, proyecto), pero también operaciones dinámicas específicas de Music/Show y algunos assets de medios que siguen fuera del piloto Owner; no abrir rutas generales ni afirmar Push/Show/Music E2E.

## 5. Control siguiente
Probar una sola transferencia autenticada de audio o proxy de vídeo desde Windows, mirando admisión, bytes por fragmento, finalización, persistencia y clasificación. Si falla, registrar HTTP status/operación/motivo sin nombre/ruta ni bytes originales. Después probar sincronización Stage y exportación local mediante Companion. Mantener actualización lossless de 2 GiB como candidato separado (no activo) y no apagar workers activos para forzar aceptación.

**Política:** adaptar Owner al contrato nativo de Chema, con integración mínima y pruebas que crucen la frontera Cloudflare–portal–Engine; nunca sustituir el editor de Chema por otra UI.