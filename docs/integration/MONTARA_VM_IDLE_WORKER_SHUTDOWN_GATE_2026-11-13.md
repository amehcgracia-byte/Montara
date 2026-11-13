# VM: autoapagado de 120 minutos y workers privados H4
Fecha: 2026-11-13 · PR #202 · **protección aplicada, cierre de ciclo de vida pendiente**.

## Diagnóstico verificado en VM Google Cloud

- El temporizador real `montara-idle.timer` está `active`, ejecutándose aproximadamente cada 20 minutos. `/usr/local/bin/montara-idle-shutdown` exige al menos 120 min desde el arranque y 120 min de inactividad, y usa `systemctl poweroff`: apagado ordenado de Linux, **no** `poweroff -f` ni cierre forzado del proveedor.
- Hasta hoy protegía SSH establecido, `ffmpeg`/`ffprobe`, procesos del mixer, lock de benchmark y marcadores web; **no** incluía los jobs Engine privados `montara-i*-job-*.service`.
- Comprobado un worker activo H4 en unidad transient `montara-i24-job-...service`, de varias horas, sin hijos FFmpeg visibles y sin peticiones recientes tras generación/lectura del master. **No hay prueba suficiente de que esté huérfano**: puede ser una sesión de edición legítima persistente, por tanto no detenerlo ni reiniciarlo a la fuerza.
- Esa unidad usa `KillMode=control-group`, `TimeoutStopSec=3s`, `SendSIGKILL=yes`. Un apagado ordenado de la VM enviaría señales de cierre, pero tras 3s podría recurrir a SIGKILL; no se debe afirmar que el apagado por sí solo garantiza persistencia de trabajos.
- Broker `urano/private_broker_service.py` y `urano/restricted_systemd_broker.py` ya tienen `stop_owner` / `stop_verified`, y usan ledger de propietario, generación y cgroup. **Solo el broker autorizado** debe liberar una unidad; NO ejecutar `pkill`, ni un `systemctl stop` indiscriminado desde el watchdog.

## Salvaguarda inmediata instalada (2026-11-13)

- En rama `fernando/montara-idle-ssh-120m`, commit `577761a5be78877f1e2a2edff8ecb401c8c496ac`, `deploy/vm/idle_shutdown.sh` añade consulta fall-safe `systemctl --system list-units --type=service --state=active --no-legend --plain 'montara-i*-job-*.service'` **antes** de decidir apagar.
- Si hay unidades de propietario activas o no puede consultarse su estado, retorna KEEP. Si no hay, conserva las reglas originales de 120 minutos, conexión SSH, actividad web y renders.
- VM real actualizada en `/usr/local/bin/montara-idle-shutdown`; archivo anterior respaldado en `/usr/local/bin/montara-idle-shutdown.backup-20261113-worker-guard`.
- Pruebas PASS: `bash -n`, detección de la unidad transient activa, ejecución `MONTARA_IDLE_GRACE_MINUTES=0 MONTARA_IDLE_DRY_RUN=1` → `private owner worker active; broker must release it before shutdown: keep`; temporizador `montara-idle.timer` permanece activo.
- No se apagó VM, no se paró worker, no se tocaron proyectos, SQLite ni procesos de los usuarios.
- **Importante: este parche es de seguridad, no cierra el problema de coste:** mientras una sesión privada se mantenga persistente, la VM no se apagará sola. No declarar el autoapagado plenamente solucionado hasta validar la liberación segura de sesiones inactivas.

## Segundo cambio indispensable: ciclo de vida de workers, separado del watchdog

1. Contrato formal **activo vs inactivo** con reloj monotónico/persistido de actividad por worker (peticiones y jobs en curso), estado de proyecto/Owner, sin usar sólo el proceso en estado `sleeping` o que el navegador haya cerrado.
2. Antes de liberar una sesión inactiva, asegurar que no hay export ni editor mutando SQLite, que los archivos temporales están consistentes y que se conserva el proyecto. No matar por PID o por nombre.
3. Pasados 120 min de inactividad real y sin trabajos, solicitar cierre al broker con identidad/slot/generación verificados; efectuar `stop_verified`; esperar comprobación de cgroup vacío, confirmar ledger y entonces permitir autoapagado. Si el broker no confirma, fail closed y registrar diagnóstico.
4. Mejorar el margen de parada de workers (3 s insuficientes para escrituras limpias) mediante contrato de cierre: dejar de admitir nuevas solicitudes, cancelar/guardar en punto seguro, flush SQLite/journals, SIGTERM y timeout razonable, SIGKILL sólo último recurso. Validar crash y shutdown de VM. No modificar `TimeoutStopSec` sin pruebas del worker.
5. Si un usuario vuelve a la web, autoencender VM por flujo externo apropiado (Cloudflare/infra), reconectar sesión y proyecto sin que el proceso antiguo sea requisito; no prometer continuidad in-memory.
6. Añadir pruebas de no-apagado mientras render real, dos usuarios con uno activo, cero jobs con worker idle, caída broker, error consulta systemd, reinicio sin daño, apagado después de release. Sin este gate no integrar autoshutdown como finalizado a main.

