# URANO U13E1 — vídeo sintético real, ingest del Engine en Docker

**Fecha:** 2026-11-06. **Estado:** PR draft; pendiente resultado del job multimedia. No desplegado.

## Objetivo y evidencia esperada

Tras U13D2D (abrir proyectos con Engine real en dos contenedores), realizar la primera operación de **procesamiento real de medios** dentro del Engine y su volumen privado, con datos creados por FFmpeg. Esto sigue sin validar edición final, exportación o Companion.

La prueba deriva la idea de medios sintéticos existentes en `tests/e2e_journey.py`: cámara sintética con sonido y master WAV de 20 s. Genera ambos dentro del contenedor y de un workspace temporal. Crea proyecto con el esquema verdadero `core.project.new_project_document`, lo abre mediante `server.api.create_app(project_path=...)` (Engine real) y usa endpoints reales:

- `POST /api/v1/inputs/videos` para registrar el MP4.
- `POST /api/v1/inputs/master` para registrar el WAV.
- `POST /api/v1/stages/ingest/run` para arrancar la fase real.
- `GET /api/v1/project` para seguir el estado ingest hasta `done` o fallo y verificar metadatos de cámara obtenidos por ffprobe y la normalización real de vídeo dentro del workspace privado. El Engine fijado devuelve deliberadamente `outputs={}` para ingest; no confundirlo con ausencia de trabajo.

La ejecución CI construye imagen Montara fijada, la arranca con `isolated_container_command` (rootfs de solo lectura, sin red/capacidades, UID no root, límites 2 CPU/2 GB, workspace único). Los datos generados son ficticios y se eliminan tras la prueba. No se accede a medios privados ni se toca host.

## Estado de seguridad y limitaciones

- **No se ha probado todavía la edición o export**. Que el ingest termine no garantiza que sync, edit y export funcionen dentro de este modelo. U13E2 deberá probar la cadena completa utilizando medios sintéticos y/o Companion.
- Esta es una prueba aislada del Engine dentro de Docker mediante Flask test_client en el mismo proceso contenedor; todavía no pasa por el protocolo stdin/stdout U13D2C. Para unir ambas cosas hay que ampliar el worker con operaciones mediadas, sin aceptar rutas arbitrarias del navegador.
- No mide concurrencia real ni tiempos/costes de la arquitectura Companion+servidor. No usar este ingest como benchmark del producto.
- Solo CI efímera con `GITHUB_ACTIONS=true`; el test limpia archivos UID 10001 tras recuperar propiedad de los datos sintéticos del runner. No reutilizar el modelo de permisos de laboratorio en producción.
- Sin usuarios, URLs, credenciales, puertos públicos, nube persistente, DNS ni cambios en `main`.

## Próximo gate U13E2

Probar sync/edit/export reales con 2 cámaras + master sintéticos, comprobar export MP4 mediante ffprobe/decodificación, aislar dos usuarios, reabrir/recuperar trabajo; y después integrar navegador/Companion local-first, control de originales y autorización de rutas. Para Chema no hay aún una URL privada con capacidad completa ni validación de seguridad.

Toda prueba debe tener resultados separados: **ingest**, **export real**, **reapertura**, **Companion+servidor** y **concurrencia real**, sin dar por superado un gate a partir de otro.
