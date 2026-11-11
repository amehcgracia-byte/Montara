# MONTARA SMART — Auditoría consolidada de navegación Owner/Stage (11-11-2026)

## Motivo
Fernando detectó fallos cruzados: navegación Home/Video/Stage inconsistente, selector Stage projects situado a la derecha incluso al volver a Music/Video, vídeos antiguos sugeridos en Latest, pantalla técnica Opening your edit y HTTP 409 entre proyectos.

## Hallazgos
1. Dos capas de navegación convivían: portada Owner y HTML original de Chema. El picker fijaba su contexto por URL en lugar de seguir la pantalla real.
2. Chema conserva archivos en IndexedDB usando un nombre global por navegador y filtra solo por plataforma. Owner requiere aislamiento adicional por UUID de proyecto.
3. La recuperación original con resume=footage muestra Making y Opening your edit antes de consultar el servidor. Ante recuperación fallida puede volver a Home.
4. El picker y el adaptador de Chema rotaban CSRF de forma independiente dentro de la misma pestaña. Un refresh podía invalidar el otro.
5. El broker limita a un worker activo por propietario. Al seleccionar otro proyecto devuelve HTTP 409. No es una pérdida de red.

## Correcciones implementadas en fernando/integracion
- owner_project_picker.js: Projects junto al logo, Account y Sign out a la derecha, contexto reactivo All/Video/Music/Stage al cambiar pantallas.
- original_jm_owner_assets.py: el logo del editor Owner lleva a la selección de modalidades mediante el evento original de Chema, sin repetir Home.
- owner_mode_entry.py: clic en logo restaura All projects; Logout en inglés; CSRF compartido.
- owner_browser_bridge.js: base local de vídeos aislada por UUID Owner sin borrar registros anteriores; token CSRF compartido con el selector; logo original cubre la transición técnica de recuperación y desaparece cuando llega a una pantalla o un error.
- owner_project_picker.css: el piloto oculta Resume latest global y el botón duplicado New project del header, sin eliminar sus nodos del HTML original.
- owner_project_picker.js: antes de entrar a un proyecto anterior solicita autorización/admisión. Ante 409 mantiene el panel abierto con mensaje legible y no detiene ni cambia otro Engine.
- Editor web original de Chema, Engine/Mixer, main y originales Windows intactos.

## Validación
16 pruebas Python y 14 subpruebas PASS; 5 tests de puente JavaScript PASS; compilación Python y sintaxis JS PASS. Salud pública 200, guest entry 401, guest picker 401, inicio OAuth 302, servicios portal/túnel/broker activos. Reversión: ~/.config/montara-owner-beta/rollback-owner-nav-audit-20261111/.

Se preparó un ensayo aislado con navegador real en scripts/owner_contextual_browser_smoke.py, pero Chromium de VM no arrancó por ausencia de libcups.so.2. No se instalaron paquetes en el servidor. No afirmar PASS de navegador humano.

## Límites y siguientes pasos
- El cambio de proyecto sigue bloqueado cuando ya existe worker activo y no se ha verificado su inactividad; no liberar a ciegas.
- La recuperación real de proyectos con vídeos, Companion y MP4 local no tiene aún PASS humano.
- Push, Show y Music siguen sin integración funcional en Owner.
- La nueva base local por proyecto no migra ni borra automáticamente la anterior; conservar la información previa.
- El acceso Account es provisional, no un perfil completo.

Siguiente prueba humana integrada: All/Video/Back, Stage a Footage, regreso mediante logo a All projects, selector contextual centrado, archivos antiguos no mezclados y aviso de otro Engine sin navegar. Corregir solo los fallos observados antes de iniciar cambio seguro entre proyectos y MP4 local.
