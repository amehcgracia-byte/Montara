# MONTARA · C3 — Integración de Companion local y empaquetado (09-11-2026)

## Qué se ha integrado sobre la base actual

Esta rama parte de **C2 #142**, que a su vez parte de **C1 #140** y de `main`; no introduce una segunda aplicación ni reemplaza el frontend de Chema.

- `companion/urano_local_handoff.py`: traductor **local** del descriptor U20 `source_slot + start_ms + end_ms` a una receta validada por `video_recipe.validate`. Solo admite huellas y tamaño de originales reconocidos localmente; no admite rutas ni assets de servidor en el JSON de entrada.
- `companion/companion.py`: inserción **quirúrgica** de `POST /video-renders/handoff`, sin modificar el antiguo `POST /video-renders`, los proxies, cancelación, audio, otros endpoints ni versión actual. Ejecuta `VideoJobs.start`, con comprobación de huellas ya existente y MP4 local de FFmpeg.
- `app.py`: el ZIP que ofrece **`/montara/companion/download`** ahora incluye también `urano_local_handoff.py`, sin el cual una instalación desde la web fallaría por `ImportError`.
- `companion/install.sh`: descarga el nuevo módulo al instalar/actualizar Companion mediante la vía existente; `companion/Install Montara Companion.command` lo copia a la instalación local en Mac.
- `tests/test_c3_companion_delivery.py`: evita regresiones en los dos canales de instalación y preserva ambas rutas de render.
- Se integran los tests reales U21 y la aceptación U22 que consumen **en el mismo ensayo** los descriptores privados del Stage real para dos Companions que deben producir MP4 locales, rechazando huellas alteradas y orígenes ajenos.

## Qué NO está montado todavía

- **No hay todavía una ruta de navegación pública** que conecte el frontend `web/montara.js` directamente a los endpoints de dueño `/urano/v1`. El backend C1/C2 se registra únicamente si el servicio crea explícitamente la aplicación y provisiona un `OwnerRuntimeController`; la web clásica sigue usando el Engine single-user. **No exponer la web clásica en una instancia multiusuario como si fuese segura por propiedad de proyecto.**
- **El laboratorio U22 genera cámaras sintéticas distintas en Stage y en Companion**. Los cortes se transfieren de la misma sesión autorizada, pero todavía no hay prueba de identidad de proxy↔original entre dos equipos físicos. No es prueba de red WAN.
- El modo híbrido beta requiere que los endpoints del **servidor** impidan automáticamente subir originales, incluso si un cliente antiguo intenta hacerlo; el frontend actual ya solicita confirmación explícita. Se conserva la subida manual solo como modo de prueba separado y explícito.
- No se han configurado credenciales reales de Google OIDC, dominio HTTPS, allowlist beta, aprovisionamiento persistente de workers ni cuotas de usuarios. No se debe habilitar la fábrica en un despliegue público sin esa revisión.
- La conversión U21 soporta **cortes básicos** de Stage/YouTube; no hay paridad declarada con todos los ajustes de Show/Push, 360, efectos o transiciones.

## Evidencia CI / instalación

