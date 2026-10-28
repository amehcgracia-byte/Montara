# LUNA 08 — créditos de prueba y control de cambios con IA (2026-10-28)

Investigación documental, sin compras, activación de servicios ni cambio de motores. Verificar de nuevo ofertas el día de contratación.

## Nubes temporales
- Google Cloud: $300 en 90 días; durante Free Trial **no se pueden añadir GPU a VMs**, ni aumentar cuotas sin cambiar modalidad. https://cloud.google.com/signup-faqs y https://docs.cloud.google.com/free/docs/free-cloud-features . Excelente para baseline CPU x86_64 16/32 GB, no para benchmark GPU durante prueba.
- Azure: $200 en 30 días; crédito no consumido caduca. https://learn.microsoft.com/es-es/azure/cost-management-billing/manage/create-free-services . Laboratorio CPU alternativo si la máquina deseada está habilitada en la suscripción.
- Alibaba: pruebas por producto, no validar un crédito general de $90 ni 30–90 días ECS sin ver ficha y elegibilidad. https://www.alibabacloud.com/help/es/user-center/product-overview/learn-about-free-trials . Requiere tarjeta y usuario nuevo para ECS; catálogo mutable.
- Tencent: una página internacional promueve 3 meses CVM S5 2C4G; portal chino oficial de campaña muestra algunas ofertas de 7 días y agotadas. No prometer 90 días garantizados en España. https://indonesia.tencentcloud.com/solutions/game y https://cloud.tencent.com/act/pro/free .
- Oracle Always Free: servidor ARM candidato a largo plazo, aún sin validación completa del lock ARM64.
- RunPod $300 de crédito de usuario: GPU experimental bajo demanda, no confundir con hosting gratis.
- Abacus AI Cloud https://cloud.abacus.ai/pricing : Basic $10/mes y Pro $20/mes, primer mes gratis con tarjeta y renovación si no se cancela, horas GPU incluidas 2/10 respectivamente; verificar recursos reales, política de FFmpeg/jobs y cobro por créditos. No aceptar claims comparativos propios como benchmark de Montara.

## Ideas de control de versiones para José Manuel y Fer
### Anthropic Scion
Fuente: https://www.anthropic.com/research/redesigning-source-control (2026-10-15), sistema **interno**, no reemplazo abierto directo de Git recomendado. Escala para decenas de miles de cambios por día y clientes agentes siempre conectados. Las ideas trasladables son consultas remotas sobre metadatos, objetos inmutables direccionados por contenido y caches, CI post-merge. No adoptar infra Spanner ni inventar un Scion para dos personas.

### Entire, de Thomas Dohmke
https://entire.io/blog/hello-entire-world y https://entire.io/about/cli , open-source CLI con Checkpoints enlazados a commits; conserva prompts/decisiones/contexto y puede mejorar handoffs y auditorías. No acelera directamente HTTP ni FFmpeg. Comprobar privacidad de logs, tamaño, secretos y compatibilidad de agentes antes de instalar. No sustituir Git ni el flujo de PR.

## Campaña A/B propuesta
1. Fijar SHA Montara/submódulos y fixture representativo, mismos cambios/cortes, calidad y salida.
2. Linux x86_64 con 2 vCPU/8GiB baseline conocida (Stage 329.192s export de 100.233991s); repetir en VM Google 2CPU/8GB y luego 4CPU/16GB y 8CPU/32GB, SIN atribuir diferencias solo a RAM: CPU/hardware simultáneamente.
3. Medir frío/caliente, cronómetro export y recorrido completo, cgroup memory.peak, disk peak, I/O, potencia/codec, RAM límite, bytes transferidos y coste del uso real.
4. ARM64 Oracle separado si build/preflight completo; GPU RunPod mismo plan e input, más transferencia + cola + encode + download.
5. Calcular tiempo remoto total y créditos gastados. Elegir hosting permanente solo cuando se conozcan costos e aislamiento.

## Estado
Todo investigación y propuesta de pruebas. N/D si proveedor no certifica oferta por región; no desplegado. Evitar instalar herramientas de captura de prompts/contextos de agentes en repo compartido sin revisión de privacidad y autorización.
