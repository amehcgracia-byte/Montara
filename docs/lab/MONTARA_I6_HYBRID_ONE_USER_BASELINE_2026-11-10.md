# I6 — Baseline híbrida real de una persona: instrumentación recuperada

**Fecha:** 2026-11-10 · **Estado:** herramientas recuperadas; **NO existe todavía un benchmark completo de una persona en la arquitectura híbrida actual**. Base: `fernando/integracion@42632a3`.

## Fuente recuperada
Desde las PR históricas #131 (U17B), #132 (U17C) y #133 (U18), sin traer cambios en producto:
- `tests/urano_hybrid_node_meter.py`: observación pasiva de PID y descendientes, CPU/RSS de Companion/navegador/servidor. Requiere `psutil` al medir.
- `tests/urano_hybrid_merge_reports.py`: validación de informes multi-host; su escala antigua empieza en 2 clientes y **no declara baseline de uno**.
- `tests/urano_browser_transfer.py`: bytes HTTP observados desde Playwright, separando servidor y Companion; no contabiliza toda la red, ni peticiones Python externas.
- `tests/urano_remote_hybrid_preflight.py`: comprobación opt-in HTTPS y localhost Companion. **La ruta histórica `/api/v1/wizard/status` es del editor clásico, no del portal C8 Google actual**; no utilizar como certificación de C8 sin adaptación.
- Tres suites de contratos y los tres informes históricos completos.

## Pruebas de recuperación
En worktree independiente sobre nuestra rama, con `PYTHONPATH=tests`:
`python -m pytest -q tests/test_urano_hybrid_node_telemetry.py tests/test_urano_browser_transfer.py tests/test_urano_remote_hybrid_preflight.py`

**Resultado local: 15 passed, 2 skipped, 14 subtests passed.** Los dos casos omitidos requieren `psutil`, ausente en el Python de la VM; el workflow nuevo lo instala en GitHub CI. No declarar estos dos como pasados localmente ni confundir contratos con benchmark WAN.

## Estado de la beta durante la comprobación
El portal `montara-owner.memoriainvalida001.workers.dev/healthz` devuelve HTTP **503** (10/11/2026); la unidad `montara-owner-beta.service` ya no figura en el gestor `systemd --user` de `fgardel00` y no hay escucha 8115. No se reinició, instaló ni modificó nada. Confirmar primero si se trata de una parada deliberada, cambio de despliegue o reinicio, y restituir solo con autorización. No usar 503 como resultado de capacidad del producto.

## Procedimiento de la baseline I6B (aún pendiente)
1. Un **usuario real** con ordenador físico navegador + Companion instalado y servidor privado HTTPS operativo. Registrar SHAs de Main/Integración/Engine/Mixer y versiones exactas Mac/Windows/FFmpeg.
2. Fixture de vídeo original local fijo, por separado plano y 360: duración, tamaño, cámaras/audio, formato y hashes; consentimiento. El original **NO** se transfiere silenciosamente al servidor.
3. Recorrido real marcado etapa a etapa: Google → proyecto → localizar original local → proxy → subida autorizada → Engine Stage aislado → receta → Companion → MP4 local comprobado con FFprobe. Las etapas aún no integradas se marcan **NO PROBADAS**, no se rellenan con mocks.
4. CPU, RAM/cgroup y tiempo por proceso/máquina; latencia, errores/reintentos, tamaño de proxy, bytes navegador→servidor y server→navegador, transferencia Companion y tiempo de render local. Valor desconocido = `null`, no cero.
5. Tres repeticiones con condiciones comparables; distinguir frío/caliente/cachés.
6. Cloudflare frente a Vercel: **solo comparar el mismo backend, servidor, versiones, client, fixture y red** si queremos aislar efecto de frontend/túnel. Si cambia infraestructura, son escenarios diferentes.
7. Antes de 2,4,8,10 usuarios: primero I5B aislamiento real, baseline de 1, criterios de latencia p95/errores/coste, y pruebas de cancelación/recuperación. Medir usuarios conectados y trabajos pesados simultáneos como variables distintas.

## Portabilidad y gobierno
Los informes deben ser neutrales respecto a GCP/Oracle/Azure/Cloudflare/Vercel; no depender de la IP, cloud SDK, cuentas, URLs completas ni credenciales. La integración de herramientas es **solo instrumentación y tests**, sin activar Engine ni realizar mediciones pesadas. La beta C8 y main quedan inalterados. No suponer que GitHub Actions en un solo runner mide red WAN ni CPU separada por dispositivo.

**Siguiente bloque:** I6B: adaptador de preflight para rutas privadas OAuth/Companion actuales y runner de un usuario opt-in; no ejecución física hasta restablecer y comprobar la beta y el aislamiento apropiado.
