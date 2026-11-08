# URANO U15C — Google OIDC laboratorio visual HTTPS, dos usuarios (08-11-2026)

**Estado: pruebas de navegador Chromium en GitHub Actions PASS. No desplegado, no Google real, no producción.**

## Qué se construyó

- Rama `fernando/urano-u15c-google-browser-lab` apilada **sobre U15B, PR #125** (a su vez depende de U15A, PR #124); NO fusionar sin respetar este orden o portar selectivamente.
- `urano/google_lab_app.py`: factoría Flask **opt-in**, distinta de `app.py` y de `urano/lab_app.py` con registro por contraseña. Monta solo el endpoint Google de U15B, el catálogo autorizado U10/U11, un endpoint propio de restauración CSRF que exige origen HTTPS exacto, y los assets estáticos del laboratorio. El catálogo, sesiones y OAuth pending se mantienen en **SQLite separado dentro de un directorio privado suministrado por el operador**.
- `urano/google_lab_ui/{index.html,lab.css,lab.js}`: interfaz de pruebas de acceso Google y catálogo privado: crear/listar/abrir proyectos, notas guardadas como `recipe_json`, cerrar sesión y recuperar tras entrar de nuevo. Preserva el patrón correcto `event.currentTarget` antes del `await`, descubierto en U12b. Se muestran claramente los límites: **sin editor, Engine ni medios**.
- `urano/google_flow.py`: parámetro de ruta de éxito local fija `success_path` suministrada por el servidor (nunca por query string), para volver al laboratorio tras callback; se conserva el comportamiento anterior por defecto.
- No se modifican `app.py`, `web/`, código del Engine, Mixer, Companion, selección de cámaras ni servicios 8101/8102/8103.

## Pruebas (evidencia)

- Workflow `.github/workflows/urano-u15c-google-browser.yml`, run **42511247069: SUCCESS**: módulos de prueba OIDC U15A y U15B con Google ficticio firmando JWT RS256, más navegador Chromium con certificado HTTPS efímero, 2 contextos aislados, 2 Google `sub` distintos y emails `.test`, historial por propietario, bloqueo de lectura cruzada, guardado de notas, recarga, logout y reentrada. JavaScript `node --check`: PASS.
- Salida del test `tests/e2e_urano_google_browser.py`: `passed=true`, `https_browser=true`, `fake_google_only=true`, `oauth_code_pkce_callback=true`, `two_isolated_owners=true`, `project_history_after_logout=true`, `editor_connected=false`, `engine_or_companion_connected=false`, `real_google_credentials=false`. Capturas de ambos usuarios y recuperación adjuntas a Actions, retención 3 días.
- Para garantizar **cero peticiones a Google real**, Playwright usa el API HTTP del **mismo BrowserContext**, compartiendo la cookie de su navegador, y solicita `/urano/v1/google/start` con redirecciones desactivadas; valida la URL Google y sus parámetros, devuelve un ID token firmado desde proveedor ficticio local y abre en Chromium el callback HTTPS local. Prueba redirección/callback/cookies/DOM desde navegador, **no** la navegación a `accounts.google.com` ni Google real.
- Hubo dos ejecuciones preliminares fallidas por interceptación incorrecta de Playwright (la navegación llegaba a Google y rechazaba el client ID ficticio). El ensayo final **no** navega a Google y **sí** pasa. Nunca se usaron credenciales reales.

## Límites y puertas de beta

- Esta prueba en GitHub Actions valida UI / sesión / catálogo en el mismo host HTTPS de laboratorio, no un despliegue público ni Companion instalado en un Mac distinto.
- No hay Client ID/Secret reales, Google consentimiento real ni callback accesible públicamente. No desplegar sin origen HTTPS confiable, allowlist operativa, secrets, protección perimetral y revisión de proxy.
- **No hay aislamiento owner→Engine/proyecto físico/medios**. El catálogo de recetas mantiene revisiones optimistas, no snapshots históricos; no representa un editor Stage con todos los cambios manuales. No habilitar acceso SaaS hasta controlar endpoints de procesos, descargas, ownership, cuotas y recuperación/relink de fuentes.
- Google U15A/B/C requieren revisión, pruebas con identidad real controlada y autorización de Chema para fusionar. Para puerto 8103 de main se aplican las reglas de segregación de releases y datos discutidas en issue #34; esta PR **no** debe desplegarse automáticamente allí.

## Siguientes pasos

1. Revisión de seguridad y consolidación selectiva U15A → U15B → U15C en main cuando corresponda.
2. Definir UX real de beta Google + contrato de sesión/propietario con proyecto Stage existente, antes de unirlo a Engine.
3. Validar 2 usuarios aislados a nivel worker y acceso a ficheros; pruebas negativas de lectura/edición/render cruzado, cancelación y relink de Companion.
4. Comparar su esquema de proyecto y snapshots con el trabajo de Chema sin sobrescribir su edición manual.
