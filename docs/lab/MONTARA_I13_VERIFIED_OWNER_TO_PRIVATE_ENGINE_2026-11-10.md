# I13 — Propietario autenticado → proyecto propio → ejecutor Engine privado

**Fecha:** 2026-11-10. **Origen:** `fernando/integracion@326187f`. **Alcance:** primer contrato de admisión a un Engine por propietario, aislado de infraestructura, sin activar un Engine compartido ni exponerlo en la beta pública. **NO fusionar en main aún**.

## Evidencia de usuario (física)

El 10-11-2026 el propietario confirmó que entró desde la portada Cloudflare Pages, completó Google OAuth y regresó a «Mis proyectos», donde aparecía su proyecto creado el día anterior. Esto **certifica la sesión y persistencia del catálogo**, pero no una sesión de editor Engine ni un export local desde Companion.

## Unión implementada

`urano/owner_engine_gateway.py` contiene la frontera de control `OwnerEngineGateway` y la ruta opcional `POST /urano/v1/projects/<uuid>/open`:

1. El navegador presenta sesión HTTP segura ya creada por OIDC, token CSRF y encabezado Origin exacto, **sin cuerpo de petición**.
2. El servidor obtiene `owner_id` de su cookie verificada; no acepta `owner_id`, `runtime_id`, carpeta, PID ni imagen de contenedor proporcionados por navegador.
3. `ProjectCatalog.get(owner,project)` exige propiedad. Un UUID extranjero se rechaza con el mismo 404 que uno inexistente **antes de consultar al proveedor**.
4. El `PrivateExecutor` inyectado por infraestructura confiable resuelve el runtime **exclusivo** del propietario, o devuelve ausencia -> HTTP 503. No hay fallback al Engine global ni se crea un worker con el UID del propio servidor web.
5. `RuntimeActivationGuard.request_open` resuelve el binding interno a la carpeta privada existente, reserva un cambio serializado y asigna generación; el adaptador abre y **verifica realmente** el proyecto dentro de un runtime ya aislado.
6. Solo tras éxito verificado devuelve `{project_id, state:"ready", generation}`; **no incluye ruta de disco, ID de runtime, UID o detalles de proveedor**. Si falla, obliga a abortar y reaprovechar solo tras reaping efectivo; si fallara el teardown, queda `switching` y se deniegan nuevas activaciones. El resultado seguro de ausencia/fallo es 503, y la contención es 409.

`create_owner_api()` recibe la dependencia opcional `engine_gateway`, garantiza que comparte el mismo archivo de catálogo SQLite y solo registra la ruta cuando existe. Por defecto **la ruta no existe**. `create_private_owner_beta()` (el servicio real C8 en 8115) continúa rechazando inyección de `runtime_controller`, y **no** pasa gateway, por lo que no ha cambiado el recorrido real ni se han creado runtimes en GCP.

**La abstracción `PrivateExecutor` no es una sandbox.** Es un protocolo de admisión para un provisionador confiable que debe instalar aislamiento OS con límites verificables. El test doble-Alice/Bob usa un ejecutor sintético, no una prueba del kernel.

## Compatibilidad y neutralidad

- La API trabaja exclusivamente con UUID de proyecto, generación y estado; no conoce GCP, Cloudflare, Vercel, Docker, systemd, arquitectura de CPU ni GPU.
- Cuando se seleccione el primer ejecutor real, debe implementar `runtime_for_owner`, `open_verified` y `abort` con aislamiento propio: OCI (contenedor temporal con imagen compartida y mounts específicos), systemd+UID Linux distinto o alternativa aprobada. No montar `/var/run/docker.sock` ni aceptar una ruta desde HTTP.
- Una sesión activa de Google **no reserva un Engine**: el worker solo se provisiona cuando el usuario abre un proyecto, y se cierra por inactividad o fin de trabajo. Los originales siguen en Companion Windows/macOS; la VM solo recibe proxies/recetas/temporales previstos.
- Para UI futura, abrir un proyecto debe devolver una sesión de trabajo *real* y reanudable, o un estado explícito de indisponibilidad. No mostrar «Editor listo» mientras el ejecutor esté inactivo.

## Tests y puertas restantes

`tests/test_owner_engine_gateway.py`: Google OIDC sintético **criptográficamente verificado** usando el proveedor fake existente, dos cuentas, 404 de acceso cruzado, header Owner falso ignorado, CSRF, Origin, rechazo de cuerpo, ausencia de worker, abort correcto, abort fallido que mantiene reserva segura, y la beta C8 real sin la ruta. No representa imagen/FFmpeg de producción. Workflow FER I13 específico; suite focal existente C1/C8/U13.

**Pendiente para uso real:** aprovisionador aislado en VM (sin tocar los servicios 8101–8103), registro de cada workspace con permisos estrictos, comprobación negativa UID/contenedor por propietario, recuperación tras caída con generaciones/fencing, un recorrido Engine real con proyecto ya existente, Companion conectado y MP4 local. Medición en el mismo servidor real antes de 2+ usuarios.

## Propuesta de integración con Chema

Conservar `main` sin cambios. El PR #189 sigue en borrador hasta el recorrido proyecto → Engine → Companion probado. Evitar que la incorporación de contratos fuerce instalación de Docker o rutas de GCP en `main`.
