# SMART — Integración funcional: selección estable y cierre explícito del worker (11-11-2026)

## Petición de producto
Fernando confirmó la navegación básica y pidió **recuperar exactamente la animación de Home de Chema**, dejar de invertir ciclos en estética, y avanzar la integración funcional de Stage, motor privado y Companion, conservando los resultados documentados previamente. Detectó que un proyecto ya abierto seleccionado desde Home hacía un no-op y que el 409 BusyOwner no explicaba cómo cerrar el Engine anterior.

## Cambios funcionales
- **Selección estable de Stage**: `owner_mode_entry.py` guarda el UUID elegido en `sessionStorage` solo como preferencia de navegación; lo coteja obligatoriamente con los IDs devueltos por `GET /urano/v1/editor/projects?mode=stage` para la sesión Google. No confía en storage como permiso. Video → Stage prefiere ese UUID válido sobre el más reciente cronológicamente. Si no existe, usa el más reciente del catálogo autenticado.
- **Selección de proyecto actual desde Home**: `owner_project_picker.js` ya no cierra silenciosamente el modal si su UUID coincide y Chema muestra `#home` o `#mode`; recarga el mismo editor con `?start=stage` para entrar a Footage, preservando datos persistentes del proyecto privado. Si ya está editando, el modal se cierra sin reiniciar el trabajo.
- **Cambio denegado**: un intento de abrir otro proyecto que obtiene HTTP 409 mantiene el modal abierto con texto inglés explícito y **no sustituye el UUID preferido**. El usuario debe regresar a su proyecto activo antes de cerrar.
- **Cierre temporal de beta**: en el menú Account del editor aparece `Close idle Engine`, usando exclusivamente el UUID de la ruta privada actual. Antes del cierre exige (1) `POST /projects/<UUID>/ensure` con Origin y CSRF, (2) generación positiva verificada y vinculada al UUID, (3) `GET /urano/v1/media/<UUID>/wizard/status` autenticado con generación y CSRF, (4) `status == idle`, (5) confirmación humana. Solo después emite el `POST /projects/<UUID>/close` previamente implementado y probado en URANO I27, que valida sesión, origen, pertenencia del proyecto y verifica la parada por unidad/cgroup. Si devuelve `stopped`, vuelve a entrada Owner. Sin botones de cierre automático entre proyectos.
- **Límite de seguridad:** esta verificación de inactividad es del frontend y no es atómica con la orden de parada; otro proceso/tab podría comenzar una tarea entre ambas llamadas. Por tanto, el botón es de **diagnóstico temporal para beta**, requiere confirmación y no debe convertirse en el cierre definitivo del producto ni considerarse rotación automática segura. Para producción se necesita comprobación atómica dentro del controlador/broker antes de detener un worker. No se ha cerrado ningún worker real en esta intervención.

## Animación original de Chema
Se conserva el bloque `#home .intro-name`, su SVG y CSS `intro-assemble` e `intro-bars` del bundle original de Chema `14cce126...`. Se invoca en Home y no se repite el medio clip al lanzar Stage. No se ha generado otro vídeo, animación ni recurso gráfico.

## Reutilización de pruebas existentes
Se releyeron los documentos `MONTARA_SMART_HITO_3_COMPANION_WINDOWS_BETA_COMPLETA_2026-11-11.md` y `MONTARA_SMART_HITO_3_COMPANION_WINDOWS_HANDoFF_2026-11-11.md`. No se repitió el render real ya validado en GitHub Actions Windows runner #43038849790: Engine `b867b3c`, 1920×1080, 4.218.608 bytes de MP4, fuentes locales sin subir originales. Tampoco se repitió el ensayo GCP de Stage, receta real de 4 segmentos y máster WAV de ~1.15 MB servido por gateway propietario.

Se ejecutaron regresiones de navegación, RPC, broker y Companion: **62 tests Python, 64 subpruebas y 11 tests Node PASS**; revisión de sintaxis JS PASS. Adicionalmente se repasaron 26 tests Python + 9 subpruebas de propietario, admisión, broker y autoactivación; y 13 tests Node de recuperación de guardado/instalador (solapados con algunos del conjunto final; no sumar como pruebas únicas). Nuevas selecciones verifican que un rechazo 409 nunca altera la preferencia Stage. No se afirma PASS humano de cierre ni MP4 desde navegador.

## Versiones y compatibilidad
La rama `fernando/integracion` ya incluye `main@5d65ec3`; el runtime VM de Owner **aún no** cambia del conjunto probado JM `14cce126` + Engine `b867b3c` + Mixer `f15ff91`. El nuevo Engine de main `92c7bc3` está **39 commits adelante de b867b3c**, con cambios en `server/api.py`, `server/edit_timeline.py`, `core/stages/edit.py`, `core/stages/export.py`, cámaras y revisión. La ruta de revisión admite nuevos parámetros opcionales por toma; los tests reales del Engine nuevo deben superar el contrato Owner+Companion antes de desplazar el bundle y paquete Windows verificados. No confundir fusión Git con actualización runtime. El editor main apenas difiere del bundle en varias actualizaciones UI, por ejemplo botón multimedia de progreso, pero su submódulo Engine sí es materialmente diferente.

## Despliegue y vuelta atrás
Solo cambiados `urano/owner_mode_entry.py` y `urano/owner_project_picker.js` en GCP SMART tras copiar a `~/.config/montara-owner-beta/rollback-selected-project-engine-close-20261111/`. Health pública 200, entry visitante 401, picker visitante 401, Google OAuth start 302; broker y túnel activos. No se tocó `main`, Engine root, servicios de Chema, base de datos ni archivos de los usuarios.

## Próximo bloqueo humano real
Un único recorrido en Windows: abrir beta, elegir Stage activo, confirmar que abrirlo desde Home sí entra en Footage, y con Companion encendido probar **proxies locales de uno o dos clips pequeños**, receta/render y **MP4 final guardado en carpeta elegida**. Si antes se necesita cambiar de proyecto, abrir el Stage activo, comprobar que no hay trabajo en curso y usar Account → Close idle Engine; esa acción es voluntaria y aún no tiene aceptación humana. Recoger únicamente fase y error concreto. No exigir reinstalar Companion ni subir originales por defecto.

## Pendientes productivos
1. End-to-end humano Stage → Companion → MP4 desde navegador autenticado.
2. Estado de trabajo/revisión por proyecto y cierre/switch de Engine comprobados en broker **de forma atómica**, sin carreras; quitar la función de beta cuando exista.
3. Actualizar bundle de runtime con los 39 commits del Engine de main mediante matriz de compatibilidad y pruebas reversibles, preservando el binario local verificado hasta prueba final.
4. PRs selectivos pequeños hacia `main` (no fusionar experimentos históricos en masa).
