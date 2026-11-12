# I5A · Concurrencia por propietario y aislamiento físico pendiente

**Fecha: 2026-11-10.** Origen: U13D2A #95, recuperado selectivamente sobre `fernando/integracion@af1dd2c`.

## Alcance de la integración

Se recuperan intactos el contrato de concurrencia de dos procesos y su informe original completo. El test falla si existe una cola global que obliga a terminar la activación de Alice antes de iniciar Bob. Una operación `busy` de un propietario no debe bloquear el runtime de otro. Esto **no demuestra aislamiento de archivos ni capacidad de render real**.

Prueba ejecutada en worktree independiente, sin tocar beta ni servicios:

`PYTHONPATH="$PWD/tests:$PWD" python -m pytest -q tests/test_urano_parallel_owners.py tests/test_urano_engine_bindings.py tests/test_urano_runtime_activation.py tests/test_urano_engine_worker_process.py tests/test_urano_private_supervisor.py tests/test_c1_minimal_owner_api.py tests/test_c4_owner_dashboard.py tests/test_c8_google_owner_ui_bridge.py tests/test_c8_trusted_local_https.py`

**Resultado: 44 passed, 26 subtests passed.** No se ejecutó E2E del editor ni Engine real.

## Reconocimiento pasivo de la VM GCP

- `fgardel00` es UID 1006; los HOME de `jm`, `fer` y `fgardel00` están en modo 0750, sin inspección de contenido ajeno.
- Kernel Linux x86_64, cgroups v2, herramientas `systemd-run`, `setpriv`, `prlimit`, `unshare`.
- Docker y Podman CLI ausentes. LXD snap instalado y `lxc list --format=json` devolvió `[]` (sin contenedores listados; no se inició ni configuró nada).
- Aunque los sysctl indican que existen espacios de nombres de usuario, el intento no privilegiado `unshare --user --map-root-user --mount-proc ...` falló con **Operation not permitted** al escribir `uid_map`; no basar el plan en rootless namespace sin arreglar y validar esa limitación.
- Pertenecer al grupo `lxd` puede conferir amplios privilegios de infraestructura; no se autoriza su uso para crear contenedores por comodidad.
- Disco ~51 GiB libres de 96 GiB en la inspección; portal propietario HTTP 200. Medidas puntuales, no capacidad certificada.

## Alternativas abiertas

| Alternativa | Qué ofrece | Puerta que falta |
| --- | --- | --- |
| Proceso POSIX con mismo UID | Sin Docker, reutiliza U13D | **No aísla proyectos de otros usuarios**; no apto para multiusuario público |
| Proceso con UID Unix independiente | Puede aprovechar permisos del SO | Provisionado privilegiado confiable fuera de web, root/secretos inaccesibles, límites y recolección FFmpeg |
| LXD privado por owner | Existe instalación base | Evaluar privilegios, perfiles, montajes, operación y recursos con aprobación |
| Docker por owner | CI de #96–#98 y #128–#137 | No instalado, requiere decisión operativa |

## Decisión de I5A

Integrar únicamente la **política de concurrencia por propietario** y su test, sin cambiar `OwnerRuntimeController`, `app.py`, `companion/`, `web/`, `engine/`, `mixer/`, submódulos o servicios. No reducir controles de `ContainerWorkerBridge` para aceptar un subprocess inseguro.

**I5B:** comparar costes y seguridad de aislamiento real, elegir una solución para dos propietarios, probar lectura cruzada denegada, cancelación de hijos FFmpeg, recuperación de caídas, cuotas y permisos. Luego conectar Engine y Stage. Si la elección requiere privilegios o cambia la arquitectura acordada, consultar antes.

No merge a `main`, no despliegue, sin borrar ramas ni PR anteriores.
