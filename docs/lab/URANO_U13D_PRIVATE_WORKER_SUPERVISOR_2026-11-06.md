# URANO U13D — supervisor privado de procesos (laboratorio)

**Fecha:** 2026-11-06. **Estado:** código aislado sin despliegue. No es aislamiento multiusuario apto para Internet.

## Objetivo

Completar la pieza operativa entre la reserva U13B y el proceso Engine U13C: supervisor confiable por usuario/runtime que arranca un subprocess, espera su saludo, abre un proyecto previamente autorizado, verifica respuesta del worker y cierra el proceso si falla o expira.

## Qué implementa

- `urano/private_worker_supervisor.py`: `PrivateWorkerSupervisor` gestiona un subprocess Linux/POSIX con `start_new_session=True`, protocolo JSON privado por stdin/stdout, plazos estrictos para saludo y apertura, respuestas con límite de tamaño y verificación del PID de saludo.
- `open_project(project_id)` exige relación U13A y reserva U13B mediante `guard.request_open`; únicamente envía nombre de carpeta resuelto en backend. Devuelve ticket **después** del acuse verificado. Si el worker rechaza, muere o se queda colgado, lo termina antes de marcar disponibilidad del slot.
- `RuntimeActivationGuard.invalidate_after_worker_exit(...)` conserva seguridad ante caídas: invalida estado listo/ocupado/anterior después de que el supervisor haya comprobado terminación y avanza la generación. Por tanto el proyecto de un worker muerto no puede aparecer falsamente como preparado. Estados antiguos no recuperan autoridad.
- Para Linux, terminación del grupo de procesos con SIGTERM y SIGKILL si vence el plazo. **El proceso y grupo son sólo un límite operativo**; no aportan permisos diferentes ni aislamiento de filesystem/red.
- Siete pruebas usando subprocess real con worker sintético: dos proyectos, fallo, crash, timeout, intento cross-owner, trabajo busy y invalidación tras cierre. `tests/test_urano_private_supervisor.py`; workflow U13D corre pruebas acumuladas U10–U13D.

## Limitaciones de seguridad y operación

1. **No es todavía aislamiento fuerte multiusuario**. El supervisor ejecuta por defecto el subprocess bajo la misma identidad Unix que el padre. Para habilitar beta externa se exige asignación real de UID/container distinto, montajes privados, recursos limitados, red restringida, separación efectiva de directorios y secretos, más pruebas de escalada.
2. El worker U13C actualmente incluye proceso Engine real en un test de humo CI sin vídeo, pero U13D usa un worker sintético para probar failover. No confundir esos dos ensayos con un E2E real de edición.
3. No hay API web pública, sesión auth lista producción, integración con U12b, descubrimiento de medios, relink, cola CPU/GPU, heartbeats, reconciliación automática después de caída del supervisor ni reciclaje de workers al cambiar de identidad.
4. No gestionar trabajos reales en paralelo ni exportar todavía. El supervisor puede terminar su grupo, pero el Engine necesita confirmar cómo se detienen procesos externos de FFmpeg antes de levantar bloqueo. El siguiente paso requiere test específico de procesos huérfanos, señales, interrupción en render y reconciliación duradera.
5. El estado persistente U13B puede quedar `switching` o `busy` si cae el propio supervisor sin invalidar. La recuperación exige evidencia fiable de que el worker anterior ya no puede seguir escribiendo, nunca liberar por simple TTL.
6. Hay que revisar efectos del Engine sobre `last_project_path` y rutas globales; confinar almacenamiento antes de pruebas con dos identidades.
7. Chema ha solicitado una URL privada; **aún no hay beta de URANO lista** y ninguna contraseña se ha establecido. Cuando se aprueben controles, crear un usuario de prueba separado y clave larga aleatoria. Nunca cuenta vacía ni credenciales escritas en GitHub.

## Gates siguientes

- Verificar CI de U13D y ver si el E2E general Linux ha terminado (sus resultados son independientes).
- U13D2: arranque con UID/container y filesystem realmente aislados, auditables, prevención de fuga de medios y rutas de resultados. Integrar guard/worker de confianza sin exponer propietario/ruta aportados por usuario.
- U13E: flujo real de proyecto antiguo → worker → lectura/edición/export y reentrada; prueba con dos usuarios y medios sintéticos.
- Beta privada, solo tras revisión de seguridad y despliegue aislado autorizado; no `main` ni Vercel ni servicios actuales.

**PRs apiladas:** #86 U10 → #88 U11 → #89 U12 → #90 U12b → #91 U13A → #92 U13B → #93 U13C → U13D. Revisar cada PR antes de cualquier merge.
