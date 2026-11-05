# URANO U6 — revisión de arquitectura y coordinación de ejecución (exploración, no decisión)

**Fecha:** 2026-11-05 · **Estado:** revisión estática e hipótesis, **sin cambios de runtime**.  
**Instrucción del propietario:** la división inicial navegador / Companion / servidor es solo un **boceto lógico**, no una arquitectura fijada. Se solicita evaluar una redistribución inteligente y un posible **coordinador de trabajos**; no imponer nuevos componentes sin medir y revisar con JM/Chema.

## 1. Evidencia de código existente

| Lugar | Coordinación que ya existe | Límite comprobado |
|---|---|---|
| `web/montara.js` | `make()` dirige `/wizard/prepare` y `/wizard/start`, `workRequest()` asocia generación y cancelación, `waitFor()` consulta status y controla 45 min sin progreso | Es coordinación de interfaz/proyecto; no decide en general capacidad, precio ni colocación entre local, cloud y GPU |
| `app.py` | `mix_jobs` en diccionario, `mix_lock` serializa el mixer y thread por trabajo | Estado en memoria de proceso; no constituye cola duradera multiworker ni planificación por recursos |
| `companion/companion.py` | `/locate` identifica local, `/proxies` crea hilo por proxy, `/video-renders` delega a `VideoJobs` | Decide tareas locales concretas, no es el scheduler universal del producto |
| `companion/video_jobs.py` | Jobs y slot/semaforo para render local, snapshot de completados | Capability limitada; no hay garantía de video renderer Windows en instalación FER |
| `app.py` + `server.api` | `create_app(project_path=...)` reabre último proyecto tras reinicio de un preview | Proyecto de servidor y sesión actual; no sistema multiusuario duradero |
| `deploy/vm/README.md` | Gunicorn 1 worker/8 threads para vista privada; aislamiento por persona en laboratorio | La nota exige no escalar workers para fingir multiusuario |
| `deployment/vercel/runtime.js` (según auditoría U4B) | Sandbox Vercel por sesión y límite de activos | Es aislamiento de infraestructura, no prueba de scheduler de costes multiubicación |

**Alcance del hallazgo:** al revisar los módulos anteriores no se identifica un **orquestador transversal de ubicación de tareas** (tipo local/CPU remota/GPU, fallbacks de disponibilidad y costes). No se afirma una ausencia absoluta en todo el repositorio, submódulo Engine o despliegue. La investigación debe ampliarse a `server.api`, Engine, sandbox y modos Show/Push.

## 2. Separar responsabilidades, sin asumir dónde vivirán

1. **Estado del proyecto (control plane):** identidad/propiedad, inputs y huellas de originales, proyecto editable y versiones de recetas, dependencia de tareas, localización de derivados y auditoría.
2. **Planificador ligero:** dado trabajo, fuentes disponibles, capacidades (`ffmpeg`, RAM, CPU/GPU, encoder, presencia del dispositivo), requisitos de salida, límites, privacidad, plazos y precio, decide el **ejecutor** adecuado. Un planificador lógico no requiere inicialmente microservicio, base de datos ni «IA» predictiva.
3. **Ejecutores (data plane):** navegador para interfaz/previsualización pequeña; Companion local para localizar originales, transformar proxies y eventualmente render; Engine/Mixer CPU remoto para tareas admitidas; GPU remoto solo donde un benchmark justifique rentabilidad/latencia y haya un proveedor disponible.
4. **Movilidad de medios:** no enviar originales locales enteros como fallback automático; transferir proxies, planes y fragmentos cuando esté justificado. Para originales de YouTube/remotos, evaluar rutas remotas legales y técnicas, separadas del drag/drop local.
5. **Persistencia y recuperación:** un *job* identifica propietario/proyecto/etapa, dependencia, ejecutor elegido, estado duradero, idempotency key, versión de modelo/receta, artefactos y política de reintento. El almacenamiento de control no tiene por qué contener los originales.

## 3. Posibles arquitecturas a comparar

