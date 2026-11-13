# Montara — entrega a main: Owner multiusuario + Companion + Stage validado
**Fecha:** 2026-11-13 · **Preparado por:** rama `fernando/chema-native-owner` · **Destino:** revisión conjunta Chema/Fernando y PRs pequeños sobre `main` · **Estado:** plan y contrato, NO fusionado ni desplegado en main.

> **Mensaje de apertura para la revisión de Chema:** El editor de Stage/Push/Show debe verse y comportarse como el editor original; bajo la interfaz, la beta H4 cambia la arquitectura: identidad Google validada, catálogo de proyectos por dueño en SQLite, sesiones revocables, Engine/worker privado y autorización por propietario en cada acceso. No portar una ruta del editor saltándose el gateway Owner ni volver a un proceso único que comparta estado de usuarios. Antes de cambiar login, proyectos, edición, media o render, revisar los informes de auditoría de integración y los tests de propietario/aislamiento. Si algo falla, corregir en la capa correspondiente conservando esos contratos, no desactivar temporalmente el control de acceso. El funcionamiento visual idéntico no demuestra que el aislamiento sea correcto.

## 0. Evidencia que permite empezar la integración

- Validación humana REAL el 13/11/2026: navegador Windows → URL H4 → Google OAuth → proyectos → editor Chema → Stage Footage → edición de toma → export original mediante Companion Windows 0.6.10 y Engine pinned `b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b` → MP4 local reproducido y comprobado de imagen y audio. 122 segmentos, archivo final 635117659 bytes. Nunca subir originales al servidor por defecto.
- El MSIX 0.6.11.1 Windows era una prueba parcial: instaló bandeja y corrección del progreso `WinError 5` pero NO el servicio Companion. El usuario obtuvo el MP4 arrancando el servicio existente `smart_beta_launcher.py` directamente con Python. 0.6.12.0 CI compila bandeja + servicio empaquetado sin selector de Python, pero **no está validado aún en Windows real ni publicado con firma de actualización persistente**. No presentar MSIX parcial como producto completo.
- Documento de la prueba: `docs/integration/MONTARA_FIRST_REAL_STAGE_MP4_H4_WINDOWS_2026-11-13.md`.
- Registros Windows: algunas conexiones HTTP localhost abortadas por cliente `ConnectionAbortedError / WinError 10053` al responder health y transmitir MP4; no invalidaron el MP4 final, pero necesitan manejo sobrio de `BrokenPipeError`, `ConnectionResetError`, `ConnectionAbortedError` en el HTTP del Companion, sin ocultar errores reales de disco/red. Probar que un cliente que corta una descarga no bloquea el servidor.
- Editor: en `cut-editor.js` tras guardar toma se invoca `refreshFrames(true,index)`; Engine reprograma pendientes de toda la galería y puente Owner espera blobs privados. Diagnóstico y gate: `docs/integration/H4_REVIEW_DELTA_AFTER_SHOT_SAVE_2026-11-13.md`. El usuario reporta espera duplicada, **no cerrar sin una regresión real**.

## 1. Estado real frente a main (verificado 2026-11-13)

- `main@5d65ec3538723b154cdac3efb6942def8c389200`; `fernando/chema-native-owner` está 209 commits ahead, 0 behind en la consulta inicial. **NO fusionar directamente esos commits**: contienen ensayos, scaffolds y artefactos de pruebas que no son contratos de producto.
- PR histórico `#189` (Fernando integracion → main): handoff, no merge masivo. Aprovecharlo como coordinación y actualizar referencias, no aprobarlo como todo-en-uno.
- PR de Chema `#211`: chequeo de versión Engine/Companion antes de editar; no reimplementar en paralelo. PRs JM/Companion recientes y pendientes pueden evolucionar mientras se prepara el merge; revalidar el HEAD de main justo antes de cada PR.
- `main` ya tiene `/montara/companion/version` y `/montara/companion/download` en `app.py`: la descarga sirve un **.pkg de Mac** desde `DATA_ROOT/Installers/Montara-Companion-<engine8>.pkg` solo si coincide el Engine. No reemplazar este contrato por links a GitHub ni por un ejecutable desconocido.
- Interfaz `web/montara.js` hoy limita `companionOffer`, `checkCompanionUpdate()` y recuperación a `isDesktopMac`; Windows ve solo texto genérico de contactar administrador.

## 2. Diseño UX y distribución Companion (común Mac/Windows)

