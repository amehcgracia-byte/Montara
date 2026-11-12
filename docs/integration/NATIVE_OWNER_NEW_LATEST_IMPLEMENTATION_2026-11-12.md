# Owner nativo — Bloque New/Latest preparado (12-11-2026)

**Rama de implementación:** `fernando/chema-native-owner` (nacida de `main` de Chema).
**Estado:** módulos de backend y pruebas aprobados **sin conectar todavía al worker ni desplegar**. El navegador, Cloudflare, Google OAuth y la beta actual no han cambiado.

## Decisión arquitectónica

**Un espacio privado de ejecución por usuario** (identificador UUID de Owner/broker) y **múltiples trabajos nativos de Chema dentro de ese espacio**. No equivale a un selector multiproyecto: no cambia la web ni muestra un catálogo.

El backend de Chema ya implementa:
- `POST /api/v1/wizard/projects/new`: reinicia la selección actual, sin borrar carpetas de trabajos guardados.
- `POST /api/v1/wizard/draft`: crea un nuevo `Projects/<nombre>.zuckervid` cuando `project_id` es nulo; si ya existe, exige que esté abierto.
- `GET /montara/recovery/latest`: consulta nativamente los trabajos reales de `Projects/` y `Sessions/`, por fecha guardada; no mostrar borradores vacíos.
- `POST /api/v1/wizard/projects/open`: abre una carpeta de proyecto existente.
Estas operaciones deben conservarse, en vez de sustituirlas por las restricciones `OwnerFirstStageWizard` del piloto.

## Código producido

| Archivo | Responsabilidad | Condición |
| --- | --- | --- |
| `urano/native_owner_project_scope.py` | Comprobar que un proyecto Chema abierto pertenece directamente al directorio privado de su Owner | No autentica ni crea carpetas |
| `urano/native_owner_workspace_gate.py` | Puerta WSGI con validación estricta de proyectos y medios para New, Open, Draft, Prepare, Start, Status y Delete; delega a los handlers originales de Chema sin modificarlos. Deja que `recovery.py` funcione dentro del `data_root` aislado | **Solo se puede montar detrás de Owner/broker autenticado**. No se permiten accesos a archivos de otros usuarios |
| `urano/native_owner_workspace_registry.py` | Asociación única y persistente `owner_id → workspace_id` en la misma SQLite de Owner; reserva atómica, adecuada para entradas concurrentes | **No selecciona automáticamente proyectos preexistentes**; exige `bind_existing` tras inspección de propiedad/worker/filesystem en la capa de orquestación |
| `tests/test_native_owner_project_scope.py` | Permisos de archivos, escapes y enlaces simbólicos | Aislado |
| `tests/test_native_owner_workspace_gate.py` | Contrato HTTP WSGI y el **`recovery.py` real de Chema** | La creación real del Engine está simulada por rutas Flask de prueba; todavía no E2E |
| `tests/test_native_owner_workspace_registry.py` | Concurrencia (24 altas de un usuario), migración explícita, no pérdida de proyectos y control cruzado de propietarios | SQLite real en temp |

**Resultado inicial:** 25 pruebas Python y 15 subpruebas completadas correctamente (pendiente repetir tras el ajuste menor a Status vacío). No cambia `web/` de `main`.

## Frontera que falta conectar antes de probar en Chrome

En la beta anterior `private_broker_worker.py` creaba un proyecto UUID vacío dentro de `data_root/Projects`, y `full_jm_worker.py` lo abría obligatoriamente al iniciar el worker. `OwnerFirstStageWizard` interceptaba New/Draft forzando ese mismo UUID; era adecuado para validar la admisión aislada, pero provoca `Create a new private Montara project first` después de usar el proyecto.

**Cambio preciso pendiente:** el UUID que llega desde el broker debe interpretarse como el **workspace privado estable**, no como cada proyecto audiovisual. El worker debe abrir el último trabajo válido que indique el propio backend Chema, sin crear otro proyecto de editor arbitrario, y montar la puerta de rutas NativeOwnerWorkspaceGate *detrás del socket/broker ya autenticado*. El servidor se encargará de `owner_id` y de conservar el `data_root` original, incluso si se crean nuevas ediciones.

Antes de aplicar:
1. Revisar cómo se selecciona `StateDirectory` y cómo se conecta a `Owner` con una única reserva exclusiva, sin alterar DynamicUser/cgroup. **No relajar el aislamiento**.
2. Para usuarios con múltiples UUID antiguos, mantener todas las carpetas y solicitar selección administrativa segura; jamás marcar el proyecto «latest» por la posición del catálogo ni migrar archivos sin verificación física.
3. Ampliar el contrato de rutas de Stage y audio para las fases que faltan. El WSGI gate no sustituye la revisión del gateway HTTP exterior, sus métodos, CSRF o cuotas.
4. Validar con el **editor original**, primero en un worker aislado, después en Chrome por Cloudflare y finalmente dos identidades reales. Solo entonces plantear PR para revisión de Chema en `main`.

## Cambios explícitamente NO realizados

No se ha modificado `main`, la web HTML/JS original, Cloudflare, el proyecto Pages, el Tunnel, GCP, el servicio del broker ni un worker activo. No se han eliminado ni migrado proyectos, ni instalado librerías, ni añadido un servidor permanente. La beta existente sigue accesible como referencia de recuperación.
