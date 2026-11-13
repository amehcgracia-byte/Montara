# I4 — Editor original de Chema sobre Owner/worker privado
**Fecha:** 2026-11-13 · **Origen:** `fernando/chema-native-owner` (beta H4) · **Destino:** `main` vía PR de cambios aditivos.

> **PARA CHEMA Y SU IA:** La apariencia de Stage/Push/Show y los controles del editor **no se reemplazan ni se rediseñan**. El cambio fundamental es invisible: login Google → sesión Owner → workspace SQLite privado → autorización del broker → proceso privado con media/recetas sólo del propietario. Los componentes integrados no reemplazan automáticamente `app.py` ni se despliegan al fusionar; sigue siendo necesaria la configuración controlada y las pruebas reales del conjunto. No dar por terminada la beta multiusuario solo porque el código esté en `main`.

## A. Novedades
- `urano/native_owner_app.py` compone en una Flask independiente el Google PKCE/OIDC de I2, el catálogo/registro de workspaces y el editor original Chema del `chema_web_root` verificado. No hay dashboard ni editor alternativo.
- `native_owner_browser_surface.py` entrega la página, JS/CSS y artefactos sólo tras sesión autenticada. `native_owner_browser_bridge.js` conecta navegación/edición existente, llamada al worker autorizado y previews privadas con token CSRF.
- `native_owner_web_gateway.py`, `native_owner_stage_http.py`, `native_owner_new_latest_http.py` y `owner_private_http_client.py`: API de edición original, nuevas sesiones, últimos proyectos y proxy HTTPS autorizado al WSGI del worker por transporte Unix/FD; no exponen el Engine directamente.
- `native_owner_workspace_registry.py` y `native_owner_workspace_gate.py`: asociación estable un workspace por propietario; autorización repetida para abrir, borrar, recuperar, medios y rutas del editor. No cambiar silenciosamente un proyecto legado de dueño.
- `native_owner_worker_binding.py`, `native_owner_worker_service.py`, `native_owner_project_scope.py`, `native_owner_stage_snapshot.py`, `native_owner_storage_guard.py`: selección y límites del proyecto nativo, servicio privado, estado Stage, lectura de exportación/media y denegación de symlinks/salidas ajenas; sin crear un proyecto ficticio al arrancar el worker.
- `c6_beta_preflight.py`, `jm_bundle_manifest.py`, `jm_private_proxy_overlay.py`, `first_valid_upload_gate.py`, `trusted_local_https.py`, `native_owner_trusted_wsgi.py`: verificaciones de origen, bundles fijados, parche privado y límites de subidas, configuración del operador y montaje WSGI.
- Pruebas copiadas de H4 para gateway, Stage, archivos, recuperación, permisos, dos propietarios y compatibilidad de interfaz; no se editaron submódulos.

## B. Duplicidades evitadas
- Se REUTILIZA la UI que mantiene Chema en `web/`; no se añade una segunda página de edición ni nuevos modos Stage/Push/Show.
- Se reutilizan Google+SQLite de I1/I2, admisión+ledger+systemd del I3a/I3b. Nada de Engine global para la versión Owner.
- No copiar `app.py` ni `companion/companion.py` de H4 sobre la versión más reciente de Chema.

## C. Reutilización del laboratorio validado
- H4 demostró entrada real Google, selección del editor original y exportación Stage con Companion local Windows y MP4 final visualizado por Fernando el 13-11 (635117659 bytes).
- Esta PR extrae la composición aislada desde H4 a `main`; no equivale a desplegar un servicio desde este commit ni a validar todos los sistemas contra la edición actual de Chema.
- Los paquetes originales permanecen locales cuando el Companion funciona; no subir media originales silenciosamente.

## D. Riesgos y dependencias pendientes
1. **Versiones de Chema:** H4 usa un `JM bundle` fijado. Al desplegar una nueva versión del editor de Chema, fijar y verificar el bundle correcto con su manifest, revisar PR #211–215 y contratos/miniaturas; no sobrescribir el editor moderno con el antiguo.
2. **Broker OS:** I3b está en `main` pero su servicio opt-in sigue sin desplegarse desde `main`. Para activar la solución, comprobar en VM permisos de usuario/socket/SQLite readonly, cgroups, cierres seguros y recuperación de dos usuarios.
3. **Flujo de medios:** se deben preservar los recursos por propietario. Validar el reanudado tras caída, streaming Range, guardado shot/miniaturas, audio y exportación. Los archivos locales nunca se deben subir por sorpresa.
4. **Companion:** compatibilidad Windows/Mac y enlace de descarga según SO (I5) pendientes. En Windows se validó el lanzamiento Python de SMART Beta, no un MSIX final firmado.
5. **Autoapagado:** política de 120 min de web/SSH cada 20 min; no retener VM por worker simplemente abierto. `TimeoutStopSec=3s` heredado necesita cierre cooperativo y pruebas antes de declarar segura la parada.
6. **CI sesión:** hay seis fallos de tests de iluminación/framing/perfomers ya observados antes de I3, documentados en issue #221; no falsear tests ni atribuirlos automáticamente al nuevo Owner.
7. El bridge se monta detrás de la autenticación configurada por operador; nunca se habilita `app.py` público con parámetros de usuario no verificados. La interfaz que parece idéntica ahora actúa por propietario: **todas las nuevas APIs/recursos deben respetarlo**.

## E. Pruebas realizadas y siguiente revisión
- Checkout Git temporal real de `fernando/integracion-i4-native-editor-20261113` en VM GCP, sin crear servicios ni cambiar despliegue: `PYTHONPATH=. /home/fgardel00/montara-owner-portal-release/.venv/bin/python -m unittest discover -s tests -p 'test_native_owner_*.py' -v` → **90/90 PASS**.
- `node --check urano/native_owner_browser_bridge.js` PASS; `node --test tests/test_native_owner_browser_bridge.cjs` → **1/1 PASS**.
- No se han ejecutado aquí el E2E Linux completo con capturas examinadas ni dos cuentas reales simultáneas mediante el despliegue de `main`, ni se ha generado un MP4 nuevo desde `main`; eso es un gate obligatorio posterior de aceptación.
- Los 34 archivos nuevos se localizan en `urano/` y `tests/`, ninguna modificación a `web/`, `app.py`, `engine/`, `mixer/`, `companion/` ni secretos/servicios.
- Submódulos heredados de main: `engine=92c7bc33f59baae92a8d61e5dd4bf0ce9685d79e`, `mixer=f15ff91c1b80fc5f157099dcd9451d958d553ae6`.

**Secuencia siguiente:** fusionar I4 al pasar las pruebas, I5 Companion compatible con Windows/Mac y descargas en servidor propio, I6 integración/operación y apagado, I7 aceptación con dos cuentas Google reales y revisión de capturas. Revisar siempre `docs/COLLABORATION.md`, issue #216, los dos STATUS y los handoffs I1–I3.
