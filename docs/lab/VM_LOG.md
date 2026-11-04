# Registro de administración de la VM de pruebas

Una línea por acción de administrador (`sudo`). Sin contraseñas, tokens ni llaves.

| Fecha (UTC) | Quién | Autorizó | Acción |
|---|---|---|---|
| 2026-11-03 | Codex | Chema | Preflight inicial 0.60 de JM: árbol limpio, ningún proceso multimedia y ninguna sesión bloqueada; sin cambios a FER. |
| 2026-11-03 | Codex | Chema | Segunda comprobación 0.60 de JM, ahora con estado autenticado del wizard: `waiting_review`, sin procesos ni locks. |
| 2026-11-03 | Codex | Chema | Repetición inmediatamente anterior a instalar 0.60: JM limpio y libre; wizard `waiting_review`. No se canceló ninguna exportación del usuario. |
| 2026-11-03 | Codex | Chema | Instalación solo JM fijada a `5a65f509a7b7c2ac628fd8fcb455df119d38f3c2`; submódulos exactos, preflight/warmup y reinicio de su servicio `:8101`. FER sin cambios. |
| 2026-11-03 | Codex | Chema | Verificación autenticada posterior: 0.60 `5a65f50`, engine `affe97a4`, mixer `f15ff91c`, HTML y scripts servidos correctamente. |
| 2026-11-03 | Codex | Chema | Lectura autenticada del estado del trabajo JM antes de preparar 0.60: `waiting_review`, sin exportación en curso; sin cambios a FER ni medios. |
| 2026-10-29 | Claude (vía Cloud Shell de amehc) | Chema | `deploy/vm/admin_setup.sh`: paquetes del sistema, usuarios `jm` y `fer` (HOME en 750, linger), bloqueo `montara-bench` |
| 2026-10-29 | Claude | Chema | Instalación de Montara para `jm` (`claude/jupiter-gcp-vm`, servicio de usuario en `127.0.0.1:8101`) |
| 2026-10-29 | Claude | Chema | `deploy/vm/lab_logins.sh`: usuario de acceso propio para `jm`; instalación de `fer` copiada del checkout de `jm`, en `127.0.0.1:8102` |
| 2026-10-30 | Fernando (`fgardel00`) | Fernando | Checkout experimental `/home/fer/montara-jupiter` con su propio entorno; sin servicios nuevos (según JÚPITER-GCP-01) |
| 2026-10-30 | Claude (comando pegado por Chema) | Chema, a petición de Fernando | Copia de los originales más grandes de `/home/jm/montara-data` a `/home/fer/lab-clips/originales` (propietario `fer`) |
| 2026-11-02 | Codex | Chema | Read-only JM checkout status before opening the test tunnel. |
| 2026-11-02 | Codex | Chema | Read-only JM commit verification before opening the test tunnel. |
| 2026-11-02 | Codex | Chema | Read-only JM session timing lookup for the reported audio. |
| 2026-11-02 | Codex | Chema | Read-only saved local-mix plan lookup for audio diagnosis. |
| 2026-11-02 | Codex | Chema | Read-only JM media-worker activity and working-tree check. |
| 2026-11-02 | Codex | Chema | Rechecked JM inactivity and clean working tree immediately before the update. |
| 2026-11-02 | Codex | Chema | Ran existing montara-update for jm only: main 9d4a560, user service on 127.0.0.1:8101; no FER service changes. |
| 2026-11-02 | Codex | Chema | Read-only authenticated verification of JM version, served page/scripts and mixer policy after the update. |
| 2026-11-02 | Codex | Chema | Read-only JM working-tree/media-process check and nonblocking session-lock probe before the metadata-only update; clean tree, no active jobs, FER untouched. |
| 2026-11-02 | Codex | Chema | Rechecked JM clean tree, media processes and session locks immediately before installing 0.58; no active work, FER untouched. |
| 2026-11-02 | Codex | Chema | Ran existing montara-update for JM only: main f902ccc (PR #66), private service 8101; no FER changes. |
| 2026-11-02 | Codex | Chema | Authenticated JM version verification succeeded; a check incorrectly expected version text inside static HTML, so this attempt stopped before checking the download. |
| 2026-11-02 | Codex | Chema | Repeated authenticated version/HTML and previous-session MP3 download verification with the corrected HTML check: 0.58 f902ccc, no tags/artwork, compressed audio packets unchanged. |
| 2026-11-02 | Codex | Chema | Read-only recent JM video-project inspection for lighting audit; latest two-video project found, older-record scan stopped on missing-path permission error; no service/project edits. |
| 2026-11-02 | Codex | Chema | Extracted six bounded before/after frame samples and read existing colour statistics from JM latest project; gamma 1.25 comparison only, no source changes or FER access. |
| 2026-11-02 | Codex | Chema | Extracted two midpoint gamma 1.65 comparison frames for lighting audit; candidates only, originals and live settings untouched. |
| 2026-11-02 | Codex | Chema | Extracted two midpoint tone-curve comparison frames; inspected locally, no project settings, engine or service changes. |
| 2026-11-02 | Codex | Chema | Read-only detailed JM project/coverage/edit-plan/export inspection: two source durations and overlap verified, proxy-derived final identified; no user project or FER changes. |
| 2026-11-03 | Codex | Chema | Read-only JM export-manifest index/schema scan (three retained exports) to answer Fernando’s historical telemetry request; no projects, services or FER changes. |
| 2026-11-03 | Codex | Chema | Read-only duration/performance summary of the same three JM manifests; historical 628.2 s manifest absent, no render launched or media changed. |
| 2026-11-03 | Codex | Chema | Read-only JM preflight before 0.59: clean checkout and one matching media process; no deployment performed. |
| 2026-11-03 | Codex | Chema | Read-only JM preflight repeated with shell processes excluded; no service or project changes. |
| 2026-11-03 | Codex | Chema | Read-only JM process/worker-lock check: one actual FFmpeg process active, no locked session; left it running and deferred deployment. |
| 2026-11-03 | Codex | Chema | Read-only JM preflight after acceptance: clean checkout, four active FFmpeg processes, no locked audio session; left the render running and deferred restart. |
| 2026-11-03 | Codex | Chema | Rechecked JM checkout, FFmpeg activity and worker locks while preparing rollout: four FFmpeg workers still active; no restart. |
| 2026-11-03 | Codex | Chema | Authenticated read-only JM wizard status: export running at 77.75% overall, 25.82% export-stage progress; no project edits. |
| 2026-11-03 | Codex | Chema | Authenticated read-only JM wizard check: previous export completed at 100%; no cancellation. |
| 2026-11-03 | Codex | Chema | Final JM preflight: clean checkout, zero active media workers and no locked audio sessions; FER untouched. |
| 2026-11-03 | Codex | Chema | Existing montara-update installed main 662c06a (0.59 plus browser history #69) for JM only, service 8101; no FER or global FFmpeg changes. |
| 2026-11-03 | Codex | Chema | Authenticated post-update version/HTML/script verification: 0.59, engine 5877eacb, mixer f15ff91c; companion 0.6.0 verified separately on the Mac. |

| 2026-11-04 | Codex/JM | Chema: diagnóstico y limpieza | `sudo -u jm`: inventario de disco y diagnose.py, solo lectura; 48 GiB usados, 49 libres, datos JM ~28 GiB; sin borrar ni alterar FER. |

| 2026-11-04 | Codex/JM | Chema: biblioteca compartida de pruebas | Un `sudo bash`: creado grupo montara-media y directorio compartido `/srv/montara-lab/media` (2770), añadidos JM y FER al grupo; no se movieron ni borraron originales ni se reinició FER. |

| 2026-11-04 | Codex/JM | Chema: carpeta común de ensayos | Un `sudo bash`: comprobado acceso lectura/escritura/recorrido con `runuser` para JM y FER; ambos OK. Sin acceso a sus archivos ni cambios de servicio. |

| 2026-11-04 | Codex/JM | Chema: actualización 0.61 | `sudo -u jm`: preflight de solo lectura; checkout limpio, cero procesos multimedia y sesiones bloqueadas, wizard done; nada reiniciado. |
| 2026-11-04 | Codex/JM | Chema: actualización 0.61 | `sudo -u jm`: segundo preflight inmediatamente antes de instalar; mismos resultados, trabajo del usuario conservado. |
| 2026-11-04 | Codex/JM | Chema: actualización 0.61 | `sudo -H -u jm bash`: fetch previo al despliegue; detenido por comprobación de referencia origin/main antigua, antes de checkout o reinicio. |
| 2026-11-04 | Codex/JM | Chema: actualización 0.61 | `sudo -H -u jm git log`: diagnóstico de solo lectura de origin/main; confirmada referencia antigua; FER intacto. |
| 2026-11-04 | Codex/JM | Chema: actualización 0.61 | `sudo -H -u jm bash`: fetch con refspec explícito, fast-forward main 58e4134, submódulos fijados y user_install offline; reiniciado solo JM:8101, retención 60 GB habilitada. |
| 2026-11-04 | Codex/JM | Chema: actualización 0.61 | `sudo -u jm`: verificación autenticada HTTP/version/scripts/pines y configuración de retención tras instalar; sin tocar proyectos ni FER. |
| 2026-11-04 | Codex/JM | Chema: abrir versión nueva | Primer intento de verificación SSH no llegó a ejecutarse: VM TERMINATED. `montara-start` la encendió y reutilizó el túnel; segunda verificación sudo registrada arriba completada. Página 0.61 abierta, Companion 0.6.2 verificado; FER no reiniciado por nosotros. |
