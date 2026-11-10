# MONTARA — Puerta de aislamiento del Engine para la primera beta visible

**Fecha:** 2026-11-10. **Estado:** decisión y criterios de aceptación; **NO** despliegue ni certificación de aislamiento del host.

## Punto de partida comprobado

- I21 está incorporada en `fernando/integracion@6dfc1380` tras CI específica **success**. Una petición HTTP con OIDC sintético firmado abre el Engine real y registra el job como `running`; el cierre atestado marca `stopped` y deja el guard en `idle`.
- I15–I21 prueban montaje privado, sin red, PID namespace y límites cgroup; **el UID efectivo del host del Engine de laboratorio sigue siendo el UID 1006 del operador**. No son credenciales aisladas por tenant.
- `/etc/subuid` y `/etc/subgid` tienen rangos, pero `newuidmap` y `newgidmap` no se encontraron instalados. El intento de `DynamicUser=yes` mediante `systemd --user` terminó con status 217. LXD 5.21 está instalado, pero **no existe pool de almacenamiento ni configuración de red administrada**; usarlo implicaría decisiones administrativas, no una opción ya operativa.
- Hay evidencia de `sudo -n true` disponible en una comprobación anterior; **no** se ha certificado todavía el lanzamiento de un Engine con identidad host separada. No asumir que tener sudo justifica invocarlo desde la API.
- La última prueba SSH por Gateway falló por **timeout de conexión** a la VM. No se han ejecutado comandos host ni instalaciones desde ese momento.

## Decisión provisional para validar sobre la VM

**Candidato principal:** un *broker* mínimo de control con privilegios acotados, separado de la web/Owner, que arranque por trabajo un servicio transitorio con UID host **realmente distinto del UID de Owner y del de cualquier otro tenant**; rootless user/mount/net/PID namespaces, cgroup RAM/CPU/PIDs, carpeta de proyecto aislada, límites de temporales, `NoNewPrivileges`, `KillMode=control-group`, timeout corto, cancelación/reaping y estado durable por job. Debe negar todos los recursos no explícitamente asignados.

**Alternativa:** OCI rootless con mapeos UID subordinados correctamente configurados y política equivalente; comparar coste, seguridad, portabilidad y mantenimiento. No elegir LXD por la pertenencia del operador al grupo `lxd` ni configurar un storage pool en una VM compartida sin autorización. La implementación del broker de producción debe ser compatible con otras nubes y arquitecturas Linux.

**Control-plane:** las operaciones I13/I18/I19/I21 no recibirán UID, nombre de unidad, ruta física, PID, imagen de contenedor o proceso de un request HTTP; solo el owner verificado por sesión y project UUID. El broker deriva el entorno OS de sus propias tablas de confianza. Nunca se expone sudo, LXD, Docker socket o systemd D-Bus a la web.

## Criterios obligatorios de aceptación (go/no-go)

1. **Dos identidades host distintas**: A y B tienen UID host no privilegiados, distintos entre sí y del Owner; evidencia desde `/proc/<pid>/status`/systemd, mientras ambos Engines están en ejecución. Repetir con Engine real pinneado. No contar root *dentro* de userns como UID host diferente.
2. **Archivos y secretos**: A intenta abrir la carpeta sintética de B y archivos exclusivos del Owner; ambos accesos fallan. B tampoco puede acceder a A. El UID del servicio y permisos de mounts quedan registrados. Originales continúan en Companion.
3. **Admisión segura**: Google OIDC real para la beta de propietario, sesión HTTPS/Origin/CSRF, cross-owner 404. El backend solo emite `ready` después de que el Engine verifique su proyecto y el job durable figure `running`. Sin atestación => no `ready`.
4. **Cancelación/reinicio**: FFmpeg descendiente y Engine real en el mismo cgroup; cancelación o caída del controlador; broker reiniciado recupera unidades físicas a partir de identidad **durable** y generación I18, comprueba que el target correcto desapareció y solo entonces permite otro job. El UID/cgroup de otro trabajo no puede verse afectado por una respuesta vieja.
5. **Recursos y TTL**: RAM, CPU, TasksMax, disco temporal y duración por trabajo limitados/medidos; no hay contenedor permanente por cada usuario registrado. Un usuario inactivo no retiene un Engine eternamente.
6. **Repetibilidad + despliegue**: CI específica y pruebas físicas positivas/negativas, endpoints públicos preexistentes siguen respondiendo; no tocar `main`, ni servicios Chema 8101–8103. Probar solo en beta cerrada con *feature flag* inicialmente desactivada.

## Trabajo operativo inmediato

A. Recuperar acceso SSH de Gateway sin reiniciar ni reconfigurar firewall a ciegas. Revisar si la VM sigue en línea y si la IP/ACL de entrada han cambiado; usar el host key ya confiado al actualizar un endpoint, nunca sustituirlo sin verificación.

B. Con operador autorizado, probar **primero solo** el lanzamiento de un proceso sintético bajo otro UID host sin instalaciones ni unidades persistentes. Comprobar mapa real de UIDs, acceso denegado a fixture ajeno y teardown. Si requiere cambios administrativos, definirlos y validarlos antes.

C. Si lo anterior supera A/B, montar y medir **un** Engine real pinneado bajo el mismo mecanismo; unir su identidad física durable al registro I18/I21, incluidas pruebas adversariales. Comparar con OCI si falla el nivel de seguridad o el coste operativo.

D. Solamente después habilitar el botón «Abrir proyecto» en beta restringida, con autenticación Google real. **No** declarar completo el recorrido hasta Companion → Stage → MP4 local.

## Estado de la CI heredada

El E2E general Linux de I20 falla en el job `session` por test Companion C6 que espera `trusted_signed_receipt_origin`, ausente también en I19 anterior con archivos Companion idénticos. No corregir de forma lateral el Companion de Chema sin coordinarlo. I21 tiene CI propia success. La CI general de I21 seguía in_progress en la última comprobación.

> Esta nota documenta una frontera de seguridad aún no demostrada, **no un sandbox certificado**. `main` y la PR #189 continúan sin fusionar.
