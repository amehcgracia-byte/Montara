# MONTARA SMART — Hito 3, Companion Windows (11 noviembre 2026)

**ESTADO: integración servidor PASS, verificación de la instalación Windows del usuario PENDIENTE. NO marcar todavía hito 3/5 como completamente validado. No tocar main.**

## Hecho y probado
- Original JM 14cce126 + Engine b867b3c + Mixer f15ff91.
- `urano/owner_stage_native_export.py`: middleware dentro del worker privado que sustituye únicamente el alias `owner-worker` por la carpeta Stage propia al solicitar `GET edit/native-recipe` y `GET edit/native-master`, sin ofrecer acceso libre a rutas ni originales.
- `urano/owner_original_jm_rpc.py`: gateway Google/SQLite/CSRF, `edit/native-recipe` y máster lossless hasta 2 GiB en streaming acotado, no buffering completo; `edit/native-source` sigue denegado (originales locales).
- `urano/owner_browser_bridge.js`: adaptación de las rutas originales de Chema a la identidad Owner; revisiones de edición tienen **20 caracteres hexadecimales**, NO son números.
- Prueba real en GCP con un Stage de 12 segundos: vídeo/audio HTTP 200, sincronización `waiting_choice`, revisión `waiting_review`, **4 segmentos en receta real**, `engine=b867b3c`, máster **1.152.078 bytes** por gateway Owner HTTP 200, SHA-256 verificado, ruta a original remoto 404. Ejecución completa código 0.
- Regresiones en Unix HTTP: 3/3, con máster de ~4,6 MiB, CSRF y separación de propietarios; JS review/Companion PASS. El worker real root-broker con DynamicUser sigue arrancando y deteniéndose, HTML y proyecto HTTP 200.
- Publicación GCP: portal `owner_original_jm_rpc.py` + `owner_browser_bridge.js`, broker candidato `full_jm_worker.py` + `owner_stage_native_export.py`; revisión publicada `f562269a`, servicios portal, túnel y broker activos, `main` sin cambios.
- Windows: Chema Companion 0.6.10 usa por defecto `venv/bin/python` y el comando POSIX `ps`, ambos incompatibles con Windows. Se añadió un patcher aislado `companion/windows_video_jobs_compat.py` que preserva su fuente y cambia a `venv/Scripts/python.exe` y `taskkill /T /F`. Compila con el source exacto; **no se ha ejecutado sobre Windows real**.
- Preflight read-only `companion/windows_beta_preflight.ps1` para comprobar origen HTTPS exacto, versión, FFmpeg, trabajo en curso, SHA del Engine; no instalar ni cambiar Companion de Fernando sin su aprobación.

## Bloqueo humano concreto
Solo hay un dispositivo Desktop Commander conectado: Oracle. El Windows personal **NO está accesible** por ese conector; no se puede certificar su versión, el renderer local, su CORS al origen `https://montara-owner.memoriainvalida001.workers.dev` ni el empaquetado Windows desde GCP. El Companion de Chema por defecto autoriza localhost, trycloudflare y vercel, **no el workers.dev propio**; para su instalación habrá que configurar `MONTARA_COMPANION_ORIGINS` con el origen exacto sin alterar las otras opciones y verificar los renders pendientes antes de actualizar.

**Próximo movimiento SMART:** pedir a Fernando únicamente un GET read-only `http://127.0.0.1:47820/health` con `Origin: https://montara-owner.memoriainvalida001.workers.dev`, obtener versión, renderer, busy y rechazo CORS. Si hay que actualizar, preparar prueba Windows aislada/instalador compatible antes del Hito 4. No volver a crear laboratorios generales.

**Regla:** ninguna integración `main` antes del test humano, y después integración escalonada.
