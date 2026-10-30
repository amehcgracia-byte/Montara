# Registro de administración de la VM de pruebas

Una línea por acción de administrador (`sudo`). Sin contraseñas, tokens ni llaves.

| Fecha (UTC) | Quién | Autorizó | Acción |
|---|---|---|---|
| 2026-10-29 | Claude (vía Cloud Shell de amehc) | Chema | `deploy/vm/admin_setup.sh`: paquetes del sistema, usuarios `jm` y `fer` (HOME en 750, linger), bloqueo `montara-bench` |
| 2026-10-29 | Claude | Chema | Instalación de Montara para `jm` (`claude/jupiter-gcp-vm`, servicio de usuario en `127.0.0.1:8101`) |
| 2026-10-29 | Claude | Chema | `deploy/vm/lab_logins.sh`: usuario de acceso propio para `jm`; instalación de `fer` copiada del checkout de `jm`, en `127.0.0.1:8102` |
| 2026-10-30 | Fernando (`fgardel00`) | Fernando | Checkout experimental `/home/fer/montara-jupiter` con su propio entorno; sin servicios nuevos (según JÚPITER-GCP-01) |