| Opción | Valor | Coste/riesgo | Decisión provisional |
|---|---|---|---|
| A. Flujo rígido web→Companion→cloud | Simple y cercano al prototipo | No adapta ubicación al tipo de medios/capacidad; puede forzar transferencias/render improductivos | **No elevar a dogma** |
| B. **Planificador lógico dentro del backend existente**, con capability negotiation de Companion | Aporta rutas de ejecución y prioridades sin añadir servicio externo | Persistencia de jobs y propiedad son precondiciones; el backend hoy mezcla estados en memoria | **Candidato a evaluar primero** |
| C. Scheduler separado con cola duradera + workers heterogéneos | Escalabilidad/reintentos/telemetría multiusuario | Alto coste operacional y superficie de seguridad; prematuro antes de resolver aislamiento y medir | Evaluar cuando exista escala que lo justifique |
| D. «Orquestador IA» adaptativo | Posible optimización posterior | Decisiones opacas, no determinismo, coste de inferencia y métricas insuficientes | No recomendable como primer escalón; empezar reglas observables |

No decidir entre B y C hasta evaluar cuenta, aislamiento, frecuencia de trabajos y cargas reales. Aunque exista planificador, cada ejecutor debe aceptar solo trabajos autorizados y verificar disponibilidad de fuentes.

## 4. Mínimo contrato experimental (borrador, NO API definitiva)

- **Input:** `job_id`, `project_id`, `kind` (locate/proxy/analyze/sync/edit/render/mix), `source_refs`, `input_sizes`, `privacy`, `recipe_revision`, `required_capabilities`, `deadline_class`.
- **Capabilities:** `executor_id` pseudónimo, `engine_version`, `supported_jobs`, `cpu`/`ram_available`/`gpu_profile` relevantes, `ffmpeg` y codecs; sin divulgar rutas absolutas privadas.
- **Plan:** ruta elegida + razón observada (privacy/bytes transferred/estimated compute/runtime/support) + presupuesto y alternativa permitida; **sin compromiso de rendimiento no medido**.
- **Estado:** `pending → claimed → running → succeeded|failed|cancelled`, reintentos acotados y recuperación tras pérdida de heartbeat. Persistir identidad y propiedad antes de aceptar un trabajo; nunca usar nombre de archivo/flag `small` como prueba de origen.
- **Gates:** no exponer Companion solo con CORS; tokens por acción/proyecto, límites, pruebas dos usuarios ficticios, cancelación idempotente, trazas y costes medidos. Antes de usar RunPod créditos, benchmark reproducible con el motor fijado.

## 5. Orden sugerido de trabajo (aporta evidencia antes de implementar)

1. Cerrar e inspeccionar PR #82 (test del puente JS con HTTP simulado) y #83 (protección del original al restaurar): integración separada solo cuando CI/E2E complete y haya revisión.
2. Inventariar **quién inicia cada tipo de job** en Stage/Push/Show/Mix y qué persiste en Engine, servidor, Vercel y Companion; marcar puntos de decisión local/cloud ya existentes.
3. Elaborar matriz real por modo: origen local/remoto, original vs derivado, dependencia, memoria/CPU/GPU, ancho de banda, coste estimado, límites y posibles fallbacks.
4. Medir casos con ejecutor local CPU vs VM CPU y opcional RunPod GPU, mismo material/Engine/versión, tiempos y bytes transferidos. No asumir que GPU gana en todo.
5. Probar un **planificador puro con decisiones simuladas**, sin infraestructura nueva: casos deterministas y prioridades costo/privacidad/plazo; revisar con Chema.
6. Diseñar el mínimo almacenamiento duradero de jobs/proyectos con propiedad, reconciliación del Companion tras reconexión y pruebas de pérdida de proceso. Elegir formato persistencia según patrón de acceso medido.

## Decisiones abiertas de producto

