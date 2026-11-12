# Montara · Integración nativa Owner: decisión de arquitectura
**12 noviembre 2026 · Rama limpia:** `fernando/chema-native-owner` (base `main` de Chema). **Estado:** diseño respaldado por código y primera comprobación de límites de rutas; **no está desplegado**.

## Producto que entregaremos

Mantener **íntegra la experiencia nativa** de Chema: marca/intro → Music o Video → Stage/Push/Show → Footage, New, recuperación del último trabajo, Mixer, edición y exportación. Añadir solo autenticación Owner, autorización privada, broker/worker y Companion, de forma invisible salvo cuando sea imprescindible. No selector de todos los proyectos, segundo dashboard, interruptor manual de Engine ni otro recorrido de prueba.

La rama `fernando/integracion` sigue siendo la **biblioteca de funcionalidades y pruebas realizadas**, no una rama que se fusionará entera. No editar `web/` de Chema si se puede resolver en un adaptador externo mínimo.

## Decisión crucial: workspace privado ≠ proyecto de Chema

- **Un propietario autenticado** → **un contexto privado de ejecución** con un `data_root` accesible únicamente desde su worker autorizado. El broker/CSRF/autorización existentes deciden si puede acceder y permiten máximo un worker activo por propietario en esta beta.
- **Dentro del contexto privado**, Chema gestiona de manera nativa sus trabajos en `Projects/` y `Sessions/`. Un **New** legítimo puede crear otra edición sin destruir la anterior; **Latest** invoca el comportamiento **original** de `recovery.py`, que elige el último trabajo no vacío por fecha de modificación, vídeo o sesión musical.
- El UUID que Owner necesita para mantener la reserva exclusiva **no tiene por qué representar cada nueva edición nativa**. En el diseño objetivo representa un **workspace privado estable**. No mezclamos los dos identificadores. Esta separación es una **propuesta por validar en el contrato completo de broker, almacenamiento y frontend** antes de activarla.
- Acciones originales `POST /api/v1/wizard/projects/new`, `POST /wizard/draft` y recuperación se dejan funcionar **dentro del worker privado**, con validaciones de rutas multimedia y de proyectos que no admiten accesos fuera del `data_root`. Nunca relajar la autorización por usuario por quitar el selector.

## Evidencia revisada

1. Código de Chema `engine/server/api.py`: `wizard/projects/new` hace `wizard.reset` y elimina la selección actual; `wizard/draft` crea un proyecto nuevo cuando no recibe `project_id`. `app.py` registra el sistema nativo de recuperación.
2. `recovery.py` en el paquete real elige el proyecto o sesión con actividad guardada más reciente, excluyendo borradores vacíos. `tests/test_recovery.py` ya cubre el contrato; no construir otra versión basada en la fecha del catálogo Owner.
3. Nuestra `owner_first_stage_wizard.py` bloquea New cuando el proyecto preabierto ya contiene datos y fija todas las operaciones al mismo UUID. Ese diseño fue apropiado como piloto seguro, pero es incompatible con el ciclo nativo completo.
4. Nuestro `owner_mode_entry.py`, picker y CSS repiten navegación y ocultan `newVideo` y `sessionResume`. No deben entrar en el producto final.
5. Código existente I16/I19/I24/I26/I27 y pruebas de dos usuarios U13D2A se reutilizarán **según su nivel real de validación**. La experiencia de Companion Windows y el render final siguen necesitando comprobación humana.

## Primera pieza de código, sin tocar la beta

`urano/native_owner_project_scope.py` comprueba que un proyecto nativo abierto desde el worker es hijo directo de su `data_root/Projects`, con metadatos válidos, sin enlaces simbólicos ni rutas externas. No crea proyectos, no arranca Engine y **no sustituye la autenticación del broker**. `tests/test_native_owner_project_scope.py` comprueba varios proyectos del mismo propietario, rechazo de proyecto de otro usuario, escapes, links y metadatos corruptos.

## Bloque siguiente que necesitamos cerrar antes de desplegar

1. Seleccionar **sin ambigüedad** el workspace existente al iniciar sesión: preferir un worker autenticado y verificado; sin worker, seleccionar el workspace estable previamente asociado al propietario. Para usuarios con varias carpetas Owner antiguas, diseñar **migración no destructiva** antes de elegir automáticamente; conservarlas todas.
2. Acotar rutas nativas New/Latest y archivos de entrada con la misma autorización Owner existente. Distinguir un nuevo proyecto **dentro** del mismo workspace del cambio entre workspaces distintos: el primero no necesita reiniciar el worker.
3. Validar el recorrido nativo con un usuario y un segundo usuario **real** antes de pedir fusión a `main`. La primera prueba humana será un solo recorrido Stage real y su recuperación, no un catálogo de tests sintéticos.

**Reglas de operación:** no tocar `main`, la beta GCP ni un worker activo; no trasladar el catálogo multiproyecto visual; no borrar ni migrar datos automáticamente; no prometer MP4 ni dos renders concurrentes sin E2E físico. La rama limpia no es un segundo producto: es el destino definitivo para PR pequeñas hacia Chema.
