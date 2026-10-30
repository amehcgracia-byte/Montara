# JÚPITER — Arranque del laboratorio compartido en Google Cloud
**Fecha:** 2026-10-30  
**Proyecto:** MONTARA · Google Cloud (proyecto de consola «My First Project»)  
**Alcance:** reconstrucción de la sesión de despliegue de Fernando, basada en las salidas compartidas en la conversación. No equivale a una auditoría directa de la VM.

## 1. Principios y restricciones
- Mantener `main` y la instalación de José Manuel sin cambios; experimentar en `fernando/continuacion-montara`.
- No incorporar todavía los commits nuevos de `main`. Congelar las referencias de submódulos de la rama experimental.
- No sobrescribir la instalación previa de Claude bajo `/home/fer/montara`; trabajar en un segundo checkout: `/home/fer/montara-jupiter`.
- Separar código y entornos virtuales, y evitar servicios/puertos adicionales hasta terminar la verificación básica.
- Los ensayos de red de Saturno anteriores son pruebas locales/controladas, **no validación WAN ni producción**.

## 2. Infraestructura observada
| Elemento | Observación |
| --- | --- |
| VM | `montara-test`, zona `europe-west3-a` (observada mediante hostname) |
| CPU | 4 vCPU (`nproc`) |
| RAM | `free -h`: 15 GiB reportados, 14 GiB disponibles en diagnóstico inicial |
| Swap | 0 B |
| Disco raíz | 96 GB, unos 86 GB libres al inicio |
| SO | Linux Ubuntu (inferido de versión del Python del sistema y paquetes FFmpeg) |
| Python del sistema | 3.12.3 (`/usr/bin/python3`) |
| Git | 2.43.0 |
| FFmpeg / ffprobe | 6.1.1-3ubuntu5 |
| Cuenta usada para SSH diagnóstico | `fgardel00` (`/home/fgardel00`) |
| Cuentas de aplicación | `jm` y `fer` |

Se observaron procesos Gunicorn:
- José Manuel: `/home/jm/montara`, usuario `jm`, `127.0.0.1:8101`, 1 worker, 8 threads.
- Instalación anterior de Fernando/Claude: `/home/fer/montara`, usuario `fer`, `127.0.0.1:8102`, 1 worker, 8 threads.

Los accesos de Cloud Shell anunciados como puertos 8080/8081 podrían estar redirigidos hacia 8101/8102, **pero la existencia de estos túneles no ha sido verificada**. Cloud Shell y la VM de Compute Engine son entornos separados. No modificar túneles, firewalls ni servicios compartidos sin inspección previa.

## 3. Instalación preexistente de Claude (preservada)
- Directorio `/home/fer/montara`.
- Rama `claude/jupiter-gcp-vm`, commit `78e9e67` (`VM install: offline checkout copy and one-time generated password`).
- Submódulos: `engine=c89e7791ff6200e29c4281b79e84307277f9527f`, `mixer=c7a46a6d8388c6e0703ef54983f2d627ea189f32`.
- `.venv` con Python 3.11.18.
- Había modificaciones locales sin confirmar en `deploy/entry.py`, `deploy/healthcheck.py`, `deploy/restart_check.py`, `deploy/vm/user_install.sh`. **No se tocaron.**

El intento inicial de explorar estos directorios desde `fgardel00` dio «no accesible o sin carpeta .git»; al ejecutar `sudo -u fer -H` se confirmó que el repositorio de `fer` existía y era accesible. Esto era un problema de contexto/permisos de usuario, no una prueba de repositorio ausente.

## 4. Clonación aislada de Júpiter
El checkout se creó como usuario Linux `fer`, preservando la instalación anterior:

```bash
sudo -u fer -H bash -c '
  set -e
  cd /home/fer
  git clone --branch fernando/continuacion-montara --single-branch \
    --recurse-submodules \
    https://github.com/amehcgracia-byte/Montara.git montara-jupiter
  cd montara-jupiter
  git branch --show-current
  git log -1 --format="%h %s"
  git submodule status
  git status --short
'
```

**Estado inicial verificado:**
- Rama `fernando/continuacion-montara`; commit `e4cf492838501a38c1d053a11bdb6851c3527244`.
- `engine=60a7b7e9a39077b36f45057811abd6a833a168ef` y `mixer=c7a46a6d8388c6e0703ef54983f2d627ea189f32`.
- `git status --short` vacío.
- No se fusionaron actualizaciones de `main`.

## 5. Python y dependencias
`python3.11` no existía en el PATH, pero Claude había instalado Python 3.11.18 mediante `uv` bajo el usuario `fer`. El intérprete base detectado era:

```text
/home/fer/.local/share/uv/python/cpython-3.11.18-linux-x86_64-gnu/bin/python3.11
```

Creación del entorno independiente:

