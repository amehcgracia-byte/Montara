# Montara — ADR I5C: arquitectura híbrida y neutralidad de nube
**Fecha:** 2026-11-10 · **Estado:** propuesta de diseño (sin despliegue ni cambios runtime) · **Base:** `fernando/integracion`.

## Intención del producto (no negociable sin aprobación)
- Originales grandes permanecen en el equipo del usuario; **Companion local** identifica fuentes, produce proxies, puede ejecutar trabajo local y genera export final desde originales sin subida silenciosa.
- El **servidor** aloja identidad/sesión, catálogo y proyectos, valida recibos/proxies, coordina Engine y tareas que realmente necesiten backend. Solo transmite proxies/recetas/metadatos necesarios, en límites medibles.
- Primero beta de 2–4 personas con créditos GCP; no atar la lógica ni los IDs/rutas a GCP. Posibles destinos posteriores: Azure, Oracle, otra VM Linux u otro proveedor. **Escalar sin rehacer el editor**.
- Google OIDC es proveedor de identidad y no exige Google Cloud para el servidor. Cloudflare Workers/VPC/hostname de beta son adaptadores de entrada, no API del producto: si se sustituyen deberá migrarse DNS/callback Google/credenciales y mantener URLs de usuario estables cuando exista dominio propio.

## Estructura objetivo
1. **Frontend + Companion (Mac/Windows):** contratos versionados `capabilities`, `media_manifest`, `proxy_receipt`, `edit_recipe`, `render_handoff`, `job_status`; identificadores opacos, checksums, consentimiento explícito, retries idempotentes y recuperación tras desconexión. Mac mantiene la versión de Chema; Windows usa extensión compatible y pruebas propias.
2. **Montara Core (control plane):** identidad/sesión, permisos, catálogo, recetas, estado de jobs, cuotas, seguimiento, auditoría, API versionada. No importa Docker, LXD, GCP SDK ni ejecuta trabajos pesados dentro de peticiones HTTP.
3. **ExecutorBackend (interfaz/adaptador):** `start(owner, project, job_spec)`, `status(job_id)`, `cancel(job_id)`, `recover()`; especificación cerrada de trabajos sin rutas arbitrarias; provisionamiento y autorización fuera del navegador. Implementaciones: systemd con UID real, LXD, OCI o worker remoto en otra VM. La seguridad del adaptador se valida de manera independiente: no todo adaptador que cumple firmas es seguro.
4. **Scheduler / admission:** límites de CPU/RAM/PIDs/disco/tiempo, justa admisión bajo saturación; sin cola global obligatoria con capacidad sobrante. Estados persistidos + lease/heartbeat + reintentos idempotentes + job version y compatibilidad de Engine. La cola podrá ser SQLite local para una sola VM y PostgreSQL u otra plataforma duradera al usar varios nodos; **no compartir SQLite mediante disco entre varias VM**.
5. **StorageAdapter:** SQLite local con backups/migraciones probadas durante beta; contrato de persistencia separa metadatos, base de datos, proxies temporales y artefactos pequeños. Preparar migración a PostgreSQL antes de multiinstancia del control plane. Object storage compatible S3 es opcional para proxies pequeños/artefactos con TTL; verificar compatibilidad API específica; nunca usarlo como depósito obligatorio de originales.
6. **Infraestructura sustituible:** build reproducible con Python, ffmpeg y submódulos versionados; imagen OCI del core/worker cuando sea práctico, pero **no asumir que Docker es requisito del usuario ni del servidor**. Variables y secretos externos al repo; scripts de despliegue Linux (Ansible o similar) reutilizables y capa de recursos por proveedor con OpenTofu solo al justificarlo; probes de salud, backups cifrados, restauración en otro proveedor y rollback.
7. **Observabilidad neutral:** métricas por fase y máquina (cliente vs server), logs estructurados y OpenTelemetry/Prometheus; registrar versión/CPU/RAM/archivos, no contenido ni rutas sensibles. Correlacionar usuario/proyecto/job pseudonimizados.

## Por qué no Kubernetes ahora
En 2026 existen Kubernetes HPA a cero (v1.37) y KEDA jobs con autoscaling, pero administrar un clúster para dos usuarios elevaría costes/operación y no resuelve el protocolo Companion ni el aislamiento de datos. Conservar el contrato Job/Executor permitirá adoptar K8s, cola externa o workers multi-VM cuando las métricas indiquen necesidad.

