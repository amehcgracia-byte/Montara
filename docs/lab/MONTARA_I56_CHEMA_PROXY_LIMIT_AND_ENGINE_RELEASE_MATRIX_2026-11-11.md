# Montara I55–I56 — Proxies largos y matriz ORIGINAL de Chema

**Fecha:** 2026-11-11 · **Rama:** `fernando/integracion` · **Estado:** PASS en Oracle; NO desplegado; NO fusionado.

## Cambio de producto: proxy largo sin segundo uploader

El uploader reanudable ORIGINAL de Chema (`resumable_upload.py`) ya tenía soporte de subidas fragmentadas de 4–16 MiB y límites de 30 GiB en entorno local. Su token de modo remoto recortaba TODAS las subidas a 256 MiB. A ~1,45 Mb/s, un proxy Companion de 1 hora puede superar ~650 MiB: el corte remoto antiguo impediría la beta con grabaciones largas.

Se implementa `urano/jm_private_proxy_overlay.py`: **adaptación de compilación** sobre la versión revisada de `resumable_upload.py`, sin tocar jamás los originales de Chema ni submódulos. Exige cinco anclas exactas; si JM cambia el archivo, falla en vez de aplicar un parche ambiguo. El resultado va a un **bundle JM nuevo e inmutable**. El operador puede fijar el límite por fichero de proxy entre 256 y 4096 MiB (recomendación inicial 2048 MiB); el modo sin token y el fallback de originales conservan su política previa. Solo proxies Companion `video_preview=true` o previews de audio específicas ganan capacidad; subir un original de 650 MiB sigue rechazado en el modo remoto. Ninguna operación lee el original local por defecto.

`urano/first_valid_upload_gate.py` y `urano/owner_original_jm_rpc.py` aceptan el límite configurable **solo para previews** y devuelven `max_original_file_bytes`=256 MiB. `urano/full_jm_worker.py` **rechaza arrancar** con un límite mayor si el bundle no tiene el overlay revisado. El root broker puede recibir `--private-proxy-limit-mib` (por defecto 256), únicamente desde configuración del operador; lo transmite al worker. `create_owner_api(...private_preview_limit_mib=...)` debe fijarse al mismo valor. No hay adaptación automática del entorno desplegado.

El uploader ORIGINAL conserva sus comprobaciones de huella, reintentos, bloqueo concurrente, espacio libre, reservas y 128 MiB de margen; no se ha creado otro servicio ni un sistema de subida distinto. **Pendiente**: cuota agregada por cuenta y limpieza de ficheros completados; ampliar un límite por fichero no prueba capacidad multiusuario sostenida.

## Matriz de versiones: incompatibilidad no ignorada

Inspección de la rama JM `fix/jm-native-video-save-project-recovery-20261110` en GitHub, SHA exacto **`14cce126137a0ef30a987351ff35b750f54473bd`**:

| Componente | Revisión |
| --- | --- |
| Editor original JM | `14cce126137a0ef30a987351ff35b750f54473bd` |
| Submódulo Engine de JM | `b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b` |
| Submódulo Mixer de JM | `f15ff91c1b80fc5f157099dcd9451d958d553ae6` |
| Bundle Engine de nuestros laboratorios I37–I54 | `b5e48317ef85225f901adc69af8cc17aa8146880` |

Comparación del Engine `b5e4831..b867b3c`: **19 commits posteriores**, cambios en `core/stages/export.py`, `core/review_previews.py`, `server/api.py`, `server/edit_timeline.py` y pruebas de recuperación. Los laboratorios con Engine antiguo siguen siendo útiles para las fronteras de confianza y flujo inicial, pero **NO** prueban el render de JM de la revisión nueva.

