# URANO U14 — Auditoría de integración sin uso de la VM

**Fecha:** 2026-11-07. **Estado:** revisión estática de GitHub y plan de aceptación; NO es una implementación, aprobación de seguridad ni prueba E2E. Base exacta: `main` commit `5becd9e9d418b404fe7d4a4b5e15d05ddd8a66e1` (PR #107). Este documento no altera runtime, datos ni servicios.

## 1. Hallazgo prioritario: el producto evoluciona más rápido que nuestra prueba nativa

- PR #107 ya integrada en main: Stage **selecciona automáticamente las cámaras con sincronización de audio demostrada**, excluye cámaras sin correspondencia o mudas salvo `Filler · no sync` explícito, y exige al menos una cámara emparejada. Se elimina el diálogo de revisión manual por cámara. Fuente: https://github.com/amehcgracia-byte/Montara/pull/107.
- Nuestro borrador [#104](https://github.com/amehcgracia-byte/Montara/pull/104), `fernando/urano-u13e2b-native-real-footage-e2e`, nace de `main` posterior a #100, **antes** de #107. Reutiliza `tests/e2e_native_stage.py`, cuyo flujo de base pasa del upload a la selección de cámaras y luego a frames/edición/export. **No asumir compatibilidad con la nueva selección automática.**
- Por tanto, antes de ejecutar medios reales: comparar selectors/flujo `#104` con #107, identificar si hay que adaptar el test (no la interfaz de Chema), repetir suite de aceptación de Stage en CI sobre una rama derivada de main reciente y preservar escenarios: cámara emparejada, cámara no relacionada, filler explícito, error sin ninguna cámara emparejada. Ninguna de estas pruebas es evidencia de sincronía con las muestras reales hasta ejecutarlas.

## 2. Mapa de piezas verificadas en código/documentación

| Pieza | Evidencia revisada | Estado y brecha real |
| --- | --- | --- |
| Catálogo, cuentas y UI histórica | `urano/project_catalog.py`, `urano/http_projects.py`, `urano/http_auth.py`, `urano/lab_app.py`, `tests/e2e_urano_dashboard.py`; integración selectiva #100 | Catálogo SQLite por propietario, sesiones opacas/CSRF, test HTTPS de dos usuarios y recuperación de notas. **Rutas solo en app de laboratorio, no en la web principal**. No abrir en Internet. |
| Apertura del Engine por usuario | PR #91 (`engine_bindings.py`), #92–#94 runtime/subprocess | Validación interna del vínculo UUID → carpeta Engine y control de ocupación, sin ruta HTTP pública segura ni integración editor/cuenta. El Engine original mantiene proyecto activo por instancia. |
| Aislamiento OS y concurrencia | PR #95–#98; `urano/container_isolation.py` en #96 | Contenedores aislados, límites CPU/RAM, rootfs read-only y pruebas con Engine real en CI; **no demuestran** aún web/Companion+Engine multiusuario con exportación y recuperación. |
| Ingest y material real | #99, #102 y #104 | #99 usa medios sintéticos dentro de Docker; #102 realiza preflight de originales; #104 adapta el E2E nativo para dos cámaras + máster. **No hay export comprobada de iPhone/Sony/360 reales**. |
| Cuenta Google | Issue #34, comentario 6697777881 | Solo diseño OIDC: Authorization Code+PKCE, validar token en backend, sesiones/allowlist. **No hay implementación ni beta publicada**. |
| Infraestructura | `docs/lab/URANO_U9_GCP_FER_INVENTORY_SAFE_ALIGNMENT_2026-11-06.md` y handoff | GCP es laboratorio temporal por créditos, no compromiso de proveedor; preservar portabilidad Linux/VM y el sistema local-first. |

## 3. Criterios de aceptación que faltan (orden sugerido)

**P0, antes de nuevos renders:** reconciliar #104 con la rama principal tras #107; vigilar selección automática de cámaras y ajustes Stage; preparar tests/regresiones ligeras en GitHub Actions. No hacer rebase destructivo ni fusionar la pila de PR #91–#99.

**P1, integración mínima y reversible:** desde una rama limpia de `main`, conectar propietario verificado → proyecto UUID → vínculo Engine autorizado → worker privado. No aceptar rutas físicas/owner del navegador. Demostrar que dos identidades no pueden abrir ni exportar el proyecto ajeno incluso manipulando IDs, recetas y solicitudes; casos de revocación, expiración y fallo del worker. Esta pieza debe ir en PR selectiva, sin tocar submódulos ni servicio de JM.

**P2, E2E real integrado:** web → sesión → proyecto propio → Companion → Engine → editar → exportar → cerrar sesión → recuperar proyecto antiguo y medios. Incluir dos propietarios, recuperaciones tras interrupción y ausencia del original local; afirmar `aprobado` solo tras archivos resultantes decodificables y revisión visual/auditiva. Separar Stage de Push/Show; no extrapolar resultados.

**P3, beta:** HTTPS, OIDC Google para acceso privado, allowlist y secretos fuera del repositorio, límites de abuso/datos, permisos y retención; no desplegar antes de P1/P2 y una revisión ligera de seguridad.

## 4. Restricciones de laboratorio vigentes

El 07-11, por Gateway, el disco GCP se observó al 100%, con alrededor de 519 MB libres; `/home/jm/montara-data` concentra ~75 GB, principalmente `Uploads`; no hay Docker instalado en la VM. Las pruebas Docker anteriores fueron en GitHub Actions. Existen originales de iPhone/Sony/360 y MP3 maestro en `/home/fer/lab-clips/originales`, pero la falta de espacio impide ensayos de render seguros. No copiar, subir a Actions, eliminar ni mover originales; no generar proxies, renders ni nuevos checkouts en GCP hasta recuperar margen. **Auditar código/CI desde GitHub no consume espacio de esta VM.**

El coste por render y el futuro cloud (GCP/AWS/Azure/Oracle) se decidirán por datos de uso real con Companion y portabilidad; los créditos promocionales no cuentan como coste de producción. Auditoría genérica pequeña de seguridad del servidor **aplazada** (SSH, TLS, secretos, mínimo privilegio, aislamiento propietario, límites, backups y portabilidad), documentada en el handoff.

## 5. Qué no se ha probado con esta revisión

No se han ejecutado tests nuevos, ni reconciliado selectores #104↔#107 mediante una ejecución. No se han validado los dos usuarios con el editor real, el fin del render, el relink de Companion ni salida final con vídeos reales. El estado verde previo de CI no acredita estos puntos. **Siguiente intervención implementable:** una PR estrecha de regresión/adaptación Stage desde `main` actual con tests CI, antes de una E2E con vídeo real.

**Fuentes:** [#100](https://github.com/amehcgracia-byte/Montara/pull/100), [#104](https://github.com/amehcgracia-byte/Montara/pull/104), [#107](https://github.com/amehcgracia-byte/Montara/pull/107), [#34](https://github.com/amehcgracia-byte/Montara/issues/34), `docs/USER_PROJECT_FOUNDATION.md`, `docs/lab/STATUS-JM.md`. No se modifican `main`, Engine, Mixer, Companion, VM, DNS ni Cloudflare.
