# URANO U20 — Stage privado por sesión y descriptor seguro para Companion (08-11-2026)

## Objetivo acotado

Unir el control de sesiones OIDC de laboratorio + Engine privado U19 con **Ingest real de Stage**, y permitir obtener un **descriptor de cortes con owner autorizado y sin rutas locales**. Reutilizar código probado en U13/U16/U19. No desplegar en las VMs JM/FER, no modificar los originales en los Macs, no habilitar aún descarga de vídeo/recetas renderizables.

## Implementación

1. `urano/engine_worker_process.py` añade dos operaciones de stdio **fijas y sin parámetros de usuario**: `{"op":"ingest_start"}` y `{"op":"ingest_status"}`. Solo funcionan después de que el worker haya abierto un proyecto con owner autorizado; cada operación comprueba que el proyecto real del Engine continúa coincidiendo con el abierto. `ingest_start` invoca el endpoint real **`POST /api/v1/stages/ingest/run`** del Engine de ese worker; `ingest_status` consulta el estado a través de `GET /api/v1/project` y devuelve **solo un enumerado de estado**, nunca errores, medios ni rutas.
2. `urano/container_worker_bridge.py` conecta esos mensajes al guardia transaccional U13: `begin_job` pone el runtime en `busy`; solo un estado terminal válido permite `finish_job`. Respuesta no esperada, proceso muerto o Docker no verificable => **detener contenedor y cerrar en fail-closed**. La interrupción/cancelación es por ahora `POST /close` de U19 y destruye el contenedor: no hay recuperación automática garantizada del Ingest.
3. `urano/owner_runtime_controller.py` valida el UUID de proyecto desde el propietario de la sesión y que el runtime actualmente tenga ese proyecto activo; bloqueo por propietario (otro dueño no espera un bloqueo global). Nadie puede inventar el proyecto en el cuerpo de la solicitud.
4. `urano/http_owner_runtime.py` añade **`POST /urano/v1/runtime/projects/<id>/ingest`** (sesión+HTTPS+origen exacto+CSRF, cuerpo vacío) y **`GET /urano/v1/runtime/projects/<id>/ingest`**. JSON mínimo, sin paths, sin activar export y sin abrir proxy genérico a Engine.
5. `urano/companion_handoff.py` y `GET /urano/v1/runtime/projects/<id>/companion-handoff` crean un descriptor **`urano-local-handoff-descriptor-v1`** solo desde un esquema explícitamente permitido (`urano_edits_v1.cuts`: `source_slot` numérico, `start_ms` y `end_ms` enteros acotados). Rechaza rutas/keys adicionales, formatos antiguos arbitrarios, edición mal formada, cuts enormes. No expone `source_files`, `/Users`, `/workspace`, `notes` ni contenido raw del catálogo. El catálogo es propietario/UUID/revisión, protegidos por la cookie.
6. `urano/google_lab_app.py` ofrece el descriptor solo cuando el operador instala explícitamente el controlador privado del laboratorio. Sin controlador, no existe la API de trabajos. No se toca `app.py` habitual.

## Importante: el descriptor NO es todavía una receta renderizable

`render_ready=false`, `local_source_resolution_verified=false`, `requires_local_originals=true` son obligatorios: un `source_slot` **no** indica un nombre de fichero local. El Companion real no ha sido modificado para resolver esos slots, comprobar los hashes/huellas de los originales ni traducirlos al `render.json` actual. **No se debe pasar este descriptor directamente a FFmpeg ni publicitar como exportación web multiusuario resuelta**. Se conserva el render real ya verificado en U17 (#130), por separado.

En esta CI se generan muestras de vídeo/audio **dentro de carpetas Docker de laboratorio**, se registran en el Engine por un script de *infraestructura de test* y después dos usuarios autorizados disparan los Ingest. **Esto NO modela todavía el envío seguro de proxies desde dos Macs diferentes**. Para beta, las fuentes originales de vídeo deben permanecer en la CPU/almacenamiento cliente, no copiar la preparación del fixture al backend comercial.

## Pruebas y evidencia

- `tests/test_urano_stage_worker_protocol.py`: worker stdio con Engine fake, operaciones y errores sin ruta.
- `tests/test_urano_stage_handoff_http.py`: descriptores seguros con revisiones, rechazo de owner extranjero, cookie revocada, rutas explícitas/maliciosas y payload HTTP prohibido.
- `tests/urano_u20_prepare_stage_inputs.py`: genera únicamente fixtures FFmpeg efímeros de 7 s y los registra dentro de cada workspace del runner Docker.
- `tests/test_urano_owner_runtime_docker.py` se amplía con un ensayo de **dos Engine reales Docker**, sesión de dos propietarios verificados mediante JWT Google ficticios firmados, activación desde Flask HTTP, envío paralelo de Ingest, polling hasta `done`, extracción de descriptor con owner y rechazo de acceso ajeno, y cierre aislado.
- Workflow `.github/workflows/urano-u20-stage-handoff.yml` con contratos rápidos y Engine real Docker (submódulos Engine/Mixer fijados en el commit, imagen local por SHA256). **No marcar PASS hasta confirmar CI del commit definitivo**.

## Faltan antes de cerrar la arquitectura híbrida

- Provisión autenticada/limitada de **proxies y metadata** desde Companion cliente hacia servidor, sin fichero original completo.
- Confirmación de fuentes/hashes originales por Companion y traducción del descriptor versionado al **formato render real** del Mac; después export MP4 con CPU local para dos clientes físicos contra un servidor HTTPS aislado.
- Autorización segura de descargar resultados/recetas, idempotencia/cancelación/recuperación, fallos de trabajos y cuotas/disco de una beta.
- Configuración real de Google OIDC y revisión de despliegue, consolidar la pila de PR históricas con Chema sin duplicar archivos U13/U16.

## Límites operativos

No modificar ni desplegar a `main`, VM GCP, puertos **8101 JM / 8102 FER / 8103 potencial**, Cloudflare, Engine/Mixer/Companion de producción o originales de usuarios. Se mantiene una PR **draft** dependiente de U19 **#134** y en el futuro integrar selectivamente con el banco híbrido U18 **#133**. No crear alias/infraestructura productiva sin revisión.