## Prueba de capacidad que aún falta
**No inferir usuarios por 8 vCPU:** cada sesión tiene mezcla de navegación, ingest/sync, proxy, 360, Stage, transferencias y render local en Companion. Definir fixtures reproducibles `flat1080p`, `flat4k`, `360`, 1/3/varias cámaras, audio, clips largos y ordenador cliente lento; y cargas 1,2,4,8,10 usuarios con distintas mezclas (25 solo si el límite anterior es seguro). Incluir pruebas frías y calientes, 3 repeticiones o más, archivos reales/sintéticos sin datos privados y perfil de recursos/CPU por host.

Medir por operación: latencia p50/p95, tiempo de primera vista, tiempo Stage/ingest/sync/cut/edit, throughput MiB/s, bytes de proxy y original al servidor (esperado original=0 salvo consentimiento explícito), CPU/RAM/PSS y cgroup, disco/proxies TTL, red/egress, colas, errores/timeout, impacto de trabajos en sesiones ajenas y tiempo export local en al menos dos equipos cliente. Distinguir cloud cost por hora/egress de equipo cliente. No prometer capacidad antes de un E2E real.

**Antecedente útil, NO extrapolable:** `docs/ANTES_DEL_SERVIDOR.md` registra vídeo de 100 s y pico de cgroup ~1.84 GiB en una prueba acotada a 2 CPU/8 GiB; otro recorrido tomó ~811 s incluyendo esperas. Son **fixtures/escenarios diferentes** y no certifican 2/10 usuarios simultáneos, 4K/360 ni la arquitectura Companion final.

Definir umbrales de aceptación junto al usuario: operatividad sin fugas, p95 interactivo, trabajos completados, ratio errores, coste/usuario y estado tras fallo/reinicio. Medir después de decidir qué trabajo se mueve efectivamente al Companion, no antes.

## Prueba obligatoria de portabilidad
En VM limpia de proveedor B (o Linux local equivalente): desde commit/submódulos fijados restaurar backups y secretos de prueba, arrancar core y worker sin cambiar código; verificar Google redirect configurado, sesiones/catálogo, 2 propietarios, trabajo sintético, cancelación, export local Companion, proxies con SHA, logs, métricas y rollback. Registrar pasos manuales, tiempo y dependencia de Cloudflare/VPC. La primera migración ensayada NO requiere contratar un segundo cloud.

## Riesgos pendientes
- **I5B**: elegir fuerte aislamiento para Engine por propietario (UID systemd de sistema con broker restringido vs LXD no privilegiado). No confundir subprocess bajo mismo UID con sandbox. No usar socket LXD desde web.
- Dependencia real de algoritmos Stage/FFmpeg/360 de servidor: medir antes de presumir qué partes pasarán a Companion. Evitar subidas grandes obligatorias.
- OAuth Google externo y subdominio Cloudflare gratuito son dependencias de identidad/entrada, **no de la nube CPU**, pero deben figurar en plan de migración.
- Versionado de contratos para que Companion y servidor se actualicen independientemente; soporte Mac y Windows.
- SQLite mononodo no es almacenamiento distribuido; migración planificada sin introducir Postgres prematuramente.
- Licencias de FFmpeg y componentes se revisan aparte antes de distribución comercial.

## Fuentes
- Documentación del repositorio: `docs/ANTES_DEL_SERVIDOR.md`, `docs/montara-c7-isolated-beta-deployment-plan.md`, `docs/USER_PROJECT_FOUNDATION.md`, `docs/lab/URANO_U13D2A_PARALLEL_USERS_POLICY_2026-11-06.md` y `docs/lab/MONTARA_I5B_ISOLATION_ARCHITECTURE_REVIEW_2026-11-10.md`.
- 12factor (config y servicios sustituibles): https://12factor.net/backing-services https://12factor.net/config
- OpenTelemetry vendor neutral: https://opentelemetry.io/docs/
- OCI: https://opencontainers.org/
- OpenTofu providers: https://opentofu.org/docs/language/providers/
- Kubernetes scale-to-zero (2026): https://kubernetes.io/blog/2026/09/02/kubernetes-v1-37-hpa-scale-to-zero-beta/
- KEDA job scale: https://keda.sh/docs/2.21/concepts/scaling-jobs/
- systemd sandbox: https://freedesktop.org/software/systemd/man/latest/systemd.exec.html

**Resultado de I5C:** ADR documental para revisión; no se cambian motores, infraestructura, servicios, puertos, secretos ni despliegue. No merge a main.
