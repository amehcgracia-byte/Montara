# Registro de administración de la VM de pruebas

Una línea por acción de administrador (`sudo`). Sin contraseñas, tokens ni llaves.

| Fecha (UTC) | Quién | Autorizó | Acción |
|---|---|---|---|
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
