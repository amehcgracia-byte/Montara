# Primera instalación privada de Montara en Linux

Esta instalación conserva la interfaz y los motores del repositorio, con sus ejemplos separados. No es el adaptador temporal de demostración de Vercel. No contrata infraestructura ni conecta automáticamente ningún proveedor de IA.

## Antes de la cuenta

Docker usa Python 3.11, FFmpeg con fuentes de subtítulos, Deno 2.5.6 y el mismo yt-dlp/EJS ya verificado en Linux. `requirements-linux.lock` fija la resolución de dependencias; se regenera explícitamente con:

```sh
uv pip compile requirements.txt deploy/requirements-runtime.txt --python-version 3.11 --python-platform x86_64-unknown-linux-gnu --output-file deploy/requirements-linux.lock
```

La plataforma de aceptación es Linux x86_64. Otra arquitectura necesita su comprobación, no se presume equivalente. El primer arranque usa CPU, una instancia, un editor a la vez. Los 2 CPU/8 GiB de Compose son límites de esta prueba, no una garantía de capacidad para clientes.

## El día de la instalación

Usar un servidor propio de prueba con Docker/Compose y espacio suficiente. Clonar con submódulos la rama/commit aprobado; no reutilizar la carpeta de datos de Zucker Editor. Desde el checkout:

```sh
git submodule update --init --recursive
export MONTARA_BUILD_SHA="$(git rev-parse HEAD)"
export MONTARA_ENGINE_SHA="$(git -C engine rev-parse HEAD)"
export MONTARA_MIXER_SHA="$(git -C mixer rev-parse HEAD)"
read -r -s -p 'Contraseña privada (mínimo 16 caracteres): ' MONTARA_PREVIEW_PASSWORD
export MONTARA_PREVIEW_PASSWORD
docker compose build
docker compose run --rm -T montara python -m deploy.preflight --server --data /data --smoke --output /data/server-check.json
docker compose run --rm -T montara python -m deploy.warmup --data /data
docker compose up -d
```

El comando `read` del ejemplo es de Bash. La contraseña no se escribe en Git, en argumentos de URL ni en informes. Compose necesita recibirla también al reiniciar; conservarla en el gestor de secretos del servidor o un `.env` local con permisos restringidos y excluido de Git. La preparación de Whisper descarga su modelo si falta; puede tardar y consumir almacenamiento/transferencia. No es una llamada a un LLM de pago. Se hace antes de medir el primer vídeo.

El preflight exige 5 GiB libres por defecto para detectar una instalación sin margen; **no** significa que cinco GiB basten para cualquier trabajo. Se puede aumentar con `--min-free-gib`. Si falla, resolver la dependencia/espacio que indique antes de empezar. El smoke genera y elimina un segundo sintético con audio y texto; no certifica la aplicación completa.

El contenedor solo escucha en `127.0.0.1:8090` del servidor. Para la primera prueba privada se puede abrir un túnel SSH desde el ordenador del propietario:

```sh
ssh -L 8090:127.0.0.1:8090 usuario@servidor
```

Abrir `http://127.0.0.1:8090` en ese ordenador y entrar con usuario `montara` y la contraseña elegida. Este enlace es local al túnel; **no es una URL pública para compartir**. Para personas externas hay que poner un proxy HTTPS o acceso privado del proveedor. No exponer Basic Auth por HTTP público ni abrir un túnel al ordenador personal como sustituto del servidor.

## Si el alojamiento no permite Docker

