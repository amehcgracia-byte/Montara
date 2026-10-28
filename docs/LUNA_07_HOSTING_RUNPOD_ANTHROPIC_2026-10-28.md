# LUNA 07 — hosting gratuito/casi gratuito, RunPod y Anthropic Fast Mode (2026-10-28)

**Estado:** comparación documental con fuentes oficiales, sin despliegues, compras ni benchmarks nuevos. Esta nota no autoriza gastos ni modifica `main`.

## Roles distintos
- Web estática/control plane: Cloudflare Workers/Pages u otro CDN gratuito; no ejecuta render Python/FFmpeg prolongado.
- API y coordinación persistente: Oracle Always Free ARM (sujeto a capacidad y portabilidad ARM), Google Cloud e2-micro (1 GB RAM, regiones US y salida limitada), o VPS barato.
- Render CPU: contenedor x86_64 Montara ya validado con 2CPU/8GiB, Stage 100.233991s output, export 329.192s y memoria peak cgroup ~1.84GiB. Repetir sobre hardware destino; no suponer rendimiento equivalente.
- Render GPU a demanda: RunPod Pods o Serverless. Pods (GPU o CPU-only) pagan mientras funcionan; Serverless escala workers a cero y paga tiempos de ejecución/cold start/idle configurado. Almacenamiento separado.
- Archivos originales: navegador/local por defecto, o subida expresa cuando ejecutor remoto requiera bytes; identificar límite transferencias y costes antes de prometer 30GB.

## Tarifas y ofertas verificadas
- RunPod oficial https://www.runpod.io/pricing actualizado 2026-10-08: L40S GPU Pod $1.09/h, RTX 6000 Ada Pod $0.99/h, H100 PCIe $2.89/h; Serverless 4090 $1.10/h; tasas variables por región/cloud. Network volume estándar $0.07/GB/mes (<1TB). Billing/storage FAQ https://github.com/runpod/docs/blob/main/accounts-billing/billing.mdx . CPU Pods existen https://registry.terraform.io/providers/runpod/runpod/latest/docs/guides/cpu-pod , no asumir precio sin cotización concreta.
- Oracle Always Free https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm : ARM A1 1500 OCPU-hours, 9000GB-hours equivalentes a 2OCPU/12GB continuos; capacidad/región y políticas de reclamación importan; 200GB block incl boot. Arquitectura arm64 no validada para Montara.
- Google https://docs.cloud.google.com/free/docs/free-cloud-features : e2-micro en 3 regiones EEUU, 30GB-month disk, 1GB/mes salida VM; demasiado pequeño para render, posible coordinación ligera.
- Render https://render.com/docs/free: web service gratis, duerme después de 15 min inactividad, despierta en aproximadamente 1 min y filesystem efímero. No guardar original/proxy persistente allí.
- Cloudflare https://developers.cloudflare.com/pages/: web estática/edge. No servidor de render.
- Hetzner https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ : desde 15-06-2026 CX23 Alemania €5.49/mes sin IVA (según tabla excl. IPv4), CAX11 ARM €5.99/mes sin IVA; confirmar coste IPv4, almacenamiento y términos. Un VPS real completo a €0.007/mes no está confirmado; €0.70/mes suele ser hosting compartido limitado, no CPU/render.
- 300€ crédito RunPod del propietario: no confundir crédito ya depositado con proveedor gratis o presupuesto perpetuo.

## Anthropic: dos referentes diferentes
- Claude API Fast Mode https://platform.claude.com/docs/en/build-with-claude/fast-mode : `speed:"fast"` da hasta 2.5x OTPS en modelos soportados (Opus 5.5), **no acelera FFmpeg ni garantiza menor time-to-first-token**. Es un servicio API de pago premium, no un repositorio GitHub clonado; benchmark de request/response sólo si Montara usa esa API.
- Código open-source https://github.com/anthropics/claude-code y https://github.com/anthropics/skills contienen instrucciones/SDK workflows; no equivalen a un motor HTTP de render, y no hay evidencia de que usuario se refiera a esos repos. Solicitar URL/nombre específico para revisar cualquier GitHub concreto de Anthropic para requests.

## Arquitectura candidata y test gates
1. URL/landing en plataforma gratuita; API/control privada en CPU gratuita o VPS mínimo; originales locales por defecto; temporales remotos con TTL y cuotas; export CPU de referencia x86.
2. GPU RunPod *solo* para trabajo que realmente mejora tras T_subida + T_cola + T_proc + T_descarga y cambios de calidad verificados; incluir arranque de worker, almacenamiento, cancelación/expiración.
3. Primero pruebas de Linux ARM64/Oracle y comparación x86 equivalente; pruebas 1 usuario antes de multiusuario.
4. Tests por servicio y privacidad: CPU/RAM/cgroup, temp disk, memoria GPU, bytes transito, coste real, alta disponibilidad, seguridad, región, persistencia y backups.
5. No contratar dominio, hosting, storage ni GPU automáticamente. Nunca publicar autenticación privada como producto multiusuario.
