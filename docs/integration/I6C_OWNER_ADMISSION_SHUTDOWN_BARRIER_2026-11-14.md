# I6c — Atomic Owner admission/poweroff barrier (2026-11-14)

## A. Novedades
- `owner_shutdown_barrier.py`: bloqueo compartido `flock` durante el arranque completo de un worker del broker privado; bloqueo exclusivo para el controlador de apagado.
- Bajo el bloqueo exclusivo se vuelven a leer los ledgers Owner (I6b). Si están vacíos y el resto de condiciones del watchdog fueron satisfechas, se crea un marcador root-only `draining` antes de invocar el callback autorizado de apagado.
- El marcador impide nuevos arranques hasta reinicio. En error del callback se retira. Se rechazan rutas de barrera no privadas, symlinks y bloqueos no verificables.
- La ruta `DemoBroker.demo_start` solo activa la barrera cuando el **operador** configura `MONTARA_OWNER_SHUTDOWN_GATE=1`. No hay cambio de comportamiento predeterminado.

## B. Duplicidades
- Reutiliza I3/ledger, I6a cierre cooperativo e I6b preflight. No añade un segundo Engine, socket, UI, cron o watchdog.

## C. Evidencia
- Tests I6c de `flock` real con hilos, SQLite real, falta de ledger, bloqueo, marker, rollback y flag opt-in.
- Exclusión mutua demostrada por pruebas locales, no una certificación de apagado de VM.

## D. Riesgos y activación bloqueada
- **No desplegado ni activado.** La VM ejecuta un watchdog con política propia fuera de este checkout. Antes de activarlo, el equipo operador debe fijar el directorio root-only compartido (`/run/montara-owner-shutdown`) en broker+watchdog, instalar y verificar **ambas** piezas juntas, y ejecutar el apagado mediante el callback de sistema autorizado.
- Broker actual en VM usa un bundle fijado distinto de `main`; no sobreescribir el proceso ni sus datos para probar esta PR.
- Hay que comprobar la quiescencia de tareas pesadas fuera del ledger Owner (JM/FER, FFmpeg, audio, SSH, colas en curso), más las rutas de recuperación de systemd al reiniciar; los fallos deben conservar la VM en ejecución.
- `draining` no se limpia durante una solicitud de apagado aceptada: se elimina automáticamente con `/run` tras reboot; si el OS no apaga después de aceptar la solicitud, requiere recuperación supervisada.
- Se requiere test real con dos cuentas y Companion por sistema operativo. No interpretar CI de contratos como validación E2E completa.

## E. Integración
- Cambios de código opt-in, sin sudo ni alteración de servicios. Se podrá fusionar en main tras pruebas, pero no dar I6 por cerrado en operación hasta el ensayo del apagado real y la recuperación.
- Submódulos: Engine `92c7bc33f59baae92a8d61e5dd4bf0ce9685d79e`; Mixer `f15ff91c1b80fc5f157099dcd9451d958d553ae6`, ambos intactos.
