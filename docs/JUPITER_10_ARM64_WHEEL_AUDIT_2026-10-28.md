# JÚPITER-10 — Verificación de paquetes ARM64 sin iniciar nubes (2026-10-28)

**Estado:** inspección documental del lock x86_64 actual de `main` y metadatos públicos PyPI. No se ha compilado imagen ARM64 ni ejecutado el motor en ARM; no hay benchmark nuevo. Solo rama `fernando/continuacion-montara`.

## Fuente e identidad
- `Dockerfile` usa `python:3.11-slim-bookworm` y etapa `node:22-bookworm-slim` para Deno; `deploy/requirements-linux.lock` indica generación con `--python-platform x86_64-unknown-linux-gnu`.
- Componentes binarios fijados especialmente sensibles: `av==14.2.0`, `ctranslate2==4.8.4`, `llvmlite==0.45.1`, `numba==0.62.1`, `onnxruntime==1.31.1`, `opencv-python-headless==4.11.0.86`, `numpy==1.26.4`, `scipy==1.17.1`, `scikit-learn==1.9.1`, `soundfile==0.14.0`.
- Verificación positiva de paquetes individuales: PyPI lista wheel Linux aarch64 para `av 14.2.0` (https://pypi.org/project/av/14.2.0/), `llvmlite 0.45.1` con CPython 3.11 manylinux_2_27/2_28 aarch64 (https://pypi.org/project/llvmlite/0.45.1/) y `ctranslate2 4.8.4` con aarch64 (https://pypi.org/project/ctranslate2/4.8.4/). Esto no certifica el *conjunto completo* ni el binario instalable para cada combinación Python/glibc.
- El preflight existente `deploy/preflight.py` reporta `platform.machine()`, límites cgroup y prueba mínima FFmpeg; reutilizarlo. El contenedor x86 ya está aceptado con pruebas Stage en `docs/ANTES_DEL_SERVIDOR.md`.

## Primera prueba propuesta — sin tocar motor
Ejecutar desde checkout de pruebas en un host con pip actual, conexión PyPI y espacio privado, usando una **copia** del lock:
```sh
python -m pip install --dry-run --ignore-installed --only-binary=:all: \
  --platform manylinux_2_28_aarch64 --platform manylinux_2_27_aarch64 \
  --platform manylinux2014_aarch64 --platform manylinux_2_17_aarch64 \
  --python-version 3.11 --implementation cp --abi cp311 --abi abi3 --abi none \
  --report /tmp/montara-arm64-resolve.json \
  -r deploy/requirements-linux.lock
```
**Interpretación:** si todos los pins se resuelven, la prueba verifica **disponibilidad de distribución binaria indexada** bajo tags declaradas, no que montara funcione. Si falla, conservar nombre/version que lo provoca y consultar distribuciones de PyPI sin actualizar todo a ciegas. La resolución cruzada con pip no sustituye una instalación ARM real; en particular, marcadores de entorno y dependencias nativas pueden tener matices. `manylinux_2_28` es compatible con glibc de Debian Bookworm 2.36 en términos de versión, pero aún requiere tests de librerías.
Si pip rechaza los argumentos por versión instalada o faltan wheels indexadas, la incidencia es de la verificación y no necesariamente del motor.

## Gate real posterior (sin activarlo todavía)
1. Build `docker buildx build --platform linux/arm64` en entorno descartable. No medir rendimiento bajo emulación QEMU.
2. Verificar `uname -m` = aarch64 (en ARM nativo), `python -c 'import av, ctranslate2, llvmlite, numpy, scipy, cv2; print("ok")'`, versión `deno` y `ffmpeg -filters` que incluya `v360`.
3. Ejecutar `python -m deploy.preflight --server --data /data --smoke` y `python -m deploy.warmup --data /data` sobre volumen QA, manteniendo `MONTARA_PREVIEW_PASSWORD` fuera de logs.
4. Repetir `tests/e2e_journey.py` en instancia aislada; comparaciones con mismo fixture/plan y validación audiovisual.
5. Registrar SHA proyecto/submódulos, salida, cache, CPU, memoria peak cgroup, disco pico, wall times. Ningún crédito cloud gastado antes de pasar compatibilidad binaria.

## Riesgos a mantener explícitos
- Docker multi-arch base no basta: Deno/npm y wheels aarch64, bibliotecas FFmpeg/opencv, CPU NEON y recursos cgroup son rutas separadas.
- `VideoToolbox` y Vision/Quartz de Mac no son equivalentes a ARM Linux; fallback FFmpeg CPU hay que validar por tarea.
- Oracle Always Free ARM no incluye NVIDIA; el backend y render GPU deben ser rutas distintas.
- Fallos de instalación o runtime no se reparan silenciosamente sustituyendo versiones, porque rompería comparabilidad del x86 lock actual.

**Decisión:** adaptar/validar plataforma, no rehacer el motor, y mantener x86_64 como referencia. Hasta completar build ARM y un E2E no se puede afirmar "Montara es compatible con Oracle ARM".
