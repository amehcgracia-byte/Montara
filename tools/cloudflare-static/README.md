# URANO — laboratorio Cloudflare, **solo rendimiento visual**

La web principal de Chema **no se sustituye**. Esta rama genera una copia de `web/` con HTML, CSS, JS y assets idénticos a `main`, salvo política CSP restrictiva que **bloquea completamente conexiones al backend, Companion y medios externos**. No es un editor funcional. No introducir fuentes originales, no iniciar trabajos, no usarlo para validar login/proyectos/edición. Solo sirve para medir **transferencia estática/TTFB/carga visual y funcionamiento GitHub→Cloudflare**; las métricas de editor funcional requieren una prueba posterior comparable con backend real.

## Construcción reproducible desde GitHub (Cloudflare Pages)

- **Rama:** `fernando/lab-cloudflare-static-benchmark`, no `main`.
- **Root directory:** raíz del repositorio.
- **Build command:** `python3 tools/cloudflare-static/build.py`.
- **Build output directory:** `dist`.
- **Environment/secrets:** ninguno necesario.
- **Production deployments:** no habilitarlos para `main` en este laboratorio; usar solo preview/proyecto temporal, sin dominio propio. GitHub debe autorizar acceso al repositorio al conectar Cloudflare Pages.

**Actualización 2026-11-06:** autorizada la conexión GitHub–Cloudflare y creado en la cuenta del proyecto el laboratorio aislado `montara-cloudflare-lab.pages.dev`, enlazado únicamente a esta rama. Este cambio documental dispara la primera compilación; verificar su resultado antes de declarar el sitio publicado. La web resultante **no procesa proyectos ni permite edición real**. Puedes retirar el laboratorio después de comparar.

## Qué comparar

1. Usar una misma revisión de `web/` y medir HTML, CSS, JS en Cloudflare (copia estática) frente al recurso estático comparable en Vercel. Mismo navegador y conexión desde Madrid. Mínimo 3 repeticiones sin caché y 3 con caché.
2. Registrar HTML TTFB, tamaño transferido, `DOMContentLoaded`, LCP de la portada, éxito/404 de assets y presencia de caché.
3. **No comparar el editor renderizando o procesando**: Cloudflare estático no tiene API; la demo Vercel arranca Sandbox (sesión, CPU y motor). Son arquitecturas distintas. El tiempo de arranque de Sandbox no es «la velocidad del CDN» y mezclarlo falsearía la conclusión.
4. Si la diferencia es marginal, preservar Vercel y continuar URANO; si Cloudflare aporta ventaja material, plantear después separación del frontend y API con autenticación real.

## Guardarraíles

- No tocar producción `montara-tau.vercel.app`, su DNS, submódulos ni `main`.
- No despliegue automático en ninguna cuenta con este commit.
- Sin credenciales, sin cobros, sin uso de GPU ni nuevas máquinas.
- Por diseño, `connect-src 'none'` bloquea `fetch`/XHR; las acciones de edición fallarán en esta réplica, **de manera deliberada**.