```bash
sudo -u fer -H bash -c '
  set -e
  cd /home/fer/montara-jupiter
  PYTHON=/home/fer/.local/share/uv/python/cpython-3.11.18-linux-x86_64-gnu/bin/python3.11
  "$PYTHON" -m venv .venv
  .venv/bin/python --version
'
```

El resultado fue Python 3.11.18 y `sys.prefix=/home/fer/montara-jupiter/.venv`.

Instalación desde **el `requirements.txt` de la rama experimental**:

```bash
sudo -u fer -H bash -c '
  set -e
  cd /home/fer/montara-jupiter
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m pip check
  .venv/bin/python -c "import flask, numpy, scipy, cv2, numba, librosa; print(\"Imports principales: OK\")"
  git status --short
'
```

Resultados observados: `pip check` respondió **No broken requirements found**; importaciones principales correctas; árbol Git limpio. La rama incluía dependencias como Flask, NumPy <2, SciPy, Numba, OpenCV headless, faster-whisper, librosa, pytest, Playwright y yt-dlp. No se instalaron paquetes globalmente.

## 6. Ensayos iniciales y fallo identificado
Pruebas ejecutadas:

```bash
.venv/bin/python -m pytest -q \
  tests/test_local_proxies.py \
  tests/test_local_proxy_preview.py \
  tests/test_proxy_signature.py \
  tests/test_proxy_cache_fastpath.py
```

**Primer resultado:** 10 superadas, 1 fallida (2.77 s).  
Prueba fallida: `test_preview_rejects_damaged_proxy_and_modified_original` en `tests/test_local_proxy_preview.py`.  
Causa inmediata: `setup(tmp_path)` se invoca dos veces con el mismo directorio; la línea `cache.mkdir(parents=True)` fallaba en la segunda llamada con `FileExistsError`. El primer escenario había devuelto 404 para el proxy alterado; el segundo no alcanzaba la comprobación del original alterado.

Se ejecutaron por separado las otras dos pruebas de ese archivo: **2 passed in 0.18s**.

**Corrección mínima aplicada solamente en el laboratorio experimental:**

```diff
-    cache.mkdir(parents=True)
+    cache.mkdir(parents=True, exist_ok=True)
```

**Repetición:** **11 passed in 2.24s**; `git diff --check` correcto. No implica una prueba E2E del editor ni del companion local, solo la batería citada.

## 7. Commit local y sincronización pendiente
El primer `git commit` se detuvo por identidad de autor no configurada. Se configuró `user.name` y `user.email` **solo en el checkout experimental** y se creó localmente:

- **`4e6fab5`** — `test(jupiter): allow repeated local proxy fixture setup`.
- Árbol de trabajo limpio después del commit.
- El commit se creó en la **VM**, pero **no estaba publicado en GitHub** al redactar este informe.

**Nota de sincronización importante (30/10/2026):** el remoto `fernando/continuacion-montara` continuaba en `e4cf492` al empezar la publicación de este documento. Si el informe se publica directamente desde GitHub, el historial remoto avanzará por separado del commit `4e6fab5` local. **No ejecutar `git push --force`**. Para integrar ambos, primero inspeccionar `git fetch origin`, `git log --oneline --graph --left-right HEAD...origin/fernando/continuacion-montara` y después realizar integración no destructiva (`git rebase origin/fernando/continuacion-montara` si el árbol está limpio y se comprueba que únicamente hay commits locales propios, o alternativa mediante PR). No tocar `main`.

## 8. Estado certificado y próximos ensayos
**Confirmado:** VM accesible por SSH, dos instancias Gunicorn preexistentes detectadas, checkout experimental y submódulos clonados, entorno Python aislado, dependencias importables, 11/11 tests Júpiter seleccionados superados tras corregir fixture.

**No confirmado todavía:** acceso web del checkout `montara-jupiter`, rutas 8080/8081 desde Cloud Shell, funcionamiento conjunto Stage/Show/Mixer, exportación real en esta VM, flujos Júpiter de permisos y persistencia de carpeta Windows/macOS integrados en Stage, creación del companion local, rendimiento bajo carga, RunPod/WAN, equivalencia amplia de códecs ni costes reales de red.

**Secuencia propuesta:** sincronizar sin perder el commit local; seleccionar pruebas adicionales no destructivas de Júpiter/Saturno; ejecutar `deploy/preflight.py` solo tras revisar argumentos y efectos; habilitar preview web independiente sin ocupar 8101/8102; reservar una ventana de benchmarking de CPU intensivo para evitar interferencia entre los dos desarrolladores.

## 9. Seguridad y reproducibilidad
- Ninguna contraseña, token ni clave privada se incluye en este informe.
- No confiar en la identidad Git como método de autenticación SSH o de la aplicación web.
- No compartir por accidente los ficheros de sesión de los agentes ni sus secretos mediante Git/Entire.
- Evitar ejecutar pruebas E2E destructivas sobre proyectos activos.
- Guardar resultados con fecha, versión de engine/mixer, hardware y hash de fixtures antes de compararlos con otras máquinas.