- Workflow `.github/workflows/c3-local-companion-render.yml`: contratos del traductor, test de empaquetado, sintaxis de los dos scripts Mac, y dos procesos de Companion con MP4 real de originales sintéticos locales.
- Workflow `.github/workflows/c3-owner-stage-companion-integrated.yml`: dos Google fake JWT verificados → dos owners HTTP → dos Docker Engine reales con Stage Ingest DONE → los mismos descriptores sin rutas → dos procesos Companion → dos MP4 FFmpeg.
- Las primeras [pruebas de Companion sobre esta rama, run 42611588018](https://github.com/amehcgracia-byte/Montara/actions/runs/42611588018) y de [la cadena integrada, run 42611587822](https://github.com/amehcgracia-byte/Montara/actions/runs/42611587822) terminaron **SUCCESS** antes de la corrección de empaquetado. **No declarar SUCCESS del HEAD definitivo hasta confirmar sus nuevos checks.**
- No hay artefactos de vídeos ni originales en GitHub; solo summaries JSON del ensayo.

## VM GCP: disponibilidad de SSH

La inspección **solo lectura** anterior registró la VM `montara-test-gcp-static` con 8 vCPU, ~32 GB RAM, raíz con 64 GB disponibles, puertos loopback **8101, 8102 y 8103** activos. Al intentar repetir operaciones sin privilegios el 09-11, **Gateway devolvió `CONNECTION_FAILED` por timeout de SSH puerto 22**; **la última orden no se ejecutó y no se realizó ninguna instalación, compilación, contenedor, cambio de firewall o reinicio**.

La VM está autorizada para ensayos por el usuario, pero **no** se debería modificar a ciegas sin nueva conectividad y comprobación de estado. Cuando se recupere el acceso:
1. verificar solo lectura disco, inodos, CPU, checkout/SHAs y servicios actuales;
2. elegir checkout/datos exclusivos para C3, un puerto de loopback nuevo libre y límites conservadores de CPU/RAM/disco;
3. preferir prueba con fixtures sintéticos, sin datos de usuarios, y SIN exponer un proveedor Google ficticio fuera de localhost;
4. publicar HTTPS y Google real solo después de configurar credenciales/allowlist y autorización del entorno de beta; no usar puertos 8101–8103 ni modificar su checkout.

## Criterio de entrega para pruebas humanas

El primer test del usuario debe llegar **después**, no sustituir la aceptación técnica:
- dominio HTTPS autenticado real y UI que despache proyecto/Stage según owner al Engine privado, no al global;
- proxy local del mismo vídeo original que Stage procesó, con huella vinculada al descriptor;
- export MP4 local, cancelación y recuperación básica;
- backend fail-closed para originales, y reinstalación/update Companion sin error de dependencias.

**Próxima tarea necesaria:** puente web autenticado a backend privado y un ensayo aislado en VM con el puerto SSH disponible. No abrir más líneas de experimentación ni exigir 25 usuarios concurrentes ahora.

**Sin merge ni despliegue de main.**

## U23 — Sincronización, CI y puerta de integración (09-11-2026)

- **Gobernanza:** prohibido fusionar o desplegar cambios sobre `main` sin consulta previa al usuario y **OK definitivo de Chema**. Las pruebas, correcciones y preparación en ramas aisladas sí están autorizadas. La integración se propondrá en bloques **C1 → C2 → C3**, tras revisar sus dependencias y el estado de `main` justo antes de cada bloque.
- **Base de código:** al verificar el 09-11, `main@765a34ceec33311cd520856d46fec15adfc6c0a1` está contenido íntegramente en C3, con **0 commits behind**. No crear merges vacíos: repetir comparación inmediatamente antes de integrar porque Chema puede avanzar `main`.
- **Regresión Linux:** en el HEAD previo `837d15b`, `tests/e2e_native_stage.py` no copiaba `urano_local_handoff.py` al Companion temporal. Corregido en `0c9318d`. La repetición `42622608269` alcanzó la prueba de mezclador y falló al iniciar otro Companion temporal; `.github/workflows/e2e.yml` tampoco copiaba el módulo. Corregido en `14e3a50`. **Pendiente confirmar CI final, no declarar PASS todavía**.
- **CI confirmado sobre `0c9318d`:** C2 y los dos workflows C3, Windows, U12 y U12b han terminado SUCCESS. La suite Linux exige revalidación por el segundo problema de fixture.
- **VM GCP:** se restableció SSH por Gateway al encender `montara-test-gcp-static` (35.242.225.127). Revisados sin cambios servicios 8101/8102/8103; todos responden HTTP 401 (autenticación) y `montara-main.service` está activo en 8103. Directorios de laboratorios previos detectados; **no reutilizar ni borrar sin examinar propietario y estado**. No se ha realizado despliegue.
- **Cloudflare:** existe `montara-cloudflare-lab.pages.dev`, proyecto Pages conectado a la rama `fernando/lab-cloudflare-static-benchmark`. No crear duplicados ni considerar este laboratorio una beta autenticada.
- **Próximo trabajo beta:** puente web autenticado hacia owner/Stage privado, identidad proxy-original, política backend contra subida accidental de originales y validación aislada antes de pruebas humanas. No exponer la web global como multiowner.