`urano/jm_bundle_manifest.py` genera un manifiesto **determinista** directamente desde Git, con las revisiones editor/Engine/Mixer, límite por proxy y SHA-256 del uploader adaptado. El broker root en modo `--jm-bundle` exige `montara-jm-bundle.json`, comprueba que el directorio `jm-<SHA>` y el directorio `engine-<SHA>` coincidan exactamente con el manifiesto, que el perfil de proxy coincida con las banderas del operador y que el código del uploader instalado tenga el hash revisado. **Si no coincide: rechaza ejecutar.** La beta actual no usa `--jm-bundle` y sigue intacta.

Manifiesto confirmado en Oracle con el código real de Chema:

```json
{
  "schema": 1,
  "editor_commit": "14cce126137a0ef30a987351ff35b750f54473bd",
  "engine_commit": "b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b",
  "mixer_commit": "f15ff91c1b80fc5f157099dcd9451d958d553ae6",
  "private_proxy_limit_mib": 2048,
  "patched_resumable_sha256": "264285f26a3106b7be55cb2d46b2769f7c3f9cbad7d484c5ddd7301c6c36073d"
}
```

## Evidencias y estado de conexiones

Durante este bloque, la VM GCP `ssh montara` no respondió (timeout al IP estática). No se reinició ni modificó. Oracle por Desktop Commander Remote sí estaba operativo y podía obtener `fernando/integracion` del GitHub privado. Se extrajo una copia temporal aislada en `/tmp/montara-i55-oracle.GATevW` y se creó venv temporal de pruebas con Flask.

- **4/4 PASS**: fuente original inmutable, overlay compilable, fail-closed ante código cambiado y límites.
- **2/2 PASS**: `resumable_upload.py` auténtico de Chema con Flask real, proxy lógico declarado de **650 MiB** aceptado (`HTTP 201`), misma cifra como original rechazada (`HTTP 413`), reanudación idempotente y cancelación. **Solo metadata**, no se escribieron 650 MiB ni se corrió un render.
- **2/2 PASS**: matrices reales editor/Engine/Mixer vía gitlinks y rechazo explícito de usar Engine `b5e..` con editor `14cce..`.
- **17/17 PASS**: regresiones Flask separadas (I51 Owner RPC 7, gate primera subida 6, perfil recursos 4), más la suite overlay (4).
- Archivo `.github/workflows/fer-i55-original-jm-long-proxy.yml` preparado para CI con fuente JM SHA pinneada. **No consta ejecución de GitHub Actions**.

## Próximos pasos imprescindibles para la prueba humana

1. Construir en laboratorio un bundle JM **editor `14cce...` + Engine `b867b3c...` + Mixer `f15ff...`**, con uploader revisado y manifiesto exacto; verificar compatibilidad real de Engine y Mixer, no solo la identidad de commits. No alterar servicios ni paquetes existentes.
2. Con GCP accesible, validar en `systemd DynamicUser` la instancia privada, `StateDirectory` persistente, sockets 0600/0700, generación, autenticación y recuperación; no tocar el broker root activo sin aprobar un despliegue separado.
3. Completar las rutas Stage del navegador original y la autenticación por pestaña: previews, audio, análisis, sincronización, edición, render/range y recuperación, sin proxy genérico a la instancia compartida.
4. Integrar el Companion Windows nativo con la versión JM y ejecutar `tests/e2e_native_stage.py` adaptado a proyecto Owner: originales locales → proxies → edición → MP4 local. Las rutas Push/Show se amplían después del primer Stage completo.
5. Antes del uso multiusuario real, implementar y probar cuotas de disco por owner y limpieza de temporales sin borrar datos de proyectos.

**No afirmar que el flujo E2E está listo**: hay avances importantes de integración y pruebas HTTP, pero no un render final Owner+Companion, ni aislamiento systemd nuevo, ni un instalador Windows integrado.

## Política anti-duplicación

Los contratos U13/I19–I27 ya existen. No volver a fabricar aperturas de Engine o pruebas de sockets si no hay riesgo funcional nuevo. Conservar `main` y las ramas de Chema intactas. Toda la nueva política es sustituible por archivo de configuración/manifest, independiente de Cloudflare, Google Cloud, proveedor Linux, cantidad de vCPU y ruta predeterminada de proyectos.
