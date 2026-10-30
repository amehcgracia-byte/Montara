# Laboratorio compartido en una VM de Google Cloud (JÚPITER)

29 de octubre de 2026 · Claude, rama `claude/jupiter-gcp-vm`. Respuesta al encargo «JÚPITER: preparación de laboratorio compartido en Google Cloud». Es una **propuesta revisable**: no cambia `main`, motores, mixer ni Vercel. Cada punto está marcado como **comprobado**, **pendiente** o **propuesta**.

## 1. Estado exacto de `main` y submódulos — comprobado

| | Commit |
|---|---|
| Montara `main` | `e46b685` (merge de PR #9) |
| `engine/` (zucker_videos) | `c89e7791ff6200e29c4281b79e84307277f9527f` = `60a7b7e` + marca Montara, falso «Irregular video cadence», rotación de músicos en Push y cortes con cámara estable (zucker_videos PR #48) |
| `mixer/` (ZuckerMixer) | `c7a46a6d8388c6e0703ef54983f2d627ea189f32` (pistas graves silenciosas conservadas) |

`engine-revision.txt` coincide con el pin. E2E Linux de PR #9: Stage, Push y Mix aprobados con `c89e779`; Session y contenedor no se repitieron con ese pin. Los resultados JÚPITER/SATURNO de la rama de Fernando se hicieron con `60a7b7e`: comparar con `c89e779` exige declarar el cambio de motor.

## 2. Requisitos Linux sin Docker — comprobado en el código, no ejecutado en la VM

- Ubuntu 24.04 LTS **x86_64**. ARM64 no está validado.
- Python **3.11**: `deploy/requirements-linux.lock` está compilado para 3.11 y Ubuntu 24.04 trae 3.12. Se instala con `uv python install 3.11` por usuario.
- Paquetes del sistema (igual que el `Dockerfile`): `ffmpeg`, `fontconfig`, `fonts-dejavu-core`, `fonts-liberation2`, `libgl1`, `libglib2.0-0`, `libgomp1`, más `git`, `nodejs`/`npm` para Deno 2.5.6.
- Servidor: `gunicorn` con 1 worker y 8 hilos (`deploy.entry:app`). El backend tiene estado global de proyecto: **un proceso por persona**, nunca varios workers para simular usuarios.
- Contraseña privada `MONTARA_PREVIEW_PASSWORD` (16 caracteres o más) y `MONTARA_DATA` propio.

## 3. Dos instalaciones independientes en la misma VM — propuesta lista para ejecutar

| | José Manuel | Fernando |
|---|---|---|
| Usuario Linux | `jm` (sin sudo) | `fer` (sin sudo) |
| Checkout | `~/montara`, `main` o su rama | `~/montara`, `fernando/continuacion-montara` |
| Python | `~/montara/.venv` (3.11) | `~/montara/.venv` (3.11) |
| Datos / cachés / temporales | `~/montara-data`, `~/.cache`, `~/montara-data/tmp` | ídem en su HOME |
| Servicio | `systemd --user`, `127.0.0.1:8101` | `systemd --user`, `127.0.0.1:8102` |
| Credenciales GitHub | las suyas | las suyas |

- Los HOME tienen permisos `750`: un investigador no lee los datos del otro.
- **Bloqueo de laboratorio:** todo trabajo pesado (render, E2E, benchmark) se lanza con `montara-bench <experiment_id> <comando>`. Usa un `flock` compartido: si el otro está midiendo, espera y muestra quién lo tiene. Nunca dos benchmarks a la vez.
- Ningún servicio escucha fuera de `127.0.0.1`. No se abre HTTP/HTTPS en el cortafuegos.

## 4. Procedimiento reproducible — propuesta (scripts en esta carpeta)

```sh
# Copiar estos scripts a la VM desde cualquier checkout (por ejemplo Cloud Shell):
gcloud compute scp --recurse deploy/vm montara-test:~/vm-setup --zone europe-west3-a
# Una vez, como administrador de la VM:
sudo bash ~/vm-setup/admin_setup.sh
# Cada persona, entrando con SU usuario (gcloud compute ssh jm@montara-test --zone europe-west3-a):
bash deploy/vm/user_install.sh main 8101                           # jm
bash deploy/vm/user_install.sh fernando/continuacion-montara 8102  # fer
# Abrir desde el propio ordenador:
gcloud compute ssh jm@montara-test --zone europe-west3-a -- -L 8101:127.0.0.1:8101
#   → http://127.0.0.1:8101
```

**Actualizar:** volver a ejecutar `user_install.sh` con la misma rama. Hace `fetch` y `pull --ff-only` (nunca reset), actualiza submódulos al pin de la rama, reinstala el lock y reinicia el servicio. La contraseña se pide solo la primera vez y se guarda en `~/.config/montara/env` con permisos `600`.

`user_install.sh` ejecuta al final `deploy.preflight --smoke` y `deploy.warmup` (descarga Whisper a la caché del usuario).

## 5. Git y coordinación entre agentes — propuesta

- José Manuel aprueba `main` y los pines. Fernando trabaja en su rama. Claude y Codex, en ramas `claude/…` y `codex/…` con PR pequeñas.
- Cada agente trabaja en el checkout de su responsable: el agente de José Manuel en `jm`, el de Fernando en `fer`. Nunca en el HOME del otro.
- Antes de comparar resultados: `git submodule status` en el manifiesto. Ningún agente mueve pines salvo una PR autorizada, que vaya acompañada de la PR del motor correspondiente.
- Lección de esta semana: el pin de `main` perdió dos PR del motor porque la rama de la que salió no las incluía. **Regla propuesta:** antes de mover un pin, comprobar con `git merge-base --is-ancestor` que el pin nuevo contiene el anterior, o declarar en la PR qué se pierde.

## 6. Entire — evaluación (sin activar)

Coincido con `docs/MONTARA_COLLAB_CLOUD_LAB_ENTIRE_PROTOCOL_2026-10-28.md` (rama de Fernando), con una corrección: **Montara, zucker_videos y ZuckerMixer son repositorios públicos** (comprobado por API el 30-10-2026; una versión anterior de este README decía lo contrario, y era un error). Por tanto:

- Los checkpoints de Entire viajan a refs del repo y, siendo público, **los puede leer cualquiera**. Las transcripciones incluyen salidas de herramientas, rutas y fragmentos de archivos.
- El filtrado de secretos es *best effort*. En esta VM habrá contraseñas en `~/.config/montara/env` y tokens de GitHub o Google: un agente que lea esos archivos los metería en la transcripción.
- **Recomendación:** no activarlo en la VM ni en Montara por ahora. Si se pilota: repositorio privado aparte para checkpoints, clon desechable con datos sintéticos, `entire status` antes del primer commit y revisión humana de una sesión ficticia. La fuente de verdad sigue siendo PR + informe.

## 7. Primer benchmark de bajo coste — propuesta

1. VM **e2-standard-4** (4 vCPU, 16 GB, x86_64, Frankfurt), decisión de José Manuel. El contenedor de referencia es de 2 CPU / 8 GiB: para compararse con él, limitar el proceso (por ejemplo, `systemd-run --user -p AllowedCPUs=0-1 -p MemoryMax=8G`) y declararlo. Disco de 100 GB. Encendida solo durante la prueba.
2. `deploy/vm/manifest.sh > manifest.json`: SHAs, FFmpeg, Python, CPU, RAM, disco y tipo de máquina.
3. Gate A sin render: preflight `--smoke` y benchmarks B03/B06/B07 de `experiments/media_optimization/`.
4. Stage `much-to-me` (3 cámaras + master), **tres veces**, alternando caché fría/caliente, con `montara-bench MTLAB-…-jm-gcp python tests/e2e_journey.py --mode stage --base-url http://127.0.0.1:8101 --output …` contra un usuario QA vacío. Hay que anotar el número de cortes: no se compara contra 16 cortes si el plan sale con 20.
5. Fases del motor desde el proyecto (ingesta, sync, edición, exportación), pico de memoria, disco pico y coste real del día en Facturación.
6. Apagar la VM al terminar (`gcloud compute instances stop`).

## 8. Bloqueos reales

| Bloqueo | Estado |
|---|---|
| Proyecto, presupuesto y VM | **Comprobado** (30-10-2026): proyecto «Montara» en la cuenta amehc; presupuesto mensual de 250 € con alertas a 100, 200 y 250 €; VM `montara-test` e2-standard-4; instalaciones `jm` (8101) y `fer` (8102) activas. Un proyecto creado por error en otra cuenta sigue pendiente de decisión. |
| GPU en Google Cloud | **Bloqueo probable**: el crédito de prueba gratuita no permite GPU. Las pruebas GPU van a RunPod (créditos de Fernando), según el protocolo. |
| Acceso de agentes a la VM desde sus sesiones | **Pendiente**: la sesión de Claude no puede abrir SSH ni llamar a `*.googleapis.com` (bloqueado por su lista de dominios). Hoy solo funciona a través del navegador del propietario (Cloud Shell). |
| Session E2E y contenedor con el pin `c89e779` | **Pendiente** de repetir. |
| ARM64 (Oracle) | **No validado**, fuera de esta primera campaña. |
