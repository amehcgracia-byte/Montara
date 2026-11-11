# MONTARA — Encaje de proyectos, material, recuperación y optimizaciones JM (11-11-2026)

**Tipo:** auditoría preliminar de lectura de código y disco. **No** se han fusionado ramas, desplegado servicios, ejecutado vídeos ni alterado el recorrido del editor. Se ampliará cuando Chema incorpore su actualización mayor a main.

## Decisiones de producto confirmadas por Fernando
- Landing -> Google -> editor auténtico JM (Stage, Push, Show); menos pasos, sin pantalla obligatoria de Mis proyectos ni botón técnico de abrir Engine.
- Selector contextual de proyecto dentro del mundo/editor; rescatar último y elegir entre varios, crear y renombrar.
- No sustituir la experiencia JM de arrastrar medios ni su procesamiento anticipado, concurrente y secundario.
- No inventar nuevos procesos: identificar y reaprovechar código actual; pedir decisión antes de cualquier modificación del flujo y de sistemas del PC.
- Mantener originales en local por defecto y comprobar gasto real de proyecto/medios/recuperación antes de fijar política de retención.
- Esperar gran actualización main de Chema antes de integrar funcionalmente; mientras tanto, auditoría/compatibilidad autónoma.

## Hallazgos código JM: rama fix/jm-native-video-save-project-recovery-20261110
- `web/montara.js`: drop handler usa `footageMemory.handlesFromDrop`, selector de Chrome/Edge `footageMemory.pick`, `addFiles` invoca `upload`, memoria y render progresivo de entradas. La actividad física y jobs activos evitan la desconexión por inactividad, pero un tab abierta sin interacción no mantiene VM despierta.
- `web/footage-memory.js`: IndexedDB `montara-footage`, guarda metadatos y handles de solo lectura del navegador; reabre tras permiso del usuario; caduca registros a los 14 días. En el actual código la lista se filtra por plataforma, no por owner UUID; exigir namespacing/migración segura si varios usuarios comparten navegador.
- `web/companion.js`: `http://127.0.0.1:47820`; comprobación `/health`, `/locate` con nombre, tamaño y SHA-256 de bordes de 64 KiB; solicita proxy y envía versión reducida, exportación local usando originales. Conserva mecanismo de consentimiento para originales en caso fallback; no convertir fallback en política general.
- `companion/companion.py` v0.6.10: indexa lugares conocidos localmente en `places.json`; búsquedas paralelas de raíces y control de presupuesto 180 s para Windows; proxy cache tiene `VIDEO_PROXY_RECIPE=3` para invalidación por receta. `/projects` abre selector nativo de carpeta y crea `Montara/<nombre>/montara-project.json` con fuentes (máximo 200), `/projects/<id>/save` guarda activos. Esta carpeta LOCAL no equivale a nuestro catálogo Owner SQLite.
- `web/montara.js` exportación Stage: exige coherencia entre `companion.local_video.engine` y `recipe.engine`; elige carpeta local cuando hace falta; preserva edición al recolocar destino después de reiniciar Companion; verifica hasta dos originales en paralelo mediante identidad/HEAD, no transfiere cuerpos completos simultáneamente; si el original no existe, aplica diagnóstico/fallback condicionado.
- `recovery.py`: endpoint `/montara/recovery/latest` busca entre los trabajos con contenido en `Projects` y `Sessions`, elige el más reciente por mtime. Existen múltiples directorios aunque la UX recupere el último.
- `app.py`: reabre `last_project_path` si está debajo de data_root y existe `project.json`; monta un engine Flask global por proceso. El aislamiento Owner→Engine requiere multiplexar a procesos/workspaces autorizados, no un proxy global `/api/v1/*`.
- `retention.py`: limpiador *opt-in* al configurar `MONTARA_RETENTION_USED_GB` (>0); preserva trabajo activo, proyectos/sesiones más recientes, pinned y modificados en última hora, controla locks y referencias; puede borrar trabajo antiguo si se habilita. **No habilitar sin política multiusuario y decisión del usuario.**
- El login dentro de Companion no parece requisito demostrado: propuesta pendiente de validar autorizar llamadas locales por proyecto y procedencia web; Origin y huella de bordes no bastan por sí solos como credenciales de propietario.
- Cuestiones abiertas: flujo Push/Show endpoint-by-endpoint, migración entre memoria navegador y varios proyectos, cancelaciones de trabajos en background, permanencia de proxies, equivalencia de recetas entre Engine JM y broker FER.

## Evidencia de almacenamiento real VM (11-11-2026; muestra, NO benchmark multiusuario)
- `df -h /`: volumen raíz ~96G, 56G usados, 41G disponibles (58%); cifra móvil, no reserva por proyecto.
- Checkout `montara-owner-beta` ~1.8G y `montara-personal-beta` ~1.8G; cada uno tiene `.venv` ~1.3G y `.git` 239-254M. **No atribuir esos tamaños a proyectos de usuario.**
- `montara-personal-beta-data` ~594M; de ellos `Cache/WhisperModels` ~464M; `Runtime/node_modules` ~109M; `Cache/proxies` ~8.3M; `Cache/audio` ~12M; `Projects` ~416K (un proyecto visible). Son ejemplos reales del entorno actual, no ratios de producción.
- E2E controlado `native-real-derived/data`: total ~14M; `Projects` ~1.3M; `Uploads` ~11M; `Cache` ~1.8M. Los vídeos sintéticos/de prueba no representan material real grande.
- La carpeta Owner de catálogo y el almacenamiento del equipo Windows no se han medido con precisión aquí. NO extrapolar tamaño por número de usuarios; diferenciar originales Windows, proxies Windows, proxies servidor, assets de exportación y metadatos persistentes.

## Diseño de encaje propuesto (sin implementar)
1. **Identidad canónica** `owner_id, project_uuid` del catálogo privado FER; **proyecto JM** interno/receta ligada a ese UUID y Engine privado; **proyecto Companion** es destino local separado, vinculable como referencia autorizada.
2. Al iniciar sesión entrar a selector de modo JM; en cada modo ofrecer control contextual con `Continuar último`, `Mis proyectos`, `Nuevo`, `Renombrar` sin interposición de dashboard. Validar detalles con Fernando.
3. Engine arranca al primer paso que requiera trabajo real, no al login ni con botón. Auditar todas las operaciones anticipadas para no retrasarlas.
4. Políticas de almacenamiento por capas y edades separadas: catálogo+receta persistentes; proxies reproducibles con límites; resultado final en PC; no suprimir materiales de proyectos activos o guardados sin consentimiento y posibilidad de regeneración.
5. Tests por owner/project de cada endpoint y negativo de acceso cruzado; dos identidades reales y viaje de punta a punta con Companion local. Todo ello PENDIENTE.

**Próxima puerta:** inventario exhaustivo de rutas Stage/Push/Show y cronograma de trabajos; definir contratos mínimos Owner↔JM con código de Chema actualizado en main y aprobación de Fernando para UX.