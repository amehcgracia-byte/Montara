# C8.2 — Portal privado de Google y proyectos por propietario

## Qué queda conectado en código

`urano/owner_beta_wsgi.py` proporciona una fábrica explícita
`create_private_owner_beta(...)` sobre la API privada existente C1–C5:

- `/` redirige a **Google real** (Authorization Code + PKCE) si no existe
  una sesión validada, y al dashboard de propietario si existe.
- El proveedor de Google emplea endpoints oficiales, con token ID validado
  y usuarios beta permitidos; los tests no llaman a Google ni emiten
  credenciales reales.
- El dashboard, la creación de proyectos y CSRF reutilizan
  `urano/minimal_owner_api.py` + `urano/owner_dashboard.py`.
- La API del **editor global** (montaje clásico sin aislamiento por dueño)
  no está registrada; `/api/v1/project` no ofrece proyectos a nadie.
- Si no se ha registrado un `OwnerRuntimeController` privado, la
  infraestructura permanece **sin Engine activo**. La web no arranca un
  subprocess por petición ni presenta un simulador como Engine real.
- Los proxies privados están deshabilitados salvo que el operador
  proporcione un runtime, un almacén de procedencia y un verificador
  de recibos firmados por Companion.

## Estado y no confundir interfaces

La beta que se abrió por túnel en **127.0.0.1:8114** utiliza el editor
clásico protegido con contraseña. **No** utiliza todavía Google, ni el
portal de propietario ni el aislamiento Engine/Companion de C1–C7.
Fue útil para comprobar el arranque e identificar un fallo separado
`CoverageInvariantError` de Stage, registrado en PR #156.

La nueva fábrica es un **portal de identidad y catálogo**, no reemplaza
el editor actual ni el diseño UX de Chema. No tiene un Google mock login
habilitado públicamente.

## Puertas obligatorias para la prueba física

1. Elegir un hostname HTTPS **fijo**, no una URL efímera de prueba.
2. Registrar en Google Cloud un OAuth **Web Client** para
   `https://HOST/urano/v1/google/callback` y definir la pantalla de
   consentimiento, usuarios de prueba y correos beta.
3. Guardar Client Secret y HMAC de Companion fuera del repositorio con
   permisos 0600; registrar los secretos por usuario de confianza.
4. Aprovisionar un `MONTARA_OWNER_PRIVATE_DIR` 0700 de un solo
   propietario del proceso, sin reutilizar datos del editor antiguo.
5. Terminar TLS con un reverse proxy controlado: conexión backend solo
   por loopback, **Host y esquema HTTPS explícitos y verificados**,
   eliminar cabeceras `X-Forwarded-*` del navegador, y proveer
   `wsgi.url_scheme=https` mediante un componente proxy confiable.
   **La fábrica no confía automáticamente en dichas cabeceras.**
6. Conectar los proyectos a workers aislados mediante aprovisionamiento
   de infraestructura confiable. En la implementación actual
   `OwnerRuntimeController` acepta exclusivamente
   `ContainerWorkerBridge` con Docker; la alternativa de procesos UID
   requiere nueva implementación y regresiones de aislamiento.
7. Validar en Chrome/Edge acceso web HTTPS → Companion
   `127.0.0.1:47820`, recibos firmados, proxies y Stage DONE.
8. C8 físico: un proyecto, una sesión auténtica, un original local,
   proxy SHA256, edición, render local y MP4; no dar por terminada la
   etapa por pasar tests unitarios.

## Comprobación / gobernanza

CI en `.github/workflows/c8-google-owner-bridge.yml`; pruebas nuevas
`tests/test_c8_google_owner_ui_bridge.py`, complementadas por contratos
anteriores de C1 y C4.

Todo se prepara en una **rama apilada sobre C8**, sin tocar
`fernando/continuacion-montara`, `main`, los servicios de Chema
8101–8103, el editor del puerto 8114 ni el watchdog de GCP.
El fallo de Stage no se ha corregido aquí: Chema mantiene el recorrido
del editor en `main`.
