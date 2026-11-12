# MONTARA — Gate I29: Companion como eslabón obligatorio de integración (11-11-2026)

**Estado:** especificación de integración comprobada con código; NO se ha implementado ni desplegado el E2E. Próxima rama de cambio funcional después de contrastar el `main` actualizado de Chema. Esta auditoría preserva `fernando/integracion` como base, `main` y servicios inalterados.

## Decisiones de Fernando
- Integración final **solo a main cuando la rama Fernando esté completa y validada** y Chema haya integrado su gran actualización. Mientras tanto, avances y pruebas aisladas en Fernando.
- **Companion es obligatorio:** no marcar la integración como terminada por el login, la privacidad, los proyectos o el arranque de Engine. Los ensayos de laboratorio/Actions pasaron, pero **faltó validación humana** de Companion y recorrido real Google -> editor Chema -> Stage -> MP4 local. El usuario sí verificó previamente login/Google, proyectos y apertura de Engine en Windows; no extrapolar a todo el E2E.
- Conservar funcionalidad original de Chema; portada original Music/Video, Stage/Push/Show, proyecto por modalidad dentro del editor; sin dashboard ni botón técnico obligatorios. Windows icono bandeja. No reinstalar ni limpiar los Companion prototipo hasta validar.
- Originales locales y MP4 final local por defecto; solo contemplar opcionalmente disponibilidad de MP4 servidor hasta 24 h cuando un caso real lo justifique.
- Laboratorios, dos cuentas Linux y material actual **se conservan**. El aplazamiento de la limpieza no es una autorización implícita de ninguna acción.
- No diseñar otro scheduler: revisar I5C/I6/U17–U18 y el broker I18–I27 ya existente.

## Inventario factual recuperado
### Fernando Windows físico
- Windows 10 19045, Python `py` 3.14.3, FFmpeg/FFprobe 9.0.1 en PATH; puerto 47820 sin listener cuando se inspeccionó, por tanto instalado/no arrancado no implica fallo.
- `%LOCALAPPDATA%/Montara-Companion-Lab/companion.py` declara v0.6.2, scripts `windows_support.py`, `video_jobs.py`, `video_recipe.py`, `Montara-Bandeja.ps1`, accesos directos y datos.
- `%LOCALAPPDATA%/Montara-W3L-Build/dist/MontaraCompanion/MontaraCompanion.exe` compilado 2026-11-05 y `windows_tray.ps1`, acceso directo, PyInstaller; no probado en esta sesión, sin firma/update verificados.
- `%LOCALAPPDATA%/Montara-Companion` contiene `proxies` y logs, no código; posibles datos de ejecución del binario.
### JM rama candidata `fix/jm-native-video-save-project-recovery-20261110`
- `companion/companion.py`: VERSION 0.6.10, `VIDEO_PROXY_RECIPE=3`, escucha 127.0.0.1:47820. `/health` expone capacidades (ffmpeg, local_video.engine, busy, etc.); `/locate` verifica nombre/tamaño/SHA-256 bordes 64KiB; `/proxies` y polling/cache; `/projects` elige carpeta LOCAL; `/video-renders` exporta usando originales y receta compatible.
- `web/companion.js`: frontend actual usa esos endpoints y se encarga de subir solo proxy/lossless, con fallback originales condicionado. No introducir otro protocolo concurrente ni cambiar los nombres de rutas sin necesidad.
- `web/montara.js`: `finishOriginalVideo()` compara **igualdad estricta** `companion.local_video.engine === recipe.engine`; hasta dos comprobaciones de originales en paralelo. Evitar una falsa compatibilidad basada solo en version string del Companion.
- CORS: `DEFAULT_ORIGINS` del Companion cubre *.trycloudflare.com, localhost y *.vercel.app. **No cubre** `https://montara-beta-preview.pages.dev` ni `https://montara-owner.memoriainvalida001.workers.dev`. El ajuste seguro será allowlist EXACTA de orígenes aprobados, no wildcard `*.pages.dev` o `*.workers.dev`, y con revisión de cómo se propaga Origin.
- `checkCompanionUpdate()` en `web/montara.js` retorna inmediatamente salvo `isDesktopMac`; la UI de actualización actual se refiere a Mac (.pkg). Windows necesita actualización/verificación propia; no mostrar falsamente botón de update operativo.
- Seguridad: `Origin` y fingerprint no identifican al usuario Google ni prueban propiedad de proyecto; una página autenticada puede invocar loopback solo dentro del permiso del navegador, mientras Owner autoriza cada acceso backend. Revisar protección CSRF/orígenes sin exponer endpoint loopback a terceros. No transmitir rutas locales al catálogo público.