**Objetivo:** al entrar a Footage/Stage, y antes de editar o exportar, detectar `/health` de localhost, compatibilidad del Engine esperado y sistema operativo; ofrecer instalador relevante del servidor cuando falta o es incompatible, sin bloquear navegación básica ni interrumpir un render activo.

1. Descubrimiento de sistema: usar señales del navegador para UI (Windows x64, Mac, y fallback "Otro sistema"), sin considerarlas prueba criptográfica de arquitectura ni autorización. `navigator.userAgentData?.platform` cuando exista y fallback conservador `navigator.userAgent`; la app/instalador validará su plataforma y arquitectura REAL. No atribuir x64 a todo Windows ni descargar el paquete incorrecto.
2. API pequeña versionada **en mismo origen HTTPS de Montara**, por ejemplo `GET /montara/companion/releases`: plataforma/arquitectura, versión app, versión Engine exigida, SHA256, tamaño, estado de firma, nombre, URL de descarga interna y estado `available/unavailable`. Evitar dar enlaces si no existe paquete validado.
3. Descarga desde **nuestro servidor** (misma web o almacenamiento tipo Cloudflare R2 protegido por reglas de publicación), sin exigir GitHub al tester. Opciones de alojamiento: directorio privado de artefactos firmados bajo servidor/Cloudflare R2; proxy/edge con cuotas. **No usar la VM de 96GB como repositorio infinito ni incluir originales de usuarios**; un .msix/.pkg por arquitectura, retención limitada y checksum verificable.
4. No entregar un placeholder ejecutable ni un ZIP que intente instalar certificados o ejecutar PowerShell silenciosamente. Si Mac/Windows aún carece de firma/validación, UI honesta de prueba ("aún no disponible" o download manual para testers autorizados). La instalación requiere aprobación explícita del SO. No desactivar SmartScreen/Defender ni pedir confiar en raíz genérica.
5. Windows: ejecutar Companion empaquetado, estado y menú Montara, tray, arrancar una sola instancia; preservar `%LOCALAPPDATA%/MontaraSMARTBeta` durante migración controlada, no originales. Firmar MSIX con identidad de editor **persistente** almacenada de forma segura fuera de GitHub y accesible solo a CI de release autorizada. Habilitar update real solo cuando funcione validación y rollback; nunca confundir CI PASS con release para usuarios.
6. Mac: reaprovechar .pkg/LaunchAgent que construye Chema. Coordinar con su rama y PRs activos para no duplicar instalador, corrigiendo permisos y runtime según sus propios tests. No exigir que Mac use Windows path.
7. Tras instalar: no redirigir a GitHub; botón **"Volver a comprobar Companion"** que verifica versión y Engine en localhost. Si incompatible, indicar versiones exigidas. Si el navegador sigue sin acceso a localhost, explicar permiso y ofrecer diagnóstico concreto.

## 3. Multiusuario: lo que cambia SIN cambiar el editor visible

- **Identidad:** Google Authorization Code + PKCE, nonce/state one-use, correo verificado y allowlist en H4. Cookie de sesión `Secure`, `HttpOnly`, `SameSite=Lax`; sesiones revocables y CSRF en mutaciones. H4 beta privada: TTL de 10 días para nuevas sesiones, no heredar política a producción sin analizar riesgo.
- **Proyecto:** catálogo SQLite por dueño; URLs y botones del editor no sustituyen la autorización. Ningún ID/UUID/nombre de proyecto permite abrir uno de otra cuenta. Consultar `urano/google_owner.py`, `urano/project_catalog.py`, `urano/native_owner_project_scope.py`.
- **Editor:** es el editor real de Chema, servido bajo el origen privado Owner. El adaptador `urano/native_owner_browser_bridge.js` reescribe **solo** rutas admitidas, conserva CSRF y generación de Engine. No agregar endpoints bypass "temporalmente" para resolver errores visuales. Revisar `urano/native_owner_web_gateway.py`, `urano/native_owner_stage_http.py`, tests del gateway.
- **Worker/Engine:** iniciar el Engine de la cuenta autorizada y su workspace privado. Broker restringido, comunicación por sockets locales/descriptor, identidad vinculada a cada trabajo; evitar regresar a Engine global con estado compartido. Revisar `urano/private_broker_service.py`, `urano/private_owner_admission.py`, `urano/private_stage_owner_admission.py`, `urano/native_owner_worker_binding.py`, `urano/native_owner_workspace_gate.py`.
- **Media/almacenamiento:** originales y MP4 final permanecen locales vía Companion cuando hay fuentes originales. Proxies autorizados pueden sincronizarse; no dar a un usuario descriptor/ruta/preview de otro. Probar Range, HEAD, reanudación, memoria y límites. Ficheros finales locales no dependen de session cookie del servidor después de completarse.
- **UI:** igual visualmente, pero proyecto, historial, recuperación tras reload, guardado, edición, render y descargas cambian de ámbito y permisos. Mantener los comportamientos originales de Stage/Push/Show; cualquier ajuste del editor de Chema debe reproducir la validación Owner con dos usuarios.
- **Aislamiento por defecto:** nunca confiar en user_id, project_id, rutas o generación recibidos desde navegador. Validar usuario a partir de sesión autorizada y cada operación en backend. No divulgar token del HTTP local ni añadir endpoints de lectura de disco arbitraria por comodidad.
- **Temporalidad:** respetar limpieza de datos efímeros del servidor y conservación de resultados locales; no borrar ningún proyecto privado real durante migración de SQLite.

