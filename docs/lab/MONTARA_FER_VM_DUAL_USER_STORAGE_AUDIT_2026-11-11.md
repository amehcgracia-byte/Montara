# MONTARA — Diagnóstico de dos cuentas Fernando y espacio en VM (11-11-2026)

## Propósito
Responder si `/home/fer` y `/home/fgardel00` son duplicaciones causadas por TryGateway, Desktop Commander o Cloudflare. Inspección **solo lectura**, sin detener servicios, borrar, mover ni cambiar la infraestructura.

## Resultado
- Son **dos cuentas Linux distintas**: `fer` UID 1005 y `fgardel00` UID 1006. No son dos sesiones interactivas idénticas ni dos montajes de un mismo home.
- `fer`: entorno histórico Júpiter/laboratorio y un servidor Gunicorn **ACTIVO en 127.0.0.1:8102**. Por ello no clasificar la cuenta o su código como obsoleto.
- `fgardel00`: entorno actual de integración con Owner beta 8115 y túnel Cloudflare como servicios user-systemd activos. Acceso actual SSH desde Oracle usa `fgardel00`. Cambio de método de conexión no genera por sí mismo 11GB: el tamaño procede fundamentalmente de worktrees, laboratorios y dependencias.
- **No hay evidencia de causalidad directa de TryGateway/Remote ni de Cloudflare para la duplicación de GB.** Faltan fechas de creación precisas de ambas cuentas para reconstruir causalidad histórica.

## Mediciones físicas
- Volumen raíz `df -h /`: aprox. 96G utilizables, 56G usados, 41G disponibles (58%). Cifras móviles.
- `sudo du -sxh /home/fer` ≈13G; `/home/fgardel00` ≈11G (cifras redondeadas en unidades de du, no confundir con GB decimales).
- `fer`: `lab-clips` 6.3G; `montara-jupiter` 2.1G; `.cache` 2.1G (uv ~1.2G, Playwright ~924M); `montara-data` ~573M (cache ~464M, runtime ~109M); `montara` ~561M; `montara-merge-lab` 269M; `montara-e2e-01` 208M; `montara-backups` 205M. Este usuario tiene procesos Gunicorn en 8102 activos.
- `fgardel00`: 24 directorios `montara-integration-*` identificados, normalmente ~178–179M cada uno; laboratorios `urano-u13e2c...` ~1.4G, `urano-u13e2d...` ~629M; `montara-personal-beta` ~1.8G; `montara-personal-beta-data` ~594M; `montara-owner-beta` registrado con tamaño variable entre lecturas debido a posibles enlaces, `.cache` 1.3G (uv ~1.3G).
- **Cuidado de contabilización:** los worktrees y entornos comparten o enlazan archivos en algunos casos; sumar `du` por subcarpeta puede doble contar hardlinks y variar según el orden de recorrido. No presentar sumas de subárboles como facturación exacta ni confundir directorios con procesos.
- `jm` ocupa ~22G con `montara-data` ~16G; compartido `montara-main` ~4.4G. No intervenir.

## Clasificación inicial, todavía no política de borrado
- **Activo/operativo:** `/home/fer/montara` (servicio 8102), `/home/fgardel00/montara-owner-portal-release`, servicios Owner/túnel, datos de Owner y broker en `/opt/montara`; catálogos y proyectos.
- **Histórico por evaluar:** directorios Júpiter, `lab-clips`, 24 worktrees de integración, labs E2E/URANO, backups, pruebas, cachés uv y Playwright. Sin auditar enlaces, pin de tests, ejecución reciente y servicios, **no borrar**.
- Cloudflare Pages/Workers no se aloja como volumen de datos de usuario bajo estos homes; túnel local y código/herramientas pueden ocupar espacio menor, pero no hay evidencia de que expliquen los 24G observados.
- Acceso Desktop Commander → Oracle → SSH usa el usuario `fgardel00`, mientras `fer` conserva recursos creados anteriormente. La coexistencia no demuestra fallo.
- No se hicieron cambios destructivos.

## Política futura sujeta a decisión
- Modelar proyectos por modalidad (Stage/Push/Show), metadatos/recetas y decisiones persistentes; originales local por defecto; cachés regenerables con medición y cotas; export MP4 preferentemente local.
- Considerar **ventana opcional de hasta 24 h** de disponibilidad del MP4 servidor solo donde sea realmente necesaria y tras medir coste y capacidad; no establecer por defecto ni ejecutar limpieza sin aprobación.
- Auditar el estudio previo de orquestación/híbrido antes de diseñar otro scheduler, sin atribuciones individuales no verificadas.
- Próximo inventario posible: dependencias y consumidores de los 24 worktrees y `lab-clips`; resultado será informe de candidatos, no borrado automático. Pedir autorización antes de cualquier limpieza, cambio de cuenta o parada del 8102.
