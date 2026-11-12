# Procesos y estudios de optimización híbrida — Montara

**Fecha:** 2026-11-12  
**Rama de documentación:** `fernando/chema-native-owner`  
**Carácter:** revisión de arquitectura, ciencia aplicada y decisiones de producto; **no** benchmark nuevo ni autorización de implementación.  
**Estado:** propuesta de evolución posterior a la validación funcional H4.  
**Propietarios funcionales:** equipo Montara; integración en `main` sujeta a revisión y decisión de Chema/JM.

## 1. Decisión ejecutiva y límites

**Dirección propuesta:** Montara debe asignar cada tarea a la ejecución local o remota que mejor preserve la calidad, la privacidad, el tiempo hasta el resultado, la experiencia de uso y el coste. El Companion Windows/macOS será **gestor de originales, ejecutor y observador de recursos**; el servidor, **autoridad de identidad/proyectos, coordinador y capacidad de cómputo adicional**. El planificador no tiene por qué ser inicialmente autónomo ni basado en IA; empezar con reglas y mediciones.

**No hay decisión definitiva** sobre dónde deben ejecutarse análisis, sincronización, edición, mezcla ni render: la implementación H4 actual es una referencia **en construcción**, no una prueba de superioridad de la nube. El servidor no debe recibir vídeos originales por defecto. Las subidas excepcionales requieren consentimiento y aislamiento. El resultado final de máxima calidad debe provenir de los originales —localmente o mediante datos originales seleccionados verificados—, **nunca de ampliar un proxy con pérdida**.

**Secuencia acordada:**
1. Cerrar el recorrido humano real H4 con el editor original de Chema: ingest local, proxy, transferencia, audio, sincronización/mezcla, receta, render local, recuperación y descarga; corregir sólo incidencias concretas. H4 aún **NO** está funcional extremo a extremo.
2. Congelar evidencia reproducible y auditar diferencias respecto al `main` vigente. Entregar cambios pequeños, con pruebas y revisión de Chema; **nunca fusionar la rama experimental completa**.
3. Una vez integrada la base funcional, hacer pruebas y benchmarks **en rama/laboratorio aislado**, contra esa misma referencia, sin modificar ni bloquear `main`.
4. Adoptar únicamente cambios con beneficio medido y sin regresión visual/audio, seguridad ni propiedad de proyectos.

## 2. Arquitectura actual frente a arquitectura candidata

### H4 observado (no es todavía un éxito E2E)
- Chrome y Companion 0.6.10 conectan; el original queda en PC y se genera una versión reducida.
- El navegador **sube el proxy pequeño por HTTPS al worker/servidor H4**, usando la lógica de uploads de Chema. Una prueba humana mostró subida interrumpida y una entrada de vídeo marcada `ERROR`; **no se certifica ingest completo**.
- El editor remoto intenta usar `/montara/mix`, ruta aún no habilitada en el gateway privado H4 según inspección del 12-11; no confundir con avería del motor.
- Los fallos anteriores de `/montara/branding` estaban ocasionados en una repetición por `/urano/v1/native/ensure` HTTP 503 y un job `orphaned` tras reinicio. El registro concreto se recuperó de forma verificada; todavía es necesaria una política duradera de recuperación y prueba humana tras reinicios.
- El código original de Chema incluye `/edit/native-recipe`, comprobación de Engine del Companion, relink de originales y render local. El gateway H4 aún no expone todas las rutas para el recorrido completo.
- En macOS/Windows, el Companion podría gestionar cargas de trabajo locales; **no asumir que todas las funciones tienen paridad**.
- Diferenciar `proxy de ingest`, `preview`, `GOP original selectivo`, `características acústicas/visuales` y `original`: objetos con propósitos y garantías de fidelidad diferentes.

