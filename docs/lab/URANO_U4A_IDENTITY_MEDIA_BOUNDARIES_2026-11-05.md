# URANO U4A — perímetros de identidad y medios (primer análisis)

Fecha: 2026-11-05. Investigación documental y lectura puntual de código; sin despliegue ni modificación productiva.

## Marco acordado

Companion es el camino preferente para originales locales, y el usuario desea **conservar la subida manual de originales como capacidad experimental**. U3C ha incorporado una confirmación por intento al frontend; la política comercial definitiva de cuotas y almacenamiento no está decidida. Esto no autoriza a publicar el bundle FFmpeg, pendiente de revisión legal.

## Fronteras existentes, observadas en el código

| Ámbito | Evidencia observada | Consecuencia para URANO |
|---|---|---|
| Navegador | `web/montara.js` llama a `/api/v1` y `/montara/*`; `web/companion.js` se conecta a `http://127.0.0.1:47820` | Hay dos interfaces de datos distintas: backend remoto y servicio local |
| Companion | `companion/companion.py` atiende por localhost, filtra `Origin` y usa IDs de fuentes/proyectos | Filtrado de `Origin` **no equivale a** autenticar cuenta ni autorización por proyecto |
| Backend | `app.py` construye aplicación Flask del Engine y registra módulos Montara, incluidos `resumable_upload` y `full_session` | No crear un backend paralelo sin auditar estas interfaces |
| Subidas | `resumable_upload.py` recibe `POST/PUT/finish` y escribe a `data_root/Uploads` | La confirmación actual es en navegador; los endpoints pueden requerir cuotas, autorización e identidad propias |
| Sesión musical | `full_session.py` guarda `Sessions/<id>/session.json` y `/session/latest` escoge la última sesión del servidor | Se diseñó para una instancia/editor; no asumir aislamiento por usuario |
| Despliegue privado | `deploy/README.md` contempla CPU, una instancia y un editor cada vez | Este modo no sustituye un servicio SaaS multiusuario |
| Demo | `deployment/vercel/README.md` documenta Sandbox y snapshot de cuenta del propietario | No cambiar alias ni recursos del dueño por experimentos U4 |

## Preguntas para el contrato futuro

1. **Identidad:** ¿qué token autoriza a una cuenta a operar sobre su proyecto y trabajos, y cómo se propaga al backend?
2. **Vínculo local:** ¿cómo autoriza esa cuenta al navegador a hablar con *su* Companion, sin confiar solo en que una página proviene de un `Origin` admitido?
3. **Propiedad:** ¿qué pertenencia de usuario y proyecto se valida para cada subida, sesión, proxy, render y descarga?
4. **Clasificación:** separar original local subido excepcionalmente, proxy, audio segmentado, imagen/voz auxiliar, y medio de URL; **no** confiar en la extensión del nombre como prueba de procedencia.
5. **Cuotas:** fijar límites de transferencia, almacenamiento, duración, concurrencia y retención por cuenta/proyecto y por entorno experimental.
6. **Recuperación:** cómo recuperar IDs de sesión, trabajos y permisos tras reiniciar navegador, Companion o backend.
7. **Permisos y privacidad:** qué datos de ruta/fingerprint se conservan en backend y qué medidas impiden fugas entre proyectos.

## Próximo paso U4B — sin cambiar arquitectura todavía

Construir una **tabla de endpoints sensibles** desde `app.py`, `full_session.py`, `resumable_upload.py` y `companion/companion.py`; identificar los controles existentes y las lagunas verificables de autenticación, cuota y ownership. Solo después diseñar pruebas de aislamiento con entornos ficticios. Evitar asegurar que una laguna implica vulnerabilidad explotable hasta reproducirla controladamente.

## Límites de esta nota

Es un mapa inicial de responsabilidad técnica, no una auditoría completa de seguridad ni un esquema de SaaS aprobado. Mantener PR #74 draft y no tocar Engine/Mixer o infraestructura de Chema. Revisión jurídica FFmpeg pendiente para lanzamiento, no para investigación.
