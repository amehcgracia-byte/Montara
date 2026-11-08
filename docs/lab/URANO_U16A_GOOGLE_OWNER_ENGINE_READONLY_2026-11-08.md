# URANO U16A — Google owner → catálogo → workspace real de Engine, READ-ONLY (08-11-2026)

**Estado:** integración parcial, opt-in y limitada a laboratorio. **Ninguna cuenta Google ni sesión pública tiene autorización de edición, render, media o proxy Engine.** No desplegado.

## Cadena de ramas y reutilización

- Esta rama `fernando/urano-u16a-owner-engine-link-readonly` es una PR apilada sobre U15C **#126**, que depende de U15B **#125** y U15A **#124**. Ninguno se fusiona automáticamente a `main`.
- Se **reutiliza literalmente** `urano/engine_bindings.py` de U13A **#91** (no se inventa un segundo registro de carpetas). Más adelante se debe deduplicar #91/#U16A antes de integrar capas U13B–U13D.
- Dos módulos pequeños: `urano/http_engine_status.py` y registro opt-in en `urano/google_lab_app.py` únicamente cuando infraestructura aporta `engine_data_root`. No se registran rutas en `app.py` o servicios JM/FER.
- UI de laboratorio U15C muestra “Workspace vinculado (aún sin activar ni render)” cuando un proyecto auténtico de su propietario está vinculado. No expone `folder_name`, filesystem paths, `project.json`, datos de cámaras ni URLs de media.
- `EngineProjectRegistry.bind_trusted(owner, project_uuid, folder_name)` **solo backend/infrastructure**; no existe un endpoint HTTP que permita elegir rutas, provisionar carpetas ni registrar un worker.

## Qué significa exactamente el endpoint

`GET /urano/v1/projects/{project_uuid}/engine` verifica la cookie opaca U11, recupera exclusivamente el owner de la sesión, exige que exista el proyecto en U10 y la correspondencia owner→folder en el registro U13A, y comprueba nuevamente que el proyecto Engine no se ha convertido en symlink/traversal. Si está vinculado, devuelve solo:

```json
{"linked":true,"status":"linked_not_activated","engine_access":false,"render_access":false}
```

Sin sesión → 401; proyecto de otro usuario, inexistente o sin binding → mismo 404. POST/PUT/DELETE → 405; owner y path suministrados por navegador ignorados. Es comprobación de metadata **sin activar el Engine**: no arranca procesos, ni renderiza, ni emite credenciales/paths.

## Evidencia y límites

- CI `URANO U16A owner-checked Engine workspace link`: tests con dos propietarios sintéticos U15, dos UUID del catálogo y dos carpetas válidas de Engine con `project.json` de prueba; casos positivos, rechazo de acceso cruzado, no autenticado, manipulación de owner por headers/query, 405 para mutaciones, symlink, vínculo duplicado, persistencia y revocación de sesión. **Tests contratos PASS**.
- Se amplió `tests/e2e_urano_google_browser.py` para levantar un HTTPS Chromium temporal con OAuth simulado, crear ambas cuentas/proyectos, vincularlas solo desde backend a sus respectivas carpetas Engine y comprobar el texto en UI, estado 200 propio y 404 cruzado. **La CI con navegador debe completar su último run antes de declararse PASS**; fixtures son archivos falsos, no un render/ingest real.
- No se ha probado un proyecto Stage real del Mac ni sus originales; `project.json` falso solo acredita el contrato de referencia física del workspace, no la corrección de su contenido. U13C–U13D siguen teniendo tests privados apilados, pero no son la misma cosa que un Engine SaaS aislado real.
- **NO** introducir permisos globales de lectura o rutas `/api/v1/wizard/projects/open` sin un worker por propietario con autenticación, atribución y cancelación de trabajos, límites CPU/disk, y pruebas negativas sobre media/descargas/artefactos. Tres puertos HTTP no constituyen aislamiento de runtime.
- El usuario solo puede consultar estado de vínculo; snapshots de edición y persistencia de modificaciones manuales corresponden a una etapa coordinada con Chema.
- No se ha tocado `main`, `web/cut-editor.js`, Engine/Mixer/Companion, infraestructura Cloudflare ni servicios puertos 8101/8102/8103.

## Próximo bloque U16B

Adaptador privado dueño→worker real (revisar U13B/C/D), **sin rutas directas al Engine compartido**, tests de aislamiento de dos procesos/contenedores con dos propietarios, denegación de acceso a vídeos/exports ajenos, cancelación segura y persistencia. Integración gradual por PR, revisión de Chema antes de merge.