## Integración main

- PR #202 añade la semántica 120 min/SSH; sumar la salvaguarda del commit anterior antes de revisarlo.
- Para el plan Owner/Stage de main, enlazar este documento desde `MONTARA_MAIN_INTEGRATION_HANDOFF_OWNER_COMPANION_2026-11-13.md` y tratar el cierre verificado como un **gate operativo para el despliegue con autoapagado**. No paralizar toda la integración de código si la operación está separada en flags, pero no declarar producción completa mientras faltan las pruebas de worker release.

## Rectificación solicitada por Fernando: prioridad de costes y criterios (13/11/2026)

Fernando confirmó que **no debe impedir el autoapagado un worker simplemente abierto**. El criterio operativo se mantiene **120 minutos desde la última actividad de web o SSH, evaluados cada 20 minutos**, con salvaguardas limitadas a operaciones reales FFmpeg/ffprobe/mixer/benchmark. Un proceso Owner inactivo **no** renueva la hora de actividad ni bloquea automáticamente el apagado. La terminal Windows Companion se ejecuta en su equipo y no crea una sesión SSH en la VM.

**Nueva política instalada y verificada:** commit `a0cd45a1c640973303f29f748fcce6b6832c1f87` de `deploy/vm/idle_shutdown.sh`: elimina el bloqueo indiscriminado `montara-i*-job-*.service`; mantiene SSH y trabajo FFmpeg; añade los marcadores de actividad `/var/lib/private/montara-owner-*/.last-activity` (datos de propiedad privada Owner/Engine) a los de `/home`. No inspecciona archivos de los usuarios ni los altera. Un worker vacío puede detenerse cuando systemd apague la VM. Cuando haya edición HTTP real, su marcador se considera actividad web. Este modo prima ahorro de créditos sobre persistencia indefinida de procesos in-memory.

Pruebas reales: `bash -n` PASS, instalador idempotente con copia en `/usr/local/bin/montara-idle-shutdown.backup-20261113-before-final-policy`; `sudo env MONTARA_IDLE_GRACE_MINUTES=0 MONTARA_IDLE_DRY_RUN=1 /usr/local/bin/montara-idle-shutdown` dio `SSH connection established: keep` (la auditoría se realizó mediante SSH), el timer continuó activo y se reconocieron 11 marcadores Owner. **No** se hizo poweroff real ni se validó aún la salida bajo 120 minutos sin conexión SSH (requiere prueba segura fuera de uso). La unidad transient tiene `KillMode=control-group` y `TimeoutStopSec=3s`: persiste una mejora diferida del apagado cooperativo de jobs para evitar pérdidas si alguna operación no usa FFmpeg y no ha registrado actividad reciente.

Aclaración: el bloqueo temporal indiscriminado descrito en secciones previas de este documento **fue reemplazado y ya no es la configuración activa**. Si se fusiona PR #202, utilizar HEAD actualizado que incluye la rectificación, no el commit intermedio `577761a`.

## Facturación: permisos insuficientes desde la VM

`gcloud beta billing projects describe` ejecutado desde la VM utiliza la cuenta de servicio de Compute Engine, **no** la identidad humana del titular. La API devolvió `ACCESS_TOKEN_SCOPE_INSUFFICIENT`; no se intentó alterar IAM ni scopes. Para conocer saldo real de créditos y costes, usar Console → Facturación → Créditos (saldo y vencimiento) y Facturación → Informes (filtrar proyecto `montara-pruebas-10292226`), o autorizar un acceso de solo lectura con permisos apropiados más adelante. No estimar un gasto real sin esos datos.
