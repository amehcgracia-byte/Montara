# URANO U8 — ¿Dónde alojar la web de Chema? Comparativa de hosting 2026

**Fecha:** 2026-11-05. **Estado:** investigación y selección de candidatos, no migración ni despliegue. El usuario recuerda y reabre la comparativa anterior Cloudflare/Vercel/servidor propio; **no asumir Vercel definitivo** porque la demo ya exista.

## Alcance

Separamos (A) **web / frontend estático** HTML/CSS/JS e imágenes/assets, CDN, HTTPS y dominio de (B) **API de cuentas, proyecto y sesiones** y (C) **workers vídeo/audio Python/FFmpeg/Engine, almacenamiento y GPU opcional**. No valorar Cloudflare Workers como sustituto directo del proceso Python de vídeo. La web debe conservar la interfaz, estilos y lógica de Chema, sin reescribirla; el backend puede seguir en Vercel Sandbox temporalmente durante prototipos, o pasar a hosting de procesos separado cuando se valide.

## Estado del repositorio inspeccionado

- `README.md`: demo pública `https://montara-tau.vercel.app/`, `deployment/vercel` como fuente, y advertencia expresa de no reemplazar alias ni desplegar en cuenta de propietario sin acuerdo.
- `deployment/vercel/package.json`: `@vercel/sandbox` e infraestructura Node.
- `deployment/vercel/runtime.js`: sesión hexadecimal, listado e instancia por sesión, límite **4** demos activas configurado en código, `Drive` y snapshots, arranque de Gunicorn dentro de sandbox, control de procesos/actividad y caducidad de snapshots **7 días**. Esta capa NO es simple hosting estático.
- `deploy/sandbox_entry.py`: cookie de acceso por sesión y límites de ruta. No es login SaaS por cuenta.
- `web/companion.js`: API local `127.0.0.1:47820`; el cambio de dominio requiere revisar origen permitido, CSP/CORS, HTTP local desde HTTPS y permisos. **No abrir el acceso a todo `*.workers.dev` sin autorización más fina.**

## Matriz, cifras oficiales consultadas 05-11-2026 (USD salvo indicación)

| Opción | Web/CDN | Precio/limitaciones relevantes | Encaje y dificultad |
|---|---|---|---|
| **Cloudflare Workers Static Assets (candidato prioritario)** | Red global, assets estáticos gratis, sin límite de requests | Workers Free; Paid desde **$5/mes**; estáticos gratis y sin límite, Workers dinámicos con cuotas según uso | Alto para web ligera. Requiere **separar** despacho de Sandbox/API y comprobar dominio/autorización; no ejecutar Python Engine dentro del Worker |
| **Vercel** | CDN + CI Git + Sandbox existente | **Pro $20/mes**, incluye $20 crédito consumo; Hobby no es comercial; Sandbox CPU/RAM/transfer y snapshots se facturan de forma distinta | Menor coste de integración inmediata; más acoplamiento a sandbox y gasto de compute |
| **Netlify** | CDN + Git + funciones | Free $0 con **300 créditos/mes**; Personal desde **$9/mes** (tarifas personalizadas de panel); Pro desde **$20/mes**; requests/transfer usan créditos | Funciona, pero hoy no proporciona ganancia técnica evidente frente a Cloudflare/Vercel para este stack |
| **Firebase Hosting** | CDN + SSL + Git por CI | Spark gratuito: almacenamiento 10 GB, tráfico de Hosting ~**10 GB/mes**; Blaze pay-as-you-go | Funciona si APIs/procesamiento están en GCP; menos favorable para web pura que Cloudflare con assets sin cargo por request |
| **VPS/servidor propio** | Nginx/Caddy sobre VM en región | El frontend consume poco CPU; coste ya incluido si servidor encendido, pero requiere mantenimiento/backups/TLS, CDN si tráfico lejano | Interesa como servidor de APIs/workers, no es necesario gastar el nodo de vídeo en servir estáticos |

**Precios no son costes finales de Montara:** hay que sumar API, DB/identidad, storage, transferencia de medios, máquinas CPU/GPU, sesiones activas y soporte. No atribuir ventaja de 100 ms o rapidez sin medidas de laboratorio en misma ubicación. Créditos temporales de RunPod/GCP no deben incluirse como ahorro de producción.

### Fuentes oficiales
- Cloudflare nuevos proyectos: Workers static assets recomendado sobre Pages: https://developers.cloudflare.com/pages/
- Cloudflare Workers static assets: https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/
- Cloudflare Workers: https://developers.cloudflare.com/workers/platform/pricing/
- Cloudflare integración Git: https://developers.cloudflare.com/workers/ci-cd/builds/
- Vercel precio y comercial: https://vercel.com/pricing
- Vercel Sandbox: https://vercel.com/sandbox
- Netlify: https://www.netlify.com/pricing/
- Firebase: https://firebase.google.com/pricing

## Recomendación provisional (no definitiva)

**Candidatos reales: Cloudflare Workers Static Assets y Vercel.** Cloudflare es **primero a probar para web estática**, sin abandonar la demo Vercel; Vercel es **baseline de funcionalidad existente**. No trasladar automáticamente el Sandbox a Cloudflare, que no puede ejecutar Engine/FFmpeg Linux Python como un hosting tradicional. El backend debe tener un endpoint con autenticación segura, aunque inicialmente esté en Vercel Sandbox; después valorar VM/Cloud Run. Mantener separación funcional web frente a backend y Companion, sin inventar microservicios.

**Comparativa controlada a ejecutar:**
1. Crear **deploy de prueba separado** de frontend Chema en Cloudflare Workers Static Assets desde GitHub en una rama/entorno de staging; no editar `main`, alias Vercel ni DNS del proyecto.
2. Medir en Chrome/Edge real desde España: TTFB y caché, tamaño inicial, LCP, carga JS/CSS, costo de servir assets, headers/cache; obtener **mínimo 3 muestras** en cada proveedor con mismas rutas/assets y red comparable.
3. Integración del frontend contra API de prueba: rutas relativas `/api/v1/*`, cookies SameSite/autenticación, CORS, login ficticio, reconexión al mismo proyecto y permisos de Companion localhost; monitorizar egress y no exponer tokens ni credenciales.
4. Testear carga y subida **solo de proxies** y descarga/export; no subir vídeos originales en benchmark sin consentimiento.
5. Comparar tiempo de desarrollo/migración, restricciones de API, seguridad, complejidad de CI, costes con escenarios de tráfico realista. La latencia final de procesamiento depende sobre todo de Engine y fuentes, no de CDN.
6. Tras pruebas elegir; si Cloudflare gana, conservar web de Chema y publicar allí, enlazando backend aparte. Si Vercel gana en integración, mantenerla conscientemente y evaluar coste Sandbox aparte.

**Bloqueadores**: aún no existe contrato definitivo frontend↔backend↔cuentas; dominio de producción, login y propiedad de proyectos y tokens Companion pendientes. **No hacer despliegue en cuentas del usuario ni alterar URL existente sin autorización.**
