# URANO U9 — Inventario FER en GCP y alineación segura con GitHub

**Fecha:** 2026-11-06. **Alcance:** inspección remota de solo lectura; ningún despliegue, limpieza, reinicio ni cambio de configuración. **No registrar credenciales, IP, usuarios personales, claves SSH ni detalles de acceso a Gateway.**

## 1. Convivencia prevista en la VM de laboratorio

La VM contiene **dos instalaciones separadas por usuario**, deliberadamente:
- `/home/fer/montara`: espacio de experimentación de Fernando; aplicación Python Gunicorn de revisión en un puerto de loopback exclusivo.
- `/home/jm/montara`: espacio de Chema; otra aplicación Gunicorn y puerto de loopback independiente.

Ambas responden HTTP **401 Basic** sin credenciales y no están expuestas como HTTP público directo. La concurrencia comparte CPU, RAM y disco de la misma VM. No desplegar ni cambiar el proceso de Chema desde el entorno FER. **Los datos multimedia y renders de cada persona quedan intactos; no realizar limpieza automática.**

## 2. Inventario comprobado

- Ubuntu 24.04, arquitectura x86-64, **8 vCPU y aproximadamente 31 GiB RAM**.
- Python, Git, FFmpeg, Node y npm presentes. Docker no instalado (no asumir su necesidad).
- Sistema de archivos aproximadamente **96 GB**, con **85–86 % ocupado** en el muestreo. Directorios de trabajo en `/home` concentran la mayoría; esto se conoce y **no justifica borrar contenidos**.
- FER: `/home/fer/montara` contiene `web/`, `deploy/`, `engine/`, `mixer/`, `local_media/`, `tests/`, `deployment/vercel/`. Submódulos locales observados: Engine `c89e779`, Mixer `c7a46a6`.
- El servicio de FER ejecuta `deploy.entry:app` con Gunicorn; su entrypoint documenta explícitamente *single worker* porque el motor original posee un **solo proyecto actual**. **No confundir esta VM de revisión con backend SaaS multiusuario ni con la demo Vercel Sandbox.**

## 3. Divergencia importante entre servidor y repositorio

Al inspeccionar **sin hacer fetch ni pull**:
- Checkout FER en rama `claude/jupiter-gcp-vm`, commit `78e9e67c335f` (2026-10-29).
- Los siguientes cuatro archivos están modificados localmente sin commit: `deploy/entry.py`, `deploy/healthcheck.py`, `deploy/restart_check.py`, `deploy/vm/user_install.sh` (**9 líneas añadidas y 5 eliminadas** en conjunto). No se ha inspeccionado ni divulgado contenido sensible del diff.
- En GitHub, la base compartida `main` recibió posteriormente las integraciones #79–#83, con últimos cambios conocidos en `4f1dceb904056abd8e3598ba7f356e5234f6c1df` (confirmar HEAD vigente antes de usarlo).
- El checkout de servidor no muestra `origin/main` entre sus refs locales actuales. **No ejecutar `git pull`, `reset --hard`, `clean`, ni sustituir este worktree**, porque podríamos perder ajustes de despliegue y porque contiene historia/pins distintos.

## 4. Plan mínimo de alineación sin interrumpir FER

1. Confirmar la referencia **actual** de `main` y sus pins Engine/Mixer por GitHub; identificar contratos web/Companion/proyectos relevantes para URANO v1.
2. Conservar el proceso y worktree actuales; preparar, si se necesita ejecutar código nuevo en VM, **un checkout aislado** con directorio de datos y puerto propios; medir espacio libre antes de clonar dependencias o medios.
3. Validar primero en CI los cambios y las pruebas de contrato (identidad de usuario ficticio, propiedad de proyecto, persistencia y reconexión de Companion). Nunca asumir que el servicio protegido por Basic ofrece cuentas SaaS.
4. Para un eventual cutover del servicio FER: documentar diferencias de configuración (sin secretos), establecer prueba de salud, rollback y ventana de cambio; no ejecutar hasta contar con evidencia.
5. El laboratorio Cloudflare y su autorización GitHub son opcionales/no bloqueantes. Vercel estable del propietario no se modifica.

**Criterio de prioridad:** construir primero el flujo de URANO v1 web → identidad/proyecto → fuentes/Companion → Engine/Mixer → edición/exportación → recuperación; después valorar GPU, scheduling y costes. La VM es un laboratorio, no un contrato de infraestructura final.