### Arquitectura candidata: planificación híbrida por tarea
```text
Original(es) inmutables en PC
      |
      +--> Companion: detección/huellas, caches, recursos, proxies si hacen falta
      |         |                         |
      |         | características/receta   +--> render original local cuando conviene
      |         v
      +--> Servidor Owner: identidad + proyectos + coordinación + motor remoto opcional
                |
                +--> analizar/editar sobre datos mínimos si compensa
                +--> render remoto sólo con segmentos originales/dependencias necesarias
                +--> devolver receta, master/resultado y pruebas de integridad
```
El planificador sólo asigna operaciones sobre las que un ejecutor dispone de datos suficientes. Para un render remoto con fidelidad original **hay que transferir información de origen suficiente**. No existe una compresión sin pérdidas universal capaz de reconstruir un original arbitrario a partir de un proxy lossy. Tampoco puede sumarse RAM de PC y VM como si formara memoria compartida de baja latencia. El paralelismo entre segmentos es posible, pero introduce transferencia, sincronía, encoders compatibles, unión y verificaciones.

## 3. Pruebas históricas recuperadas: resultados vs producción

Fuentes en `fernando/continuacion-montara`:

| Ensayo / documento | Evidencia | Limitación / conclusión |
|---|---|---|
| `docs/SATURNO_24_FULL_SELECTIVE_ISOLATED_RESULTS_2026-10-29.md` | Selección de GOP de origen. 3007/3007 frames idénticos, PCM y cronología idénticos, SHA-256 MP4 A/B idéntico; bytes de medios 9.549.037 → 5.744.051 (−39,85 %). | Material controlado, vídeos extendidos artificialmente y ajustes QA. Render sólo ~0,30 % más rápido en esa prueba. **No** certificado multiformato ni WAN. |
| `docs/SATURNO_25_CONTROLLED_TRANSFER_RESULTS_2026-10-29.md` | ZIP 9.260.068 → 5.682.115 bytes (−38,64 %); hashes de recepción correctos. | Transferencia **loopback 127.0.0.1**, no red del usuario. No inferir beneficio WAN ni ahorro económico universal. |
| `docs/JUPITER_OPT_06_SATURNO_GOP_DECISION_2026-10-30.md` | Evaluación cerrada: GOP selectivo candidato para transferir menos bytes. | No reabrir GOP como optimización de velocidad de render sin otro cuello de botella demostrado. |
| `docs/FOCUS_AC_PROXY_EDIT_ORIGINAL_EXPORT_PASS_2026-10-30.md` | `EditStage` sobre proxies físicos 360p y `ExportStage` real desde originales; 6/6 segmentos desde origen, MP4 generado. | Ensayo sintético. No prueba E2E navegador/Windows, calidad de audio ni cámaras reales complejas. |
| `docs/AUDIT_JUPITER_03_PROXY_CACHE_RENDER_2026-10-28.md` | Se distinguieron cachés de previews, proxy completo, Show y render. Se observó fuente H.264 41,48 MiB → proxy 73,72 MiB (~78 % más) en configuración experimental. | No asumir que todo proxy ahorra bytes; presets y contenido determinan el volumen. |
| `docs/lab/PUENTE_JUPITER_URANO_INTEGRATION_TRIAGE_2026-11-05.md` | `main` ya contenía piezas de receta nativa/render local, cachés y parte de mixer. | Reutilizar las funciones de Chema; **no** hacer cherry-pick masivo de rama FER ni tocar punteros engine/mixer sin revisión. |

Los datos anteriores son **evidencia histórica de sus ensayos concretos**, no métricas extrapolables al H4 operativo. Proxies no implican reconstrucción pixel-perfect; en SATURNO la igualdad se logró con **GOP de origen**, no creando información inexistente desde 360p.

## 4. Investigación científica / tecnológica útil (consultada 2026-11-12)

### A. Scheduling local/edge/cloud
- **ASDMR: Adaptive Scheduling of DNN Models and Resources for Collaborative Edge-Cloud Video Analytics**. IEEE ICPADS 2025, DOI: https://doi.org/10.1109/ICPADS67057.2025.11323168 . Optimiza decisiones dinámicas entre latencia, coste y precisión para analítica de vídeo. **Aplicación:** inspiración para reglas de enrutamiento y feedback de recursos; no trasladar sus resultados a render Stage sin validación.
- Regla inicial: medir cómputo local `T_local`; contrastar `T_remoto = T_preparación + T_subida + T_cola + T_ejecución + T_descarga`, junto con coste, calidad, estabilidad y posibilidad de seguir editando. Un render distribuido en segmentos sólo compensa si el beneficio excede sobrecarga y coste de unión.

