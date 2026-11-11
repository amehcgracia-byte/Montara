# MONTARA — Decisiones UX de proyectos, activación del Engine y almacenamiento local

**Fecha:** 2026-11-11 · **Estado:** propuesta pendiente de aceptación de Fernando; **ningún cambio de comportamiento aplicado**. Rama `fernando/integracion`.

## Hallazgos verificados en el editor ORIGINAL de Chema

1. Stage recoge archivos en el paso Footage. Su JS hace la preparación de previews/proxies y la subida a endpoints existentes **antes** del botón Continuar; no afirmar que toda transferencia sucede después de Continuar.
2. En `web/montara.js`, al pulsar `#continueFootage`, `registerProject()` espera cargas pendientes, llama `/montara/branding`, solicita carpeta mediante `montaraCompanion.projectFolder()` si Companion está conectado y todavía no hay `state.localProject`, llama `/api/v1/wizard/projects/new`, después `/api/v1/wizard/draft` y guarda `state.projectId`. Se debe mantener este flujo con un adaptador que conserve Owner UUID, como ya se ha probado en I42–I44.
3. `web/companion.js` llama `POST http://127.0.0.1:47820/projects` y recibe un **ID de proyecto local** y la **carpeta local**. Son distintos del Owner UUID y del Engine legacy project path. Al terminar, `saveInProject()` y `startVideo()` reutilizan este ID local.
4. `companion/companion.py` ya soporta selector nativo Windows/Mac (`choose_folder`), crea `<carpeta elegida>/Montara/<nombre>`, escribe `montara-project.json`, asigna ID local de 16 caracteres, y persiste su mapeo en `HOME/projects.json` (HOME predeterminado `~/.montara-companion`). En `video_jobs.py` el MP4 final se guarda en la **carpeta de proyecto elegida** y los temporales de render en su subcarpeta `.montara-renders/<job>`. No duplicar esa funcionalidad.
5. `windows_support.py` usa `tkinter.filedialog.askdirectory` para pedir carpeta; la instalación y la carpeta de proyecto son cosas distintas. `companion/companion.py` utiliza `HOME/proxies` para cache de proxies. `~/.montara-companion` es el valor predeterminado de HOME en código JM; **no asumir** que el Companion actual Windows está instalado en AppData sin comprobar su paquete.
6. UI original `web/index.html`: cabecera/logo y botón `New project` a la derecha; selector Stage/Push/Show original en paso de modo. No hay un selector Owner contextual final ni menú de cuenta/suscripción integrado.

## Recomendación de arquitectura / experiencia

**A. Activación bajo demanda, NO botón 'Abrir Engine' visible como UX final.**
- Login Google, navegar y elegir proyecto existente, consultar catálogo y configuración: no abrir Engine.
- Arrastrar/seleccionar archivos: Companion local comprueba, hace fingerprint y genera proxy sin exigir Engine central; el servidor necesita recibir/guardar los proxies pequeños, pero debe poder hacerlo en una **puerta ligera de ingest** o arrancar Engine bajo demanda para esa operación. **La arquitectura actual del editor JM sube archivos al servidor mientras se arrastran**: no quitar ese requisito sin implementar una entrada segura alternativa. No introducir un segundo upload arbitrario.
- Pulsar **Continuar**: si aún no está en marcha y se necesita procesar, el coordinador abre automáticamente el Engine privado asociado al Owner UUID, espera ready y continúa el draft. Una importación previa puede necesitar activar antes el worker en la primera operación que requiera el Engine; activación idempotente por owner/proyecto/generación (no por cada request).
- Preview, edición, guardado y render: mantener el worker mientras se trabaja. Autoapagado/idle solo tras quiescencia y sin render ni upload en curso; reapertura automática al recuperar proyecto y al reanudar una tarea interrumpida. Nunca sustituir Engine mientras hay trabajo real.
- Push/Show y funciones de audio/mix pueden tener disparadores distintos; no asumir universalmente que 'Continuar' es el único inicio.

