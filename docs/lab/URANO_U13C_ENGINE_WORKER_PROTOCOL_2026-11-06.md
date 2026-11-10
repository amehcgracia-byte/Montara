# URANO U13C — protocolo de apertura de proyectos en proceso Engine separado

**Fecha:** 2026-11-06 · **Estado:** primera implementación de worker, PR **draft**, sin desplegar ni exponer URL pública.

## Qué hemos verificado en código real del Engine

En `zucker_videos/server/api.py`, `create_app(project_path=None, dev=False)` crea estado independiente por instancia Flask. Existen `POST /api/v1/wizard/projects/open` y `GET /api/v1/project`. La primera ruta carga un proyecto mediante `load_project(folder)`, reconstruye inputs y devuelve estado; el snapshot de `GET /api/v1/project` es el contenido de `project.json` y **no expone el campo de ruta de carpeta**. La identidad de carpeta realmente activa debe comprobarse dentro del proceso con `app.config['ZUCKER_STATE'].project.folder`. No alterar `engine/` en Montara.

## Qué implementa este paso

- `urano/engine_worker_process.py` ejecutable como `python -m urano.engine_worker_process --engine-dir <submódulo> --data-root <directorio privado>`. Requiere una carpeta Engine de pruebas propia. Inicializa `server.api.create_app()` **en el proceso worker**; nunca modifica el estado global del proceso padre.
- Protocolo interno JSON de una línea por mensaje, por STDIN/STDOUT: `open` con **solo nombre relativo de carpeta** y `stop`. Verifica nombre, ubicación bajo `Projects/`, `project.json` y ausencia de symlinks antes de invocar el Engine. Tras abrir, comprueba respuesta 200 y carpeta activa interna, no se limita a confiar en HTTP 200. Envía resultado normalizado sin volcar rutas privadas.
- Test con FakeEngine ejercita la ruta **real** `/api/v1/wizard/projects/open`, rechazo de rutas ajenas/symlinks/comandos desconocidos, errores Engine, verificación de ruta cargada y ausencia de submódulo.
- Workflow CI ejecuta el contrato U13C y todas las pruebas heredadas U10–U13B, más comprobación sintáctica de JS.

## Límites cruciales

**Esto no es todavía un runtime comercial ni un sandbox de seguridad.** El script permite crear una instancia Engine en un proceso aparte si lo arranca explícitamente un operador sobre un directorio de laboratorio, pero:

1. **No existe todavía un coordinador confiable que arranque y mantenga** un proceso dedicado por propietario, gestione permisos UID/cgroups o contenedores, aislamiento de archivos/secretos, límites de CPU/RAM, limpieza de procesos ni recuperación tras caídas. Múltiples procesos Python bajo un mismo usuario NO garantizan confidencialidad.
2. El protocolo STDIN/STDOUT **no es una API de navegador** y no debe exponerse directamente; el futuro coordinador debe resolver `owner_id` verificado y proyecto por U10/U13A, obtener reserva U13B y enviar únicamente el nombre resuelto internamente. Evitar que el navegador envíe `folder` o `owner_id` a una ruta pública.
3. **La suite de U13C utiliza FakeEngine** y carpetas inventadas; aún falta ensayo end-to-end del submódulo Engine real con un proyecto sintético, inspección humana de apertura/edición/exportación, dos procesos aislados y fallo de worker.
4. Hay además una prueba CI adicional `tests/urano_real_engine_smoke.py` con un **proceso separado y el submódulo Engine realmente fijado en el repositorio**, que abre dos proyectos sintéticos en secuencia y rechaza `../untrusted`. **Pendiente confirmar su resultado en GitHub Actions**; no contiene edición/render.
5. No hay enlace desde U12b a Engine, ni relink de medios, ni editor funcional, ni validación de fronteras de upload/preview/export/companion.
6. No usar para almacenar medios personales ni cuentas reales. No poner contraseñas de demostración previsibles o usuarios vacíos; provisionar identidades temporales únicas, acceso con HTTPS y protección privada cuando existan gates.
7. Issue #34 pendiente de respuesta de IA de Chema sobre navegabilidad histórica. Chema solicita acceso a una URL de beta; **no hay URL de U13C para compartir todavía**. La URL existente de Cloudflare es una copia HTML estática, no la beta de proyectos.

## Próximos gates

- U13D: coordinador subprocess con ciclo de vida, aislamiento real por UID/contenedor, interrupciones/reconciliación de reservas U13B y timeouts, más pruebas de dos identidades.
- U13E: apertura Engine con proyecto sintético, confirmar receta/medios, interrupción durante render, edición/exportación y pruebas de aislamiento. Solo después considerar beta privada para Chema y guía de uso.
- No merge ni despliegue sobre main, FER/JM, Vercel o Cloudflare; revisión de seguridad y E2E real antes de decir «ya puedes probarlo».

**Pila de PR:** #86 U10 → #88 U11 → #89 U12 → #90 U12b → #91 U13A → #92 U13B → U13C (esta entrega).