### B. Compresión orientada a la tarea
- **How2Compress: Scalable and Efficient Edge Video Analytics via Adaptive Granular Video Compression** (2025), https://arxiv.org/abs/2510.18409 . Control de compresión H.264 granular orientado a precisión analítica; autores reportan hasta 50,4 % menos bitrate en sus tareas. **Aplicación:** evaluar representaciones distintas para sync acústico, análisis visual, previsualización y export. **No** garantiza identidad visual, calidad de montaje ni ahorro real en Montara.
- **Principio:** no encadenar recodificaciones con pérdida sobre el camino a MP4 final. Conservar original; proxy/análisis genera **decisiones**, la receta remite al original/segmentos originales. Huellas acústicas o vectores visuales podrían reemplazar transferencias en tareas bien definidas, siempre con precisión y coste verificados.

### C. Transporte / continuidad
- **HTTP resumable uploads**, IETF Internet-Draft `draft-ietf-httpbis-resumable-upload-15`, publicado 2026-11-02: https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-resumable-upload-15 . **Es un borrador**, no una garantía de compatibilidad universal. H4 ya dispone de una vía resumable propia; arreglar integridad, reintentos, finalización, recibos y errores antes de sustituirla por otra tecnología.
- **HTTP/3 + QUIC en Cloudflare:** https://developers.cloudflare.com/speed/optimization/protocol/http3/ . Mejora potencial ante pérdidas y multiplexación; Cloudflare indica que HTTP/3 se aplica navegador→Cloudflare, no conexión HTTP/3 al origen. **No** multiplica el ancho de banda físico.
- **FTP/FTPS o túnel FTP:** no recomendable para navegador + OAuth + Cloudflare + control de acceso; no reduce bytes ni supera el uplink. HTTPS con resumable + control de transferencia es opción más simple y coherente.

### D. Hardware local y fases concurrentes
- Companion podría observar CPU, RAM libre, cola, temperatura/aceleración disponible, FFmpeg/codec, almacenamiento, ancho de banda y actividad del usuario, con consentimiento y mínimos datos. No enviar inventarios detallados del equipo innecesariamente.
- Ejecutar en segundo plano puede solapar operaciones (huellas/previews mientras se prepara el proyecto), pero también deteriorar UX si satura CPU, disco o ventilación. Limitar hilos, prioridades, trabajos simultáneos; pausar de forma segura cuando proceda.
- Codificación paralela y reparto local/nube por segmento sólo tras demostrar equivalencia A/V, economía de transferencia y continuidad de codec/GOP/color/HDR/360.

## 5. Matriz de decisiones provisional

| Opción | Estado recomendado | Justificación |
|---|---|---|
| Mantener arquitectura H4 existente durante el cierre E2E | **Sí, provisional** | Base reproducible; no debe confundirse con arquitectura final. |
| Originales locales + receta + render original local | **Objetivo base** | Preserva calidad, privacidad y evita subida de originales. Ya hay piezas en Chema. |
| Companion como agente de recursos y ejecutor | **Dirección de producto** | Planificación local/nube futura, telemetría acotada y UX. |
| Subida de proxies completos | **Condicional, no dogma** | Útiles si análisis requiere ver imágenes en servidor; evitar si metadatos locales bastan. |
| Control adaptativo de calidad/tamaño del proxy | **Candidato posterior** | Medir frente a originales comprimidos que producen proxies más grandes. |
| Audio local / enviar huellas o master final | **Candidato por flujo** | No asumir que sustituye la mezcla de Chema o garantiza sync. |
| GOP selectivo original a nube | **Candidato render remoto** | Factibilidad de laboratorio; requiere códecs y WAN reales. |
| Enrutamiento local/nube según coste/tiempo | **Después del E2E** | Empezar con reglas, no ML complejo. |
| FTP/túnel FTP | **No** | Sin ventaja probada en nuestro caso. |
| Distribución de memoria RAM o render híbrido fragmentado por defecto | **No para beta** | Complejidad y coste de transferencia/unión elevados. |

## 6. Benchmark mínimo, sólo tras H4 funcional

**Evitar un laboratorio infinito.** Una matriz muy pequeña sobre un mismo proyecto reproducible (y, si es posible, una muestra con 360 o HEVC sólo si es representativa):

