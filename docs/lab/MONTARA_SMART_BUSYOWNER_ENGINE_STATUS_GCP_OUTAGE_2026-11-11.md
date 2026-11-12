# MONTARA — Causa BusyOwner, estado del Engine y recuperación segura
**Fecha:** 11-11-2026 · **Rama:** `fernando/integracion` · **Publicación:** pendiente; VM GCP inaccesible.

## Evidencia humana
- Al subir `5._Second.mp3` el navegador informó: «Este usuario ya tiene otro proyecto abierto en el Engine privado. El trabajo activo no se cerrará automáticamente».
- Indicador amarillo, botón ON/OFF con error 503 y ninguna manera clara de localizar el proyecto que ocupaba el Engine.
- El usuario propone un estado simple: rojo si apagado, verde si encendido y título del proyecto activo. Pide análisis sin poner en peligro originales ni trabajos.

## Causa confirmada en código
- `JobRecoveryLedger` mantiene índice único por propietario para `starting|running|stopping|orphaned`. El broker `ensure_owner` solo reutiliza un worker verificado cuando corresponde al **mismo UUID de proyecto**; otro UUID devuelve `BusyOwner` y Owner HTTP 409. Es una política de seguridad correcta.
- `owner_mode_entry.py` favorecía un UUID en `sessionStorage` o el más reciente del catálogo. **Ninguno representa necesariamente el worker registrado en el broker**. Por eso entrar a Stage o cargar audio desde otro proyecto provocaba 409.
- El interruptor original en `owner_project_picker.js` invocaba `ensure` incluso para consultar el estado y vinculaba OFF a `wizard/status` del editor. Esto mezcla ciclo de vida del proceso y estado de trabajo. Puede iniciar un worker al comprobarlo, ocultar el proyecto A y fallar con 503.
- El `close_owner` del broker detiene un proceso verificado, pero no incorpora un bloqueo atómico frente al inicio de nuevas tareas desde otra pestaña. **Se retira el interruptor de usuario y no se invocan cierres** hasta diseñar el mecanismo seguro.

## Segundo bloqueo independiente: infraestructura
- En la comprobación de las 21:15 UTC del 11-11-2026: Oracle/DC bridge operativo, `ssh montara` a la IP estática de GCP expira por timeout, Cloudflare Worker responde HTTP 503 en `/healthz`, y Cloudflare API declara túnel `montara-owner-fg` en estado `down`.
- No se tiene acceso conectado a controles de Compute Engine para confirmar si la VM está detenida por su autoapagado o hay problema de red. No afirmar que se haya apagado hasta comprobarlo en consola.
- No se ha reiniciado ningún servicio, cambiado Cloudflare, alterado `main` ni limpiado trabajo. El código actualizado está en GitHub **sin desplegar**.

## Corrección preparada, centrada en adaptar Owner a Chema
1. **Estado de solo lectura del broker** (`private_owner_admission.py`, `private_broker_service.py`, `owner_broker_preview.py`): operación `status_owner` únicamente para sesión Google, CSRF, proyecto propietario verificado y peer Unix autorizado. Consulta el ledger y, si dice `running`, comprueba también unidad systemd, cgroup, PID y marcador de proyecto. Nunca crea ni detiene un worker. Devuelve exclusivamente estado y UUID propietario, no unidades, PIDs, jobs o rutas.
2. **API protegida** `GET /urano/v1/projects/<UUID>/engine-state`: resuelve título del proyecto activo usando catálogo del **mismo usuario**, con `Cache-Control: private, no-store`. `on` requiere identidad verificada y proyecto autorizado; `off` sin worker; `unknown` cuando no hay verificación. Una identidad de otro propietario produce 503 sin filtración.
3. **Cabecera Chema** (`owner_project_picker.js`/`.css`): se elimina ON/OFF. LED verde + `Engine · Nombre del proyecto` solo al verificar worker, rojo `Engine · Off` ante vacío demostrado, ámbar cuando GCP/broker no responde. Si otro proyecto del usuario ocupa Engine, acción `Open active Stage` sin parada. Refresco informativo cada 30 s; sin POST de admisión para dibujar un LED.
4. **Navegación Owner** (`owner_mode_entry.py`): al elegir Video→Stage consulta primero el broker. Si existe proyecto activo autorizado, entra en **ese proyecto**, no en el UUID de la pestaña o el último por fecha. Ante estado desconocido se abstiene de un cambio inseguro.
5. **Selector y errores** (`owner_project_picker.js`, `owner_browser_bridge.js`): al intentar otro proyecto informa del nombre del Stage activo y ofrece volver a él. Un 409 durante una carga recupera solo el estado read-only para dar el nombre, sin intentar cerrar el worker.

## Pruebas fuera de la VM
- Copia temporal y aislada de la rama en Oracle (`/tmp/montara-owner-engine-safety-20261111/`), sin alterar el bridge ni repositorios de trabajo.
- Suite Pytest: **46 PASS + 30 subpruebas PASS** (broker, Owner HTTP, autenticación, read-only, navegación y admisión). Node: **4 PASS** (bridge, Stage resume, pestañas y errores de carga). Sintaxis JS PASS.
- Nuevos casos: 2 proyectos del mismo propietario, UUID ajeno, sesión revocada, CSRF ausente, off/on/unknown, worker systemd inactivo, procesos internos ocultos, ausencia de start/stop por consulta.
- No hay aceptación en el portal real ni tests end-to-end de carga, porque GCP/Cloudflare no está disponible. No etiquetar deploy como PASS.

## Regla de activación
Cuando GCP vuelva a estar accesible, inspeccionar primero broker, ledger y workers en vivo. El servicio root `DemoBroker.__init__` recupera jobs en reinicio marcándolos huérfanos y puede parar unidades; **no reiniciarlo con renders activos**. Preparar instalación reversible, aplicar solo con ventana segura, verificar `engine-state` autentificado, y hacer una sola prueba humana de audio/Stage. No sustituir Engine `b867b3c` por el pin nuevo de Chema hasta probar la transferencia.

## Acciones humanas mínimas
Comprobar en Google Cloud Console → Compute Engine → VM instances si la instancia está `Stopped` o `Running`. Si está detenida, iniciarla y avisar; si está en ejecución, informar del estado sin cambiar IP/SSH/Firewall. Evitar abrir Stage o iniciar renders hasta revisión de seguridad del broker tras conexión.

**Objetivo de producto:** un producto de Chema con autenticación y proyectos privados Owner, no dos aplicaciones superpuestas; el Engine debe funcionar como recurso transparente, no como un interruptor que el usuario tenga que gestionar.