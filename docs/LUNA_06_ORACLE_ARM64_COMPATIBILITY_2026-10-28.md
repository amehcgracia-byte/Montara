# LUNA 06 — Compatibilidad Linux ARM64 y Oracle Always Free (2026-10-28)

Estado: auditoría estática + fuentes primarias consultadas el 28-10-2026. Sin despliegue, compras, benchmarks ni cambios al motor. Branch `fernando/continuacion-montara`, main preservada.

## Evidencia directa desde `main`
- `deploy/README.md` dice explícitamente que la plataforma de aceptación es Linux x86_64 y otra arquitectura debe verificarse.
- `deploy/requirements-linux.lock` fue generado por `uv pip compile ... --python-platform x86_64-unknown-linux-gnu`; incluye componentes nativos `av==14.2.0`, `ctranslate2==4.8.4`, `onnxruntime==1.31.1`, `opencv-python-headless==4.11.0.86`, `llvmlite==0.45.1`, `numba==0.62.1`, `numpy==1.26.4`, `scipy==1.17.1`, etc. El lock no acredita ruedas ARM para *todas* esas versiones.
- `Dockerfile` combina `node:22-bookworm-slim` + Python 3.11, copia Deno empaquetado desde Node/npm, instala FFmpeg Debian, fuentes y dependencias Python. Es razonablemente multiplataforma en sus bases, pero `npm deno`, wheels y códecs deben probarse realmente en ARM64. Dockerfile no instala CUDA ni GPU.
- `deploy/preflight.py` ya hace comprobaciones Linux, paquetes, acceso privado, fuentes, FFmpeg/ffprobe, escritura de volumen y smoke de H264+AAC+subtítulo. Añade en reporte architecture, cgroup CPU/memory, commits e identidad; **reutilizarlo**, no crear otro preflight.
- `compose.yaml` fija 2 CPU, 8 GiB y un solo servicio/volumen; la aplicación mantiene estado global por proyecto. CI x86_64 existente: Stage 100.233991s, 16 cortes, export 329.192s, pico cgroup 1.84GiB, pero no es benchmark de ARM ni carga 4K/30GB.

## Evidencia externa verificada
- Oracle Always Free oficial: para cuentas Always Free 1500 OCPU-h y 9000 GB-h mensuales, equivalente a 2 OCPU/12 GiB para una VM continua; 200 GB de block storage total incluido boot volume; región de origen y disponibilidad de forma restringida. https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm . Oracle también publica 3000 OCPU-h y 18000 GB-h de asignaciones gratuitas en páginas de precios para tenancy pagada: **NO asumir cuota 4/24 Always Free sin verificar el tipo de cuenta**. https://www.oracle.com/cloud/price-list/
- Docker multi-platform: https://docs.docker.com/build/building/multi-platform/ ; buildx `--platform linux/arm64`, emulación QEMU posible pero lenta para trabajos CPU; rendimiento debe medirse en ARM nativo.
- CTranslate2 4.8.4 publica wheels Linux aarch64 y soporta CPU ARM; https://pypi.org/project/ctranslate2/ y https://opennmt.net/CTranslate2/hardware_support.html . onnxruntime 1.31.1 publica aarch64; https://pypi.org/project/onnxruntime/. Esto no certifica todos los paquetes ni Whisper completo.

## Matriz de riesgos antes del primer build ARM
| Riesgo | Diagnóstico | Test que cierra |
|---|---|---|
| Wheels no disponibles para versión fija | PyAV, OpenCV, numba/llvmlite, scipy/numpy, ONNX, CTranslate2, Playwright | Resolver lock ARM64 separado; pip --only-binary=:all: sobre wheelhouse target / build nativo. No actualizar librerías para arreglar un falso fallo de lock sin registrar diff |
| Ejecutable Deno en stage de Node | Instala paquete npm en la arquitectura base correspondiente | `docker buildx build --platform linux/arm64` y `deno --version` dentro del contenedor |
| FFmpeg y codecs/filtros | Debian ARM puede variar capacidades | preflight H264+AAC+drawtext; 360 v360 filter y ffprobe; etapa de render real |
| Whisper CPU ARM | Wheel compatible no garantiza misma inferencia/timing | warmup y prueba con voz representativa para latencia y memoria |
| Motor Python, dependencias Mac | Algunas rutas tienen VideoToolbox/Vision/Quartz y fallback; no asumir paridad | ejecutar CI/e2e Stage, Push, Mix, Session con motores fijados y comprobar salidas |
| Memoria/disk | 2 CPU/12GiB Always Free, 200 GB totales incl boot; os/caché/inputs/temporales consumen volumen | cgroup memory.peak, disk usage pico, headroom preflight y 1 worker |
| Red y seguridad | Crear VM no garantiza HTTPS ni aislamiento multiusuario | SSH tunnel privado, auth, ownership; no exposición pública accidental |
| Velocidad/Coste | 329 s x86 CI no predice ARM | mismo fixture/plan cold-warm, tiempo total subida+render+descarga, RAM/IO, sin usar créditos hasta baseline |

## Protocolo recomendado
1. En rama experimental y equipo/CI aislado, generar `deploy/requirements-linux-arm64.lock` con la misma versión Python, resolver ruedas binarias para arm64, registrar paquetes incompatibles **sin alterar lock x86**.
2. Intentar build `docker buildx build --platform linux/arm64 ...`; si se hace en x86 QEMU, usarlo solo como compatibilidad, no como benchmark.
3. Ejecutar `python -m deploy.preflight --server --data /data --smoke` en ARM real (con credencial privada no guardada en logs) y `python -m deploy.warmup --data /data` en volumen persistente.
4. Correr tests relevantes y E2E Stage de fixture *exacto* con mismos inputs/plan y salida; repetir caché cálida; inspeccionar frames y sincronía, no solo HTTP 200.
5. Registrar JSON: sha motor/mezcla/Montara, `uname -m`, CPU count y cgroup quota, RAM mem peak, espacio mínimo libre, fuentes, duración entrada/salida, fps/color, A/V offset, tiempos por etapa, transferencia y métricas de fiabilidad.
6. Sólo entonces dimensionar Oracle Always Free y decidir CPU de backend / coordinator. Una sola VM de 2 OCPU no es capacidad garantizada para concurrentes ni GPU.

## Criterio de decisión provisional
Candidato razonable para API, coordinación, sesiones privadas CPU y cargas pequeñas; render pesado sin GPU queda condicionado a benchmark nativo y presupuesto de disco. No recomendar contratación de GPU ni convertir una VM Free en servidor de 30 GB multiusuario. Si falla la compatibilidad ARM, continuar probando x86_64 CPU local/CI como referencia; no degradar calidad por forzar Oracle.