- **A — Baseline real:** recorrido que ya funcione, Companion→proxy→servidor→plan→render con originales locales. Registrar duración por fase, éxito/reintentos, bytes por clase de activo y uso CPU/RAM/disco de PC y VM.
- **B — Sustituir sólo una fase justificada:** por ejemplo, extracción de huella/sync local o envío de características si el motor acepta un contrato equivalente; preservar el resto para comparación causal. Sin motor paralelo nuevo.
- **C — Render:** comparar local vs remoto/GOP **únicamente si** el perfil A revela un cuello importante y existe una ruta de equivalencia validable.

**Criterios de aceptación:** resultado funcional, sincronización, calidad perceptual y comprobación de píxeles/PCM cuando aplique, tiempos end-to-end y hasta primera interacción, volumen WAN real, coste por trabajo, consumo del dispositivo, porcentaje de trabajos reanudados, aislamiento por usuario, recuperación tras reinicio y ausencia de subida de originales sin consentimiento. Registrar versión exacta del código, engine/mixer/Companion, equipo y códecs.

**Condición de parada:** si B no reduce significativamente el cuello de botella o sacrifica calidad/fiabilidad, archivar sin otra serie de experimentos. Un ensayo comparativo útil es mejor que veinte microbenchmarks inconexos.

## 7. Protocolo de integración con Chema

- Rama de validación H4: `fernando/chema-native-owner`, conservar beta anterior; no tocar `main` directamente.
- Antes de proponer PR: consolidar sólo cambios indispensables, suprimir experimentos temporales, tests de integración y E2E humano Windows/Mac (donde aplique), seguridad multiusuario y recuperación.
- **Chema revisa y decide** integración de PR pequeñas sobre `main` actualizado. No arrastrar 400+ commits de laboratorios ni pines antiguos de submódulos.
- Tras integración, una rama separada de benchmarks (`fernando/...-hybrid-benchmark`, por crear) medirá arquitectura con el mismo `main` base; los experimentos no deben modificar el comportamiento de usuarios de la beta.
- Si el benchmark recomienda otra arquitectura, propuesta de cambio incremental y opt-in, con rollback y métricas; no reescribir la interfaz de Chema por capricho.

## 8. Pendientes inmediatos de H4 (antes de investigar nuevas arquitecturas)

1. Investigar subida del proxy marcada `ERROR`: distinguir fragmento / finalización / recibo; no permitir avanzar silenciosamente con activos fallidos.
2. Completar las operaciones reales de mezcla y demás rutas requeridas, con autorización Owner por usuario y proyecto.
3. Validar audio coincidente, edición Stage, receta, render local y MP4 final; cuidar versiones Engine y Companion.
4. Probar reanudación y recuperación del worker privado tras apagado, evitando registros `orphaned` bloqueantes; conservar protección ante procesos duplicados.
5. Documentar medidas A de transferencia/CPU, pero sin optimizar antes de disponer de un flujo de referencia válido.

## 9. Fuentes y trazabilidad

- Rama histórica: https://github.com/amehcgracia-byte/Montara/tree/fernando/continuacion-montara
- SATURNO-24: https://github.com/amehcgracia-byte/Montara/blob/fernando/continuacion-montara/docs/SATURNO_24_FULL_SELECTIVE_ISOLATED_RESULTS_2026-10-29.md
- SATURNO-25: https://github.com/amehcgracia-byte/Montara/blob/fernando/continuacion-montara/docs/SATURNO_25_CONTROLLED_TRANSFER_RESULTS_2026-10-29.md
- FOCUS proxy→original: https://github.com/amehcgracia-byte/Montara/blob/fernando/continuacion-montara/docs/FOCUS_AC_PROXY_EDIT_ORIGINAL_EXPORT_PASS_2026-10-30.md
- Auditoría integración: https://github.com/amehcgracia-byte/Montara/blob/fernando/continuacion-montara/docs/lab/PUENTE_JUPITER_URANO_INTEGRATION_TRIAGE_2026-11-05.md
- Fuentes científicas/técnicas: ASDMR, How2Compress, IETF resumable uploads y Cloudflare HTTP/3 (enlaces arriba).
- Esta nota **no** representa un gate de producción, pruebas H4 completas, una revisión legal del codec/licencias ni una aprobación de Chema.