Los recorridos Linux también se prueban arrancando Python directamente. El servidor debe permitir un proceso persistente, Python 3.11, FFmpeg/ffprobe, fuentes DejaVu y Node/npm para instalar el ejecutable Deno. Si falta Python 3.11 puede prepararse un entorno de esa versión con uv; no instalar este lock en una versión arbitraria de Python. Desde el checkout, en un espacio de datos propio:

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r deploy/requirements-linux.lock
export MONTARA_DATA="$HOME/MontaraData"
npm install --prefix "$MONTARA_DATA/Runtime" --no-audit --no-fund deno@2.5.6
export PATH="$MONTARA_DATA/Runtime/node_modules/.bin:$PATH"
.venv/bin/python -m deploy.preflight --server --data "$MONTARA_DATA" --smoke
.venv/bin/python -m deploy.warmup --data "$MONTARA_DATA"
.venv/bin/gunicorn --bind 127.0.0.1:8090 --workers 1 --threads 8 --timeout 1800 deploy.entry:app
```

También necesita la contraseña privada exportada antes. Para un ensayo puede mantenerse el proceso en esa terminal; para alojarlo de forma estable hay que configurar el supervisor/reinicio del proveedor. La cuenta real debe confirmar que permite estos procesos, volumen persistente y acceso privado. Tener un chat con modelos no demuestra que exista ese alojamiento.

## Primera prueba y medidas

1. Entrar en Stage, conservar las cámaras y stems separados del ejemplo. Para comparar solo vídeo, usar el ejemplo de master terminado.
2. Continuar por cámaras, mezcla si corresponde, selección de frames y exportación. Descargar y escuchar/ver el resultado; no basta un HTTP 200 o que aparezca el reproductor.
3. Registrar versión, fuentes y duración/resolución; separar descarga de modelos, ingestión, sincronía, análisis, mezcla, render y transferencia. El motor guarda tiempos por etapa en el proyecto.
4. Reiniciar solo cuando no haya trabajos activos. Confirmar que el proyecto, sus decisiones y el resultado siguen disponibles. No ejecutar `docker compose down -v` sobre datos que se quieran conservar.

Para repetir el ensayo automatizado en una **instancia de QA vacía y separada**:

```sh
python tests/e2e_journey.py --mode stage --base-url http://127.0.0.1:8090 --output server-check-output
```

El cliente necesita Python, Playwright/Chromium y FFmpeg/ffprobe. Toma la contraseña de `MONTARA_PREVIEW_PASSWORD`; nunca ponerla en la URL. **Este ensayo crea/edita el proyecto actual: no usar contra una instancia con trabajo del propietario.** Puede aislarse con otro nombre Compose (`-p montara-qa`) y puerto (`MONTARA_PORT=8091`); su volumen también será diferente.

El informe incluye tiempos del motor cuando existen y tiempo total del recorrido de navegador, que incluye esperas de UI y descarga. No confundirlos con duración de salida, rendimiento puro del render ni estimaciones. La memoria del contenedor en `memory.peak` incluye todo el cgroup y cachés, no es RSS aislada del motor.

## Persistencia y alcance

- Volumen `montara-data`, proyectos, originales subidos, cachés, modelos y decisiones separados del código. Hacer copias cuando no haya trabajos activos; ensayar recuperación antes de abrir cuentas públicas. La persistencia no es por sí sola una copia de seguridad.
- Healthcheck autenticado y de solo lectura. Contraseña incorrecta/ausente no da acceso. Un estado saludable no prueba calidad, exportación ni capacidad para 30 GB.
- Una instancia/contenedor y volumen por usuario durante las pruebas. No aumentar workers Gunicorn para intentar aislar proyectos: el motor conserva estado global. La administración multiusuario y suscripciones todavía no están integradas.
- El runtime de importación está instalado; YouTube puede seguir rechazando enlaces nuevos. No prometer ausencia de CAPTCHA.
- IA remota desactivada por defecto en Compose. Configurar/probar modelo y credenciales cuando exista cuenta; no incluir claves en la imagen.
- Segmentación Vision/Quartz, reemplazos Linux, herramientas de Show pendientes y CorridorKey están recogidos en [la lista de preparación](../docs/ANTES_DEL_SERVIDOR.md). No se declara paridad completa.
- El enlace público estable de Vercel no se cambia con esta preparación. Desplegar en el nuevo servidor y dirigir allí el frontend será un paso posterior, con acceso real y pruebas.
