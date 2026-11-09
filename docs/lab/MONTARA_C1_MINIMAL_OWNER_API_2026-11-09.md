# MONTARA C1 — Integración mínima Google → catálogo existente
**Fecha:** 2026-11-09  
**Base de rama:** `main@765a34ceec33311cd520856d46fec15adfc6c0a1`  
**Tipo:** integración pequeña de backend **opt-in**, sin modificar `app.py`, `web/montara.js`, `companion/companion.py`, Engine, Mixer, servidores ni puertos.

## Qué hemos elegido para ir más rápido

La política de confirmación manual de subida de original de vídeo **ya está presente en el main** dentro de `web/montara.js` (funciones `confirmOriginalVideoUpload`, `uploadSmall`, `upload`) y hay tests `tests/urano_u3a_upload_baseline.cjs`. Por tanto, **NO copiar nuevamente el frontend de PR #74** ni rehacer esta protección. La garantía integral de backend sigue pendiente para una beta, pero hoy no debemos arriesgar regresiones en el uploader.

El siguiente mínimo funcional es conectar **el login Google verificado al catálogo existente** para obtener sesiones de dueño reutilizables por los futuros Engine workers. No construir otra aplicación completa, otra UI o nuevos modelos de catálogo.

## Código traído selectivamente

Se han recuperado **de la rama laboratorio U15C** exclusivamente:
- `urano/google_oidc.py`: verificación estricta de ID token Google.
- `urano/google_owner.py`: mapeo Google `sub` verificado → ID privado persistente, sin apropiarse de datos por email.
- `urano/google_flow.py`: OAuth Authorization Code+PKCE, nonce, estado de un solo uso, emisión de cookie opaca ya existente.
- `requirements-urano-oidc.txt`: dependencia **opcional**, no cargada en el servidor web actual.
- Sus contratos `tests/test_google_oidc_contract.py` y `tests/test_google_flow_contract.py`.

Nuevo en C1:
- `urano/minimal_owner_api.py`: fábrica API **opt-in**, combina el flujo seguro anterior con **`urano/http_projects.py` y `urano/project_catalog.py` de main**, sin copiar ni sobrescribir esos archivos. Una ruta muy pequeña permite renovar el CSRF únicamente desde el HTTPS origin conocido y una sesión ya autenticada.
- `tests/test_c1_minimal_owner_api.py`: dos sesiones Google de prueba firmadas, aislamiento de proyectos, rechazo de ID ajeno, CSRF, logout, email fuera de allowlist, ausencia de endpoints de Engine/medios.
- Workflow aislado de CI `.github/workflows/c1-minimal-owner-catalog.yml`.

## Límites deliberados

**Esto NO despliega Google, NO inicia Engine y NO expone ningún puerto.** Los JWT del CI son ficticios pero firmados y verificados en memoria; nada llama a Google real. Los secretos reales, el dominio HTTPS, la allowlist y los callbacks no se configuran ni se publican aquí. La fábrica no se invoca desde `app.py`; solo es una costura verificable para integrar luego.

El email verificado es necesario para la allowlist de beta pero **no sirve como clave de apropiación de un proyecto existente**; se utiliza la clave estable Google `sub` mapeada a una identidad interna. Las sesiones mantienen cookie Secure/HttpOnly, estado PKCE y CSRF.

## Qué falta para la arquitectura mínima útil

Una vez pasada esta puerta, **unir directamente** el dueño de la sesión a su worker privado U19/U20 sin crear nueva UI experimental; conectar Stage y el Companion local U21. Mínimos antes de permitir acceso externo: proxy↔huella del mismo original, endpoint de subida servidor fail-closed por defecto, cancelación básica, un servidor HTTPS de test y una prueba real desde Mac. No requieren hacer 25 usuarios, Windows completo, una nueva plataforma cloud ni una auditoría enorme.

## Revisión y aceptación

1. CI de OIDC/PKCE y la nueva API de propietario **en verde**.
2. `main` y app actual intactos, sin migración de SQLite ni modificación de `project_catalog.py`.
3. El constructor de esta API sigue **no invocado en producción**; prohibido merge/deploy automático.
4. Siguiente PR, si esta pasa, será un **solo enlace owner→worker/Stage**, tomando las partes finales validadas de U19/U20, no cada microPR antigua.

**Ajuste de calendario:** tratamos C1 como primer corte de una arquitectura funcional rápida, no como una etapa de producto independiente de semanas. Se prioriza un MVP con **Mac Companion** y web básica; Windows avanzado y benchmarks 4/8/10/25 se posponen.