- ¿Edición disponible sin Companion encendido, y qué acciones exactas requieren fuentes originales?
- ¿Móvil, tablet y YouTube remotos exigen rutas distintas para los mismos modos?
- ¿Qué hacemos si falta GPU/Companion/Internet? Prohibido convertir fallo en subida silenciosa del original.
- ¿Dónde vive la fuente de verdad de la **receta editable**? ¿En cloud con snapshots local-first, o réplica sincronizada? Depende de cuentas, modo offline y colaboración, no se decide aquí.
- ¿Queremos costes máximos por trabajo / SLA / usuarios simultáneos y qué pagaríamos por colas en lugar de retrasar el trabajo?

**Conclusión:** el esquema inicial es una implementación parcial útil, no la distribución final. Existe coordinación por componentes; no se ha verificado orquestación transversal. La ruta razonable es primero inventario + benchmarks + contrato de trabajos, y solo entonces escoger orquestador, persistencia y despliegue. Esta nota no autoriza cambios a producción, Engine/Mixer ni instaladores.

## 6. Contexto comercial y experimental aportado por propietario — 05-11-2026

**Intención de producto:** Montara se concibe **de pago desde el lanzamiento**, no como un servicio gratuito que se monetizará después. La estructura de suscripciones sigue totalmente abierta: el intervalo **15–50 €/mes es una intuición inicial**, no precios aprobados, márgenes calculados ni funcionalidades contratadas.

**Hipótesis de segmentación:** el acceso a procesos acelerados con GPU podría corresponder a planes **Pro**. **No está aprobado**; no hay que convertir esa sugerencia en una condición del código ni asumir que toda edición Pro debe usar GPU. Es razonable comparar aceleración GPU solo donde aporta valor real por etapa y unidad de coste.

**Infraestructura GPU:** existen créditos experimentales del propietario en **RunPod**, por lo que tiene sentido usar ese proveedor como laboratorio para medir, no comprometer la infraestructura definitiva. Alternativa futura: GPU bajo demanda en el ecosistema Google Cloud para reducir integraciones/latencia si la disponibilidad, cuotas, coste real y perfil de carga lo justifican. Ningún proveedor, GPU, modalidad de pago o tiempo está elegido.

**Estado de madurez:** existe mucho código avanzado y bien cuidado, pero algunas funciones transversales —suscripciones, aislamiento multiusuario, persistencia duradera de jobs, scheduler, cálculo de costes— pueden estar por diseñar. La falta de estos componentes **no implica fallo del prototipo**; son requisitos de maduración hacia producto de pago.

**Implicaciones para el estudio:**

1. Instrumentar **coste por proyecto y por operación**: tiempo local, tiempo CPU cloud, tiempo GPU, bytes originales/proxy/segmentos, almacenamiento residual y transferencia de salida, además del tiempo de preparación/cola/inicio.
2. Comparar **cuándo la GPU ahorra tiempo neto**; tener en cuenta esperas, inicio del equipo, carga de modelos y transferencia. No presuponer superioridad en FFmpeg o la mezcla de audio.
3. Estimar margen por perfil de consumo y concurrencia **antes** de fijar cuotas: usuarios ligeros, medios y exigentes; límites de trabajos, almacenamiento, GPU y tamaño de vídeos, evitando diseñar una «tarifa ilimitada» implícita.
4. El primer coordinador podría ser un **motor de reglas** auditable que opere con capacidades/plan/cuotas/coste estimado; la asignación por plan es **un parámetro configurable**, no una política cerrada.
5. La planificación de SaaS de pago requiere contabilidad de uso, identidad, atribución de jobs a cuenta y cuotas verificadas **en backend**; no usar datos del navegador como fuente de verdad.
6. El laboratorio RunPod puede aprovechar créditos actuales, pero el análisis de coste comercial debe computar **precios reales sin descontar créditos promocionales**, para no falsear la viabilidad.

**Acción inmediata:** continuar inventario técnico y tests; no activar GPU de pago, servicios nuevos ni cobrar usuarios. Revisar posicionamiento y costes después de evidencia reproducible.
