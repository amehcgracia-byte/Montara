# MONTARA — Auditoría preliminar no destructiva de integración (11-11-2026)

**Ámbito:** editor de Chema + arquitectura FER + Companion Windows. **Estado:** inspección de metadatos GitHub, archivos fuente y VM; SIN merge, despliegue, modificación de servicio ni instalación. No es certificación E2E.

## 1. Evidencia física VM (Desktop Commander Remote -> Oracle -> ssh montara)
- Host: `montara-test.europe-west3-a.c.montara-pruebas-10292226.internal`; usuario SSH `fgardel00`.
- `montara-i26-broker.service`: `active`.
- Owner FER de usuario: `montara-owner-beta.service` y `montara-owner-tunnel.service` active/running.
- Loopback `127.0.0.1:8115` escuchando. Servicios Chema `127.0.0.1:8101,8102,8103` escuchando e intactos.
- Disco raíz 96G total, 53G usados, 44G libres (55%); RAM 31Gi total, ~29Gi available.
- No se ha comprobado sesión OAuth positiva actual ni render Stage->MP4: no inferirlos de un puerto activo.

## 2. Estado de ramas y PR (consulta GitHub del 11-11-2026)
- `fernando/integracion` commit inicial confirmado en comparación: `ec1f7e8605f3297259e62a251acd77df3b81a5ea`, 51 ahead y 0 behind respecto a `main` en el momento de la consulta.
- `fix/jm-native-video-save-project-recovery-20261110`: 56 ahead y 0 behind de `main`; 38 archivos afectados en comparativa con main (incluye web, app, Companion, instalador Mac, pruebas y pin Engine).
- Entre ambas ramas: 56 commits exclusivos Chema, 51 exclusivos FER; merge-base `765a34ceec33311cd520856d46fec15adfc6c0a1`. **No fusionar toda la rama**.
- PR #208 (Stage shot-local + presets músico): merged **hacia `fix/jm-safe-auto-framing-user-branch-20261110`**, NO hacia main. Diferenciar merge de subrama del merge en main.
- PR #209 (estabilidad thumbnails Stage): **open/draft**, base `fix/jm-safe-auto-framing-user-branch-20261110`; lleva engine pin y suite E2E total pendiente según descripción. NO desplegado según PR.
- PR #189 FER: DRAFT, no merge hacia main. Descripción del PR es anterior al alcance real I24-I28 y necesita actualización separada cuando se prepare handoff.
- `fernando/companion-windows-w1` respecto a main está divergida (44 ahead /125 behind): tratar como legado de extracción selectiva, nunca reemplazar Companion completo.

## 3. Contratos editor / Companion inspeccionados
- `web/companion.js` actual de Chema se comunica con `http://127.0.0.1:47820`. Incluye `/health`, `/locate`, `/proxies`, `/projects`, `/video-renders` y operaciones locales de export.
- Identificación original: nombre, tamaño, SHA-256 de primeros/últimos 64 KiB; los proxies viajan al servidor, originales permanecen localmente por defecto.
- `companion/companion.py` rama JM native: versión **0.6.10**, `VIDEO_PROXY_RECIPE=3`; las rutas conocidas se guardan en `~/.montara-companion/places.json` en texto local.
- La versión Windows `fernando/companion-windows-w1` inspeccionada es **0.6.2**; incluye `windows_support.py`, `windows_tray.ps1`, pruebas y compatibilidad de binarios congelados. No inferir de esto qué está instalado físicamente en Windows.
- `companion/install.sh` Mac detecta `busy` mediante `/health`, evita sustituir si hay trabajo, verifica puerto 47820 y protege parcialmente sustituciones. **No equivale a un sistema Windows de actualización firmada y transaccional con rollback**. Investigar autenticación de manifiesto y seguridad de origen.
- `app.py` Chema registra múltiples módulos Flask sobre aplicación Engine; la interfaz también usa rutas `/api/v1/wizard`, `/api/v1/edit` y APIs Montara. Introducir adaptador owner+project por operación, no proxy global directo.
- Riesgo a resolver: CORS/origins Companion existentes enumeran localhost, Vercel y trycloudflare, pero no el dominio Cloudflare Worker de Owner ni necesariamente Pages. Comprobar preflight y requisitos Private Network Access en navegador; no ampliar wildcard sin prueba.

## 4. Dependencias y decisiones previas a edición de UX
1. Identificar qué rama de Chema será la definitiva para el próximo merge de main; #209 no es main.
2. Trazar Stage, Push, Show por endpoints reales y sus side effects; mapear rutas que hoy dependen de un proyecto Engine global, rutas de proyecto, export y recuperación.
3. Acordar con Fernando punto exacto de autoarranque Engine y localización de selector contextual de proyectos sobre editor Chema. Mantener Google -> selección Stage/Push/Show sin pantalla obligatoria.
4. Probar tokens de acceso al Companion local para que otros orígenes/páginas no puedan abusar de un servidor loopback. Un fingerprint de bordes no equivale por sí solo a autorización fuerte.
5. Establecer compatibilidad de receta/proxy y pines Engine antes de seleccionar versión base.
6. Auditoría y ejecución de E2E Linux y, posteriormente, prueba humana Windows + prueba cruzada dos propietarios.

## 5. Inventario Windows: PENDIENTE de lectura local autorizada
**Desktop Commander solo muestra actualmente el dispositivo Oracle `instance-20261001-0035`**; no existe acceso remoto habilitado al PC Windows de Fernando. No instalar, borrar, detener procesos ni explorar archivos Windows indirectamente sin su intervención.

**Checklist no destructivo para ejecutar en Windows con aprobación de Fernando:**
- Versión del ejecutable/script del Companion encontrado en instalaciones previas; origen/ubicación, firma y fecha; posibles entradas en Apps instaladas.
- Estado de `127.0.0.1:47820/health`, PID que escucha y ejecutable propietario (si existe).
- Icono de bandeja y forma de inicio automático; no matar procesos.
- Versiones locales `ffmpeg` y `ffprobe`, y carpetas de cache/proyecto **solo metadatos**, sin enumerar nombres de vídeos ni transmitir rutas privadas.
- Comparar `/health`, `/locate`, `/proxies`, export, busy y receta con Chema 0.6.10 antes de instalar nada.

**Comandos de PowerShell de solo lectura, a revisar con Fernando antes de ejecutarlos:**

```powershell
Get-NetTCPConnection -LocalPort 47820 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'montara|companion|python' -or $_.CommandLine -match 'montara-companion' } | Select-Object ProcessId,Name,ExecutablePath
try { Invoke-RestMethod -Uri 'http://127.0.0.1:47820/health' -TimeoutSec 3 | Select-Object app,version,busy,ffmpeg } catch { 'No health disponible' }
Get-Command ffmpeg,ffprobe -ErrorAction SilentlyContinue | Select-Object Name,Source
```

No recopilar `CommandLine` ni listado de rutas completas para compartir sin revisar privacidad; el ejemplo de proceso solo presenta PID, nombre y ejecutable.

## 6. Siguiente puerta de validación
Preparar un análisis endpoint-by-endpoint por mundo y una matriz de compatibilidad de Companion (0.6.2 Windows contra 0.6.10 JM); solicitar decisiones de UX antes de implementarlas. La auditoría actual establece una línea base de integración, **no** indica que Google->editor real->MP4 esté conectado.