**B. Separar carpeta interna y carpeta del proyecto del usuario.**
- Companion/configuración, cache de proxies, logs y estados transitorios: espacio privado de la app (en Windows *preferiblemente* `%LOCALAPPDATA%/Montara/Companion`; macOS su carpeta de soporte, atendiendo a rutas antiguas durante migración). No usar esta carpeta oculta como destino principal del MP4.
- Datos visibles: una única raíz de proyectos elegida por el usuario, preferiblemente `Documentos/Montara` por defecto **configurable**. Cada proyecto: subcarpeta con metadatos, render/exports, originales **referenciados** (sin copiarlos automáticamente), y cachés internos claramente separadas o limpiables. Archivos originales permanecen donde estaban.
- Al crear el primer proyecto, presentar la ubicación sugerida y ofrecer **Cambiar carpeta**. Guardar preferencia para próximos proyectos; no abrir selector nativo en cada Continuar. En proyectos existentes, recordar/reconectar ubicación local por id y solo solicitarla si se pierde el vínculo.
- La carpeta por defecto, nombres/colisiones y migración de `projects.json` deben definirse antes de modificar Companion. **No borrar** instalaciones ni directorios antiguos.

**C. Navegación integrada al editor original (sin segundo dashboard).**
- Superior izquierda, junto a logo: `Mis proyectos ▾`, pequeño dropdown contextual con recientes del Owner, `Crear proyecto`, `Ver todos` si crece la lista, y estado breve (listo/en proceso/reconectando) sin botones técnicos Engine.
- Superior derecha: avatar de cuenta con `Perfil`, `Configuración`, `Suscripción y facturación` (último elemento deshabilitado o no mostrado hasta definir pagos; nunca simular compras).
- Cambiar proyecto: guardar o advertir ediciones sin persistir; nueva sesión Owner/proyecto; no cambiar silenciosamente de worker en trabajo activo. Activación transparente cuando la ruta requiere Engine.
- Mantener **los controles y los recorridos Stage, Push y Show de Chema**: aplicar integración como navegación/proyecto, no reemplazar UI ni extender I28.

## Decisiones para Fernando (aún no ejecutadas)

1. **Destino local por defecto**: `Documentos/Montara` con botón Cambiar al crear primer proyecto y posibilidad posterior de mover/reenlazar, vs pedir carpeta cada nuevo proyecto.
2. Menú **`Mis proyectos ▾`** arriba izquierda, avatar de cuenta arriba derecha, con crear/abrir sin pantalla obligatoria intermedia.
3. Después de `Continuar`, apertura automática Engine cuando corresponda, y antes únicamente si una operación de ingest/preview necesita procesamiento central. Nunca botones manuales de Engine salvo diagnóstico de beta.

## Restricciones técnicas / seguridad

- No mezclar el ID local de Companion (16 hex), UUID del catálogo Owner y ruta del proyecto JM; el mapeo solo lo debe decidir backend confiable y cada nivel debe autorizar su acceso.
- Los proxies tienen ruta de ingest previa a Continuar; toda propuesta 'Engine solo después de Continuar' exige probar preupload seguro **sin motor global compartido**.
- No subir originales por defecto; conservar contratos de versión del proxy/Engine, verificar la versión Windows instalada, no inventar equivalencia 0.6.2↔0.6.10.
- No crear nueva portada, un segundo editor, nuevo backend de medios o carpeta de vídeo oculta duplicada.
- Cloud-neutralidad del Owner/Engine y políticas de recursos configurables: GCP, Cloudflare, 4/8 vCPU no deben codificarse como requisitos funcionales.

## Próxima implementación tras decisión

Integrar selector propietario/UX sobre **los assets auténticos de Chema**, con configuración que permita probarlo en staging aislado; adaptar el contrato Companion `/projects` para reutilizar preferencia de directorio, reabrir y enlazar; implementar admisión Engine idempotente cuando se necesite para la primera ruta multimedia y conservar un intake separado si resulta necesario, con pruebas de dos propietarios y E2E JM existente.

**No desplegar ninguna decisión de UX ni modificar main/servicios de Chema antes de aprobación.**
