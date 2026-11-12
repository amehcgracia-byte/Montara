# MONTARA — Integración real del editor JM en proceso privado (I40–I44)

**11 de noviembre de 2026** · `fernando/integracion` · **PASS laboratorio, no desplegado ni fusionado en main.**

## Qué hemos probado de verdad, sin rehacer I19–I27

- **El editor auténtico de Chema** (`app.py`, `web/index.html`, `web/montara.js`, CSS y `web/companion.js`) arranca contra el Engine real pinneado `b5e48317ef85225f901adc69af8cc17aa8146880` desde una copia temporal de su rama `fix/jm-native-video-save-project-recovery-20261110`. No se usa nuestro estudio provisional I28 ni se altera `engine/`.
- `urano/private_jm_wsgi_socket.py` sirve la app JM real por **socket Unix WSGI**, sin puerto TCP ni listener público. El cliente local comprueba PID y UID de `SO_PEERCRED`, permisos del socket y una lista exacta de assets estáticos procedente del `web/` del build revisado. **7 rutas originales respondieron HTTP 200**: HTML (41.905 bytes), `montara.js`, `companion.js`, `montara.css`, `/api/v1/wizard/status`, `/api/v1/project` y `/montara/version`. 30 recursos estáticos reconocidos. No se admiten rutas arbitrarias por el cliente de prueba.
- **Problema de producto detectado y corregido en adaptador opt-in**: el JS JM hace `POST /wizard/projects/new` y luego `POST /wizard/draft` con `project_id:null`; esto **borra el Engine Owner UUID abierto y crea otra carpeta sin relación**. El middleware `urano/owner_first_stage_wizard.py`, instalado solo como adaptación en el worker aislado, conserva el UUID de un proyecto Stage **inicialmente vacío**, y transforma su primer draft al ID físico ya abierto. No cambia el código de Chema ni de Engine.
- `tests/urano_i44_real_jm_stage_unix_draft_lab.py` ejercita la **APP ORIGINAL** y su API real vía socket Unix: `GET /` 200; `POST /api/v1/wizard/projects/new` 200; `POST /api/v1/wizard/draft` 200 con **vídeo MP4 proxy sintético REAL generado por FFmpeg** de 320×180 y 2 s. Tras el draft: proyecto canónico Owner conservado, **cero carpetas JM extra**, segundo `new` rechazado HTTP **409** para no sobrescribir edición persistida. Segunda ejecución del laboratorio obtuvo **exit code 0**.
- `tests/test_urano_private_jm_wsgi_socket.py`: 6 casos PASS. `tests/test_urano_owner_first_stage_wizard.py`: 4 casos PASS. Se probaron además I38/I39 sobre el registro U13A existente con 16 tests PASS y pruebas físicas de Engine real. El flujo no exige ni crea un segundo registro durable de proyectos.

## Lo que NO se ha probado

**No está listo para la primera prueba de Fernando aún.** El ensayo usa una sesión/lab local, sin login Google de un navegador real, sin usuarios separados bajo `systemd DynamicUser` en este WSGI nuevo, sin transferencia de proxies desde Companion real, sin sincronización/cortes/renders finales ni MP4 de calidad original. Tampoco se ha expuesto la nueva app a una URL pública. Conservamos los servicios Owner, broker y Chema sin modificar.

**Importante sobre identidad de proyecto:** el JM legacy devuelve en `draft.project_id` la ruta absoluta del workspace privado; el adaptador I42 conserva esa semántica dentro de un worker aislado, pero **NO** debe filtrarse a clientes sin un adaptador de alias seguro. El cliente web actual usa ese valor como ID de recuperación; el diseño definitivo tiene que mantener el proyecto lógico Owner UUID, manejar alias backend y proteger todos los endpoints que aceptan rutas/IDs. Tampoco se debe hacer pasar a la app de Chema por un servidor global de múltiples usuarios.

## Ruta directa al producto, sin nuevos laboratorios de broker redundantes

1. Construir el **bundle JM completo e inmutable** desde `main` cuando Chema incorpore su desarrollo, o desde su rama candidata para beta cerrada explícitamente etiquetada; no sobrescribir JM/Engine en uso.
2. Conectar Owner Google session + catálogo + ledger/worker existentes con el socket HTTP privado del **JM completo** por owner; proteger las rutas estáticas, API, importación de **proxies verificados**, recuperación y descargas mediante identidad y generación. Diseñar transporte de respuesta multimedia/streaming que no pase bytes enormes por el broker root. Sin exposiciones globales `/api/v1/*` a 8101–8103.
3. Reutilizar el **E2E ya existente** `tests/e2e_native_stage.py` y Companion nativo, adaptándolo a Owner; no crear otro renderizador ni un segundo editor. Comparar `VIDEO_PROXY_RECIPE=3` de JM con el Companion Windows antes de instalar/desplegar.
4. Probar permisos reales entre dos propietarios, interrupción y reanudación, y Stage/Push/Show donde los endpoints difieren. **Fernando solo participa cuando el recorrido completo con Companion Windows tenga sentido**.

## Portabilidad

La lógica Owner/proyecto/receta es cloud-neutral. `private_jm_wsgi_socket.py` es un adaptador de ejecución Linux, sustituible; no presupone GCP, AWS, Azure, Oracle, Cloudflare ni un número fijo de vCPU. Las limitaciones de recursos del broker I26 son perfil experimental, no política universal del producto.
