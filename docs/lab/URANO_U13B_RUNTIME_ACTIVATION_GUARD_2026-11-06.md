# URANO U13B — Reserva segura de activación del Engine por propietario

**Fecha:** 2026-11-06 · **Estado:** contrato de seguridad aislado, PR DRAFT, sin conectar al runtime ni desplegar.

## Riesgo que aborda

El Engine actual mantiene un único proyecto activo dentro de un proceso. Abrir en ese mismo proceso el proyecto B mientras el proyecto A está renderizando —o dejar que otro usuario cambie el proyecto activo— arriesgaría cruces de estado/medios y resultados. El catálogo U10 y el binding U13A **no** lo solucionaban por sí mismos.

## Implementación de laboratorio

- `urano/runtime_activation.py`: estado persistente en SQLite para **un slot de runtime asignado a un único propietario**. El alta `register_trusted(owner_id)` es exclusivamente de infraestructura; no se expone al navegador.
- Un proyecto solo puede solicitar activación con `request_open` si pertenece al propietario y su carpeta Engine está vinculada y sigue siendo válida en U13A. Se devuelve un `ActivationTicket` con generación y ruta interna; **no se envía al cliente ni abre realmente el Engine**.
- Transiciones: `idle` → `switching` (reserva) → `ready` (solo tras acuse de apertura real por un futuro worker de confianza) → `busy` (trabajo) → `ready`. Un fallo de apertura pasa a `idle`. Cambiar mientras `switching` o `busy` lanza `RuntimeBusy`; finalizar un trabajo de otra generación lanza `StaleActivation`.
- SQLite `BEGIN IMMEDIATE` serializa cambios de estado entre instancias de guardia. Cada propietario tiene slot distinto (restricciones SQL únicas).
- Pruebas `tests/test_urano_runtime_activation.py`: seis escenarios con dos usuarios/proyectos anteriores, bloqueo durante jobs, rechazo de cruces entre cuentas, confirmaciones atrasadas, rollback lógico y persistencia interinstancia.
- CI específico ejecuta todos los tests URANO (U10–U13B) y comprobación JS del dashboard.

## Límites — NO es todavía apertura real

**Este contrato NO crea procesos, sandbox ni contenedores, NO invoca `/wizard/projects/open`, NO inicia ni detiene renders, NO autoriza rutas de media/archivo, NO verifica PID ni corazón del worker y NO habilita multiusuario real.** Los tests son simulaciones de transición de estado con carpetas de prueba.

### Qué se exige antes de conectar Engine

1. **Aislar realmente un proceso Engine por usuario o proyecto** (u otro mecanismo con equivalencia de seguridad probada), directorios privados, tokens/rutas y límites de CPU/memoria, no solo una fila de DB.
2. Un *worker* de confianza debe validar `ActivationTicket` contra slot/generación actual, abrir el proyecto **dentro de su propio proceso**, comprobar estado, reconocer apertura y únicamente entonces aceptar trabajos. Si la apertura falla o muere el worker, bloquear nuevos trabajos hasta limpiar el proceso y reconciliar estado.
3. El estado `switching` o `busy` sobrevivirá al reinicio y fallará cerrado; **no existe todavía mecanismo de recuperación ante caída o heartbeat**. No marcar manualmente `ready` si no se ha comprobado el proyecto activo.
4. Control de propiedad de medios, cargas, jobs, resultados y rutas backend y Companion, más pruebas E2E con dos cuentas y render real. Las sesiones U12 no están listas para usuarios externos.
5. Consultar la coordinación [issue #34](https://github.com/amehcgracia-byte/Montara/issues/34#issuecomment-6682639303) sobre selector de proyectos históricos antes de fusionar interfaz o migración de proyectos.
6. PR apiladas: U10 #86 → U11 #88 → U12 #89 → U12b #90 → U13A #91 → U13B. No integrar toda la pila sin revisión, actualización de bases y pruebas.

**Guardarraíles:** sin cambios en main, Vercel, Cloudflare ni VM FER/JM. No tocar los pines de Engine/Mixer. No borrar ni relinkar originales.
