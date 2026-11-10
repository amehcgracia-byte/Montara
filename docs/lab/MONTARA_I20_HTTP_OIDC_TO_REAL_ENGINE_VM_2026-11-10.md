# I20 — Primer recorrido HTTP autenticado → Engine REAL aislado en VM

**Fecha:** 10 de noviembre de 2026. **Tipo:** prueba física de integración opt-in en VM de FER, sin desplegar ni modificar Owner C8 público, la cuenta Google real, los servicios de Chema, `main` o los vídeos. **NO prueba todavía un editor multiusuario seguro de producción ni Companion/MP4.**

## Qué faltaba hasta ahora

I13 proporcionaba autorización HTTP por sesión Google y propietario, pero solo con broker falso; I14–I17 habían abierto y cancelado el Engine real en Linux aislado, pero sin pasar por una petición HTTP autenticada. I18/I19 documentan reservas y recuperación, pero el broker de producción no está cableado. **I20 reúne por primera vez, en una sola ejecución física:** inicio de sesión con Google OIDC sintético *firmado y verificado* → Owner ID de la DB real del proyecto (DB temporal de laboratorio) → catálogo propio → comprobaciones HTTPS Origin/CSRF → `POST /urano/v1/projects/<uuid>/open` de I13 → `EngineProjectRegistry` → `RuntimeActivationGuard` → un proceso auténtico del Engine en namespace Linux con `systemd --user` cgroup de límites reales → verificación del proyecto abierto → desmontaje, cgroup vacío, guardia `idle`.

## Qué se ejecutó

`tests/urano_i20_oidc_to_real_engine_lab.py`, invocación **manual opt-in** en VM Linux con Engine pinneado `b5e48317ef85225f901adc69af8cc17aa8146880`:

- Proveedor `SignedFakeGoogle` del proyecto: firma tokens y ejecuta las comprobaciones criptográficas de OIDC existentes. **No conecta con Google real ni utiliza client ID/secret de FER**.
- Dos sesiones HTTPS mediante Flask `test_client`, un catálogo privado temporal y un proyecto `project.json` creado por `core.project.new_project_document` del Engine verdadero. Un segundo owner recibe HTTP **404** al intentar abrirlo, un anónimo recibe **401** y una solicitud sin CSRF **403**.
- Se inyecta en el `OwnerEngineGateway` opt-in un ejecutor exclusivamente de laboratorio `CgroupLabExecutor`, que crea un nombre de servicio impredecible y lo ejecuta mediante `systemd-run --user --pipe --wait --collect`, aislamiento I15 user/mount/net y PID namespace I16. La raíz tmpfs solo monta código/venv de lectura y **un único workspace sintético**; no se monta el HOME/DB real del portal.
- Se comprueban las cuotas mediante `systemctl --user show` **en la unidad activa**: `MemoryMax=512M`, `TasksMax=32`, `CPUQuota=100%`; se valida que el worker anuncia PID 1 y que `opened` devuelve la carpeta autorizada. El guard pasa a `ready` únicamente tras confirmar la apertura real.
- El cierre usa `KillMode=control-group`, `TimeoutStopSec=3s`, `SendSIGKILL=yes`. El comprobador **conserva el `ControlGroup` atestado antes de detener** y exige que sea la ruta exacta esperada de la unidad. Así, al descargar systemd la unidad y devolver `ControlGroup=` vacío, **nunca consulta `/sys/fs/cgroup/cgroup.procs` de la raíz**. Confirma eliminación del cgroup, invalida guard por generación y termina en `idle`.

## Mediciones de la VM

| Prueba física | Hasta respuesta HTTP `ready` | Apertura+cierre completo | Peak de cgroup hasta handshake | Resultado |
| --- | ---: | ---: | ---: | --- |
| Primer ensayo correcto | **2,442 s** | **5,553 s** | **83,61 MiB** | PASS |
| Segundo ensayo correcto | **2,902 s** | **6,115 s** | **83,50 MiB** | PASS |

Previamente hubo un **fallo de atestación de limpieza** tras desaparecer el campo `ControlGroup` por descarga automática de la unidad. El kernel ya había detenido los procesos, pero el test intentaba consultar un grupo no identificado. Se corrigió guardando la identidad exacta y se añadieron pruebas negativas; **se conserva el fallo en la documentación**. Estos números son de apertura sintética sin medios, no de Stage, render, concurrencia ni SLA.

## Tests y compatibilidad

- `tests/test_urano_i20_oidc_real_engine_lab_contract.py` usa exclusivamente `urano/lab_cgroup_identity.py` (stdlib, sin importar Google/Engine), para que los workflows antiguos sin dependencias de OIDC puedan descubrirlo: nombres de unidades válidos, rechazo de ruta vacía/raíz/otro servicio, estado live no vacío, cgroup eliminado con identidad previamente validada, script explícitamente opt-in. CI offline no arranca systemd ni consulta Google.
- Pruebas locales I20 + I13 + I19: **17 tests, 10 subtests PASS**. La prueba física I20 requiere ejecución manual por operador en VM y no está incluida en el workflow general Linux.
- El protocolo HTTP solo revela `{project_id, state, generation}` sin UIDs, rutas, PID ni nombres de unidad. El navegador no decide un owner, worker, ruta o tecnología de infraestructura.

## Pendiente para levantar bandera 1 visible en el navegador

**No conectar todavía este laboratorio al Owner público.** Su `CgroupLabExecutor` corre bajo el UID del operador en el host; el aislamiento de user/mount/net/pid y cgroup está demostrado, pero **no se ha certificado separación de UIDs entre tenants, hardening seccomp/AppArmor, recuperación durable entre `RuntimeActivationGuard` y I18/I19, seguridad de tareas simultáneas de vídeo ni control de canales al cerrar sesión**. Tampoco persiste un worker de producción tras salida del HTTP; se detiene al completar el test.

El siguiente paso directo es sustituir el ejecutor de laboratorio por un **broker real de vida de proceso**, con estado de I18/I19 y reconciliación de I13, aislamiento host/OCI según prueba de seguridad, y conectar la ruta `POST /open` solo detrás de un feature flag de beta restringida. Después se incorpora UI «Abrir proyecto» y el flujo con Companion. No ampliar más laboratorios sintéticos salvo para resolver ese enlace.

**`main` de Chema permanece intacta.** PR #189 sigue DRAFT hasta recorrido beta web → Engine → Companion → MP4 local validado por FER.
