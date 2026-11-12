# I17 — Controlador independiente: cancelación real del Engine y FFmpeg

**Fecha:** 2026-11-10. **Resultado:** laboratorio de cancelación real del Engine y FFmpeg **PASS**, conservando fallo y límites históricos. **Producción aún NO certificada**. Ninguna instalación Docker, unidad persistente, modificación a main, despliegue Owner, permisos del sistema o acceso a archivos reales.

## Problema descubierto

En I16 se había demostrado la apertura real del Engine en `systemd-run --user --pipe --wait` con PID namespace, pero al ejecutar un `systemctl --user stop` bloqueante desde el mismo flujo de trabajo el controlador no lograba certificar el final. Se comprobó que **el PID 1 del espacio de procesos no manejaba SIGTERM**; la unidad entraba en `stop-sigterm`, esperaba su timeout por defecto y la llamada `stop` acababa agotando su plazo. La primera prueba de `stop --no-block` también superó el plazo del controlador mientras la unidad seguía en espera.

Una primera prueba concreta con FFmpeg ejecutado sin limitación de hilos provocó un fallo tipo `SEGV` de la unidad antes de completar el Engine; esto **no se considera un éxito**, y se conservaron como observaciones las incidencias. La siguiente prueba utilizó una fuente de audio sintético a velocidad real con FFmpeg y un solo hilo, evitando cargas artificiales de CPU/memoria.

## Solución y evidencia medida

El trabajo **no se detiene a sí mismo**. Dos servicios transitorios independientes bajo `systemd --user`:

1. **Controlador I17 independiente**, que prepara datos sintéticos, conoce un identificador de servicio generado al azar y controla su propio informe JSON.
2. **Target I17 Engine + FFmpeg** en otro cgroup: montaje privado sin red de I15, user/mount/net/pid namespaces, `unshare --pid --fork`, PID 1, código/virtualenv Engine de solo lectura y un workspace temporal. El servicio tiene `MemoryMax=512M`, `TasksMax=32`, `CPUQuota=100%`, `KillMode=control-group`, `TimeoutStopSec=3s` y `SendSIGKILL=yes`.

El controlador solo admite detener unidades `montara-i17-target-` + 12 caracteres hexadecimales. Envía **`systemctl --user stop --no-block`**, espera hasta 10 segundos que termine el cliente, y verifica de forma independiente que el cgroup de esa unidad **ya no contiene PIDs** y que no queda FFmpeg. El servicio también limpia sus temporales al cesar.

**Ensayo físico PASS (VM FER):**

- Engine auténtico del submódulo pinneado `b5e48317ef85225f901adc69af8cc17aa8146880`; proyecto sintético creado con el esquema real.
- Hizo handshake `ready`, entró en proyecto y respondió `opened`.
- FFmpeg real, fuente sintética `anullsrc`, `-re`, un único hilo, sin archivos multimedia reales ni red. Verificado en el cgroup antes de cancelar.
- El controlador independiente sobrevivió a la cancelación. El Engine y FFmpeg dejaron de existir; cgroup vacío; servicio temporal eliminado.
- **Tiempo hasta apertura:** ~2,28 segundos; **duración total incluyendo cancelación y confirmación:** ~5,50 segundos.
- **Memoria pico leída hasta antes de cancelar:** ~94,27 MiB de cgroup; no representa exportaciones/FFmpeg reales ni p95.
- `forced_cancel_certified=true`, `engine_pids_reaped=true`, `ffmpeg_descendant_reaped=true`, `controller_survived_cancel=true`. No quedó ninguna unidad de target activa.

**Segunda repetición física PASS:** Engine real, FFmpeg detectado (`ffmpeg_processes_before_cancel=1`), 3 PIDs en cgroup antes de detener, `controller_survived_cancel=true`, `engine_pids_reaped=true`, `ffmpeg_descendant_reaped=true`, `cgroup_empty_after_cancel=true`, `forced_cancel_certified=true`. Apertura ~2,95 s, ciclo total ~6,10 s, MemoryPeak 94,15 MiB medido antes de cancelar. Nada persistente.

Se ejecutaron pruebas anteriores con un hijo `sleep` en lugar de FFmpeg, pasando la cancelación completa (~5,82 s), así como dos pruebas que no pudieron certificar la parada con el timeout incorrecto. En el informe se separan explícitamente los fallos previos del resultado PASS.

## Limitaciones — no entregar a una beta multiusuario todavía

- El laboratorio aún utiliza el UID real de FER en el host (aunque use user namespaces), no identidades host segregadas por tenant. Faltan perfiles seccomp/AppArmor revisados, política de salida de red prevista para Stage y trabajo real con vídeo/Companion.
- `systemd-run --pipe --wait` se usó para validar el protocolo; **no es el contrato definitivo de un broker de ejecución independiente del host ni el protocolo `PrivateExecutor` de I13**. Antes de exponerlo hay que diseñar autenticación control-plane → broker, no permitir desde HTTP nombres de unidades, rutas, señales, PID ni UID y prevenir reutilización de jobs/cgroups.
- No se ha ensayado un FFmpeg de normalización/render sobre proxy MP4 ni una cancelación durante una etapa de vídeo real, solo un filtro de audio sintético. Faltan picos memoria/disco de varios jobs y pruebas de recuperación al reiniciar VM.
- El controlador necesita persistir el estado de la cancelación y **fencing** de generación; el fallo de host puede interrumpir el propio controlador y debe recuperarse en el siguiente arranque sin dejar proyectos ambiguos.
- La prueba de la aplicación real y del supervisor I13 sigue sin abrir el editor desde el dashboard público; la beta Owner 8115 no ha recibido estas rutas.

## Próxima decisión

I17 acredita que **el mecanismo Linux sin Docker puede controlar la cancelación de todo un cgroup**, no que necesariamente sea la opción final para todos los proveedores. La siguiente puerta práctica: comparar con un runtime OCI equivalente o justificarlo con los requisitos, diseñar broker de ejecución limitado con garantías de aislamiento por UID/tenant y conectar gradualmente I13 tras pruebas adversariales. No ampliar arquitectura por inercia; el objetivo sigue siendo proyecto → Engine → Companion → MP4 y una integración limpia con Chema.

**Seguridad operativa:** no ejecutar la prueba sin entorno de laboratorio, no tocar Chema 8101–8103, ni usar datos reales. GitHub CI comprueba contratos y sintaxis sin iniciar unidades de systemd.
