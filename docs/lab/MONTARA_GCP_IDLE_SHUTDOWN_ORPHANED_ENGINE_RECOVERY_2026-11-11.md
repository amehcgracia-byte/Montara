# Montara — Apagado automático y recuperación segura de Engine (11-11-2026)

## Evidencia comprobada en GCP
- VM `montara-test`, zona `europe-west3-a`, arrancada tras apagado a las 21:17:16 UTC del 11 de noviembre.
- El 11 de noviembre a las **21:11:17 UTC / 22:11:17 Madrid**, `montara-idle.service` registró `inactive 121 min (>=120), no SSH, engine or benchmark: poweroff` y ejecutó `systemctl poweroff`.
- Configuración activa: `montara-idle.timer` a los 20 minutos desde arranque y cada 20 minutos tras ejecución; `montara-idle.service` establece `MONTARA_IDLE_MINUTES=120` y `MONTARA_IDLE_GRACE_MINUTES=120`.
- Copias anteriores de 30 de octubre: inactividad de 60 minutos, chequeo cada 5 minutos, protección de arranque de 15 minutos. Por tanto **se amplió la ventana**, no se desactivó el apagado.
- Los archivos actuales se instalaron el **10 de noviembre a las 20:14:45 UTC / 21:14:45 Madrid** mediante sudo desde la cuenta de VM `fgardel00`. Los registros identifican la cuenta, no a la persona física; no permiten atribuirlo a Chema u otra persona.
- `gcloud compute instances describe` y `gcloud logging read` devolvieron `ACCESS_TOKEN_SCOPE_INSUFFICIENT` bajo la cuenta de servicio de la VM. No afirmar que se leyó Cloud Audit Logs; la evidencia del apagado procede del journal de systemd.
- Riesgo pendiente: el script de inactividad detecta ffmpeg/ffprobe/mixer, SSH y archivos `.last-activity` de rutas delimitadas, pero no comprueba explícitamente los workers privados I26 del broker como protección frente al apagado. Un worker residente sin ffmpeg ni marca actualizada puede quedar fuera de la señal de actividad.

## Engine already busy tras reiniciar: causa real
- El ledger `/var/lib/montara-i26-broker/jobs.sqlite3` retenía **tres jobs `orphaned`**, bloqueando la admisión de proyectos Owner. `systemctl show` de las unidades exactas informó `LoadState=not-found`, `ActiveState=inactive`, `MainPID=0`, `ControlGroup=` y los cgroups `/sys/fs/cgroup/system.slice/<unidad>.service` eran inexistentes.
- El broker implementa una reserva exclusiva por propietario y no reutiliza reservas huérfanas sin prueba de cgroup vacío. Así aparece `Engine already busy` aunque los procesos ya hayan desaparecido tras el apagado.
- Se comprobó la integridad de los identificadores de unidad frente a sus jobs y se ejecutó una prueba de solo lectura previa: **3/3 ausentes verificados**.
- Antes del cambio se creó una copia root-only mediante SQLite online backup en `/var/lib/montara-i26-broker/jobs.pre-verified-orphan-reclaim-20261111T213903Z.sqlite3` (modo 0600).
- Se liberaron **solo las tres reservas `orphaned`**, a través de `JobRecoveryLedger.confirm_stopped` y revalidando cada cgroup/unidad inmediatamente antes. No se ejecutó `systemctl stop` ni se reinició el broker; no se borraron proyectos, archivos, vídeos ni sonidos.
- Verificación final: `SELECT state,count(*)` devuelve `stopped=12`, cero reservas abiertas. Servicios broker, portal y túnel `active`. HTTPS `/healthz`=200, entrada anónima=401, OAuth Google start=302.

## Pendientes de arquitectura, NO corregidos por la limpieza
- El temporizador sigue habilitado con límite de 120 minutos. Evitar que la VM se apague si hay trabajo no terminado requiere un control del broker o una política de cierre seguro, equilibrando los créditos de GCP; **no se modificó esa configuración**.
- El interruptor ON/OFF antiguo sigue desplegado. En `fernando/integracion` existe una implementación probada de indicador read-only rojo/verde/ámbar con título del proyecto activo y acceso directo a ese Stage; **aún no desplegada en GCP**, porque requiere actualizar portal y broker root de forma coordinada.
- Verificar un único upload autenticado del mismo proyecto existente con Companion para cerrar el gate real, sin usar el interruptor ni cambiar de proyecto durante la prueba.

## Regla de operación
El estado `orphaned` no autoriza limpieza automática por tiempo. Liberar únicamente tras comprobación independiente de la unidad exacta y cgroup vacío. Nunca detener workers activos ni modificar `main` por una incidencia del Owner beta.