## 4. Orden de PRs sugerido

A. **PR Foundation Owner:** login Google + SQLite + sesión + catálogo + scopes por usuario y broker mínimo, tests C1/C2 y matriz 2 usuarios. Feature flag de acceso privado; rollback sin afectar editor anónimo antiguo. Mantener infraestructura provider-agnostic: GCP es VM de prueba, no contrato de producto.

B. **PR Stage Owner adapter:** integrar navegador real de Chema sin reescribir el editor y habilitar rutas Owner al worker privado, pruebas E2E de proyectos, frames, modificación de toma, cancelar, reconstruir worker, export y MP4 local. Corregir doble espera de miniaturas en módulo acotado, con revisión de Chema y sin invalidar cachés ajenas.

C. **PR Companion distribution/Windows+Mac:** extensión de los endpoints existentes de descarga, manifiesto por SO + Engine + hash; UI de instalación/revisión, firma persistente de Windows y .pkg de Chema, mantenimiento del parche progreso y manejo suave `WinError 10053`. **No bloquear A/B por el diseño definitivo del instalador**: la beta puede mostrar aviso honesto y enlace solo cuando el instalador haya pasado gate.

D. **PR Operational docs/deployment:** Cloudflare, base de datos, servicios, secretos, backups, observabilidad, retención, rollback, costes y matriz de aceptación; activar portal privado en el entorno acordado, sin alterar infra existente en producción.

Cada PR debe: diff pequeño, tests, owner de revisión, plan de rollback, comparación con main actualizado, no tocar submódulos Engine/Mixer pinned sin motivo y aceptación explícita del equipo. Puede convenir dividir B y C si su tamaño crece.

## 5. Gate para fusionar en main

- [ ] Chema revisa que la UX no se rompa ni se reimplemente, y alinea el PR #211 y sus otros cambios.
- [ ] Seguridad: sesión, CSRF, Google real, proyectos privados, workspace, worker, previews, audio, descargas con pruebas de dos usuarios y acceso cruzado DENEGADO.
- [ ] E2E Stage completo en entorno staging con usuario Windows y Mac previstos, primera vez y regreso; reproducción del MP4 final y bytes locales.
- [ ] UI de descarga diferenciada por SO, solo binarios realmente disponibles y con checksum/firma verificados; bloqueo si Engine incompatible; rehacer rutas local cuando carpeta antigua existe.
- [ ] No upload de originales, ni exposición de carpeta del PC desde web, ni almacenamiento perpetuo de temporales en VM.
- [ ] Revisión de errores `WinError 10053` y doble trabajo de fotogramas; el usuario no espera innecesariamente una segunda galería de 122 imágenes.
- [ ] Rollback demostrable a main anterior, migración sin destrucción, monitorización de recursos y configuración de acceso.
- [ ] Documentación adjunta en PR: diferencias invisibles a la interfaz; enlaces a auditorías, pruebas y rutas de cada módulo.

## 6. Investigación diferida, no bloqueante de primer merge

Perf render local: hilos FFmpeg, máximo trabajadores, 8 GB RAM, 360, cache reusada por segmento, calidad de salida, datos de máquina. UI barras verdes son CSS estado y no motores FFmpeg extra. Mejora UX resultado: «Mostrar en carpeta» primero, «Guardar otra copia» después; el MP4 se genera directamente en el directorio seleccionado, actualmente pulsar Descargar crea una copia del archivo local.

**Regla de integración:** si hay incertidumbre, crear una prueba y revisar la auditoría correspondiente. No retirar los controles para hacer que un botón vuelva a funcionar. El objetivo es integrar la capacidad en `main`, no replicar los laboratorios ni rehacer el editor de Chema.