## Contratos de integración mínimos (sin implantar otro editor)
1. Identidad: Google Owner session -> `owner_id` -> `project_uuid` con `mode` en {stage,push,show}. El cliente no dicta owner en URL; el servidor revalida propiedad en catálogo por petición.
2. JM Engine: existe un proyecto/receta interno por trabajo; unión `owner_project_uuid` -> Engine workspace/receta versionada; fase de importación real de media aún NO implementada. I27 hoy arranca workspace sintético, I28 editor provisional NO es editor JM.
3. Companion local: `/health`, `/locate`, `/proxies`, `/proxies/<id>`, `/proxies/<id>/file`, `/projects`, `/projects/<id>/save`, `/video-renders`, `/video-renders/<id>`, `/video-renders/<id>/cancel`, `/video-renders/<id>/file`, opcional `/segment`, mezcla. Mantener IDs efímeros propios Companion distintos del UUID Owner y del path Engine.
4. Red: navegador HTTPS auténtico de Montara (no servidor) solicita localhost Companion; CORS con allowlist exacta de dominio final; Google no inicia ni detiene un ejecutable local. Validar navegador Windows y cambios de certificado/dominio. Fallo Companion debe mostrarse sin upload silencioso de originales.
5. Handoff: receta Engine contiene hash de versión, fuentes originales ligadas por identidad y segmentos; verificar `local_video.engine` antes de render. No bajar originales al servidor; cachés locales pueden regenerarse.
6. Persistencia: catálogos Stage/Push/Show separados por modo bajo propietario, links internos JM/proxy y carpeta local por usuario; referencias del navegador IndexedDB (TTL14d) NO equivalen a TTL del proyecto. El editor entra sin dashboard obligatorio.
7. Ejecución: arrancar Engine invisible cuando haya operación real; no proxy global a `/api/v1/*` ni `/montara/push/*`/`/montara/show/*`; aislar rutas Stage, Push y Show por propietario+proyecto. Revisar worker y submódulo Engine de JM tras actualización main.
8. Actualización: Windows bandeja ya prototipada; comprobar versionabilidad, autenticidad, trabajo ocupado, swap/rollback sin cancelar renders. Mac seguirá la fuente JM vigente, no copiar instalador Mac en Windows.

## Puertas de aceptación que sí faltan
- **A (contrato offline):** tabla exacta de diferencias v0.6.2 Windows vs última JM ya integrada en main, API, CORS, intérprete empaquetado, disponibilidad FFmpeg, hash Engine, proxy recipe. Scripts que existan: reusar `tests/urano_owner_hybrid_preflight.py` y tests Windows/Companion históricos; no añadir un segundo preflight.
- **B (local humano):** iniciar la distribución Windows instalada bajo consentimiento del usuario, GET /health desde el propio ordenador, comprobar `local_video.engine`, y que el navegador HTTPS de Owner reconoce Companion. El preflight I6B alcanza 3 GET, sin fabricar cookies ni validar login Google.
- **C (Owner/JM aislado):** Google real -> portada/editor JM -> selector contextual -> proyecto Stage propio -> crear proxy -> subir -> Engine privado y receta -> exportar con Companion -> MP4 local verificado mediante ffprobe y hash/size; repetir tras refresh/reinicio y cambiar al segundo usuario para demostrar negación de acceso cruzado.
- **D (desarrollo):** no integrar a main hasta superar E2E humano, tests offline+CI y comprobación de compatibilidad nueva main; no dejar UI I27/I28 como segundo producto.
- **Riesgos:** versión Engine bloquea export aunque Companion 0.6.10 esté instalado; CORS deniega dominio Cloudflare; origen local y permisos Windows difieren de Mac; Push utiliza `PushPacks` independiente del wizard; otros endpoints `/montara/*` deben aislarse; workloads de vídeo pueden seguir en procesos al actualizar.

## Primer cambio funcional propuesto tras el corte de Chema
**Un adaptador de entrada mínimo y reversible que sirva el editor JM real desde una sesión Owner Google**, conservando el resto del JS/HTML del editor y el protocolo Companion; asociar el proyecto seleccionado y enrutar cada operación backend por su Engine privado. Antes de desplegar, ensayar CORS exacto y capacidades Companion Windows con el dispositivo físico; no modificar `web/index.html` ni flujo si Fernando no aprueba el diseño.
