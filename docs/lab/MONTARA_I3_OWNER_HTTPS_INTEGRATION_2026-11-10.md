# I3 — Portal privado HTTPS y Google real (integración selectiva)

**Fecha:** 2026-11-10. **Base:** PR #166 / `fernando/i2-owner-dashboard-20261110`.
**Origen:** C6 #153, C8 #157–#158. **Sin desplegar ni alterar la beta C8 activa**.

## Alcance exacto
- Se incorporan `urano/c6_beta_preflight.py`, `urano/trusted_local_https.py` y una variante mínima de `urano/owner_beta_wsgi.py`, además de pruebas y CI.
- La variante I3 mantiene el puerto/Engine sin activar, y **rechaza explícitamente** recibir `runtime_controller`, `proxy_staging_root`, `receipt_verifier` o `stage_provenance` hasta la revisión futura de Engine/Companion. Esto evita importaciones/dependencias C2-C5 todavía no integradas.
- No se importan `app.py`, `web/montara.js`, `companion/companion.py`, `engine/`, `mixer/` ni cambios de despliegue real de Cloudflare.
- No se guardan Client ID, Client Secret, secretos HMAC, datos de usuarios, carpetas privadas ni claves en Git.

## Verificación focalizada
En worktree de integración aislado, Python del entorno beta con configuración ficticia:
`PYTHONPATH="$PWD/tests:$PWD" python -m pytest -q tests/test_c1_minimal_owner_api.py tests/test_c4_owner_dashboard.py tests/test_google_oidc_contract.py tests/test_google_flow_contract.py tests/test_c6_https_google_preflight.py tests/test_c8_google_owner_ui_bridge.py tests/test_c8_trusted_local_https.py tests/test_urano_project_catalog.py tests/test_urano_session_http.py -k 'not test_companion_signed_receipt_only_for_exact_beta_origin'`

**Resultado: 51 passed, 1 deselected, 54 subtests passed.** La primera ejecución SIN exclusión dio **51 passed, 1 failed, 54 subtests passed**: `test_companion_signed_receipt_only_for_exact_beta_origin` requiere `trusted_signed_receipt_origin`, función de Companion posterior que **no existe en el main base**. La prueba original se conserva intacta; no se falsifica como pasada. El contrato se recuperará en una PR específica de Companion tomando la versión Mac vigente de Chema (incluyendo #164 cuando se integre). No copiar la versión antigua del Companion sobre main para resolver esto.

## Puertas restantes
- CI específica y E2E general del main (independientes y aún pendientes cuando se escribió este documento).
- Integrar los tres bloques apilados en `fernando/integracion` solo después de revisar resultados y conservar rollback.
- El acceso HTTPS real ya se verificó en una beta separada, pero I3 **no** afirma que su rama se haya desplegado ni que Engine/Companion funcione en multiusuario.
- Mantener `fernando/continuacion-montara`, C8 y todas las PR históricas como fuentes de verdad; no cerrar ni borrar.
