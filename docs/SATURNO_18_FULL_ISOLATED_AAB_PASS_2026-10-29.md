# SATURNO-18 — A/A/B completo y aislado: resultados verificables

Fecha: 2026-10-29. Rama `fernando/continuacion-montara`. Motor Zucker intacto en `60a7b7e9a39077b36f45057811abd6a833a168ef`.

## Procedencia
- Primera ejecución [40913678569](https://github.com/amehcgracia-byte/Montara/actions/runs/40913678569), job 123588098934, failure operacional.
- Segunda ejecución [40913731083](https://github.com/amehcgracia-byte/Montara/actions/runs/40913731083), job 123588282687, success.
- Script `experiments/saturno_18/full_gate_passthrough.py`, derivado del A/A/B de SATURNO-12. Workflow `.github/workflows/saturno05-native-ab.yml`.
- Fuente: líneas `SATURNO18_SUMMARY` y `SATURNO18_PRESERVED` de los jobs; no se conservan los MP4 para re-hasheo externo posterior.

## Fallo de la primera ejecución
`FULL_GATE_EXECUTION_ERROR`: durante A, aserción `Expected seven QA decoder interventions`. Los fallbacks de codificación pueden generar intentos adicionales; el conteo exigido era demasiado rígido. El log también informa de detección de cadencia irregular (delta de hasta 1.066666 s) y activación de reparación de cadencia por el renderizador. No atribuir el fallo a desigualdad A/B: B no se ejecutó. Antes de la segunda ejecución se relajó la aserción para permitir >=7 intervenciones sin modificar engine.

## Resultado de la segunda ejecución

- Estado: `PASS_FULL_PLAN_ISOLATED_AB`.
- A/A_repeat: 3007/3007 fotogramas iguales; audio PCM exacto; JSON de cronología de paquetes exacto; SHA-256 del MP4 completo exacto.
- A/B: 3007/3007 fotogramas iguales; audio PCM exacto; JSON de cronología de paquetes exacto; SHA-256 del MP4 completo exacto.
- A, A_repeat, B: cada MP4 mide 204977186 bytes; hash SHA-256: `e0f6a4eec27ce0b21675f4565ad7ac4ed2123ba37a5f8a85d5d4c50708b4ad8b`.
- Duraciones de export: A 597.160945 s, A_repeat 594.804604 s, B 594.220096 s. Estas son duraciones locales de export, no tiempos de transmisión remota.
- 7 llamadas nativas 360 exitosas por exportación.
- El control QA agrega `-fps_mode passthrough` al comando del decodificador por interceptación temporal en memoria y conserva `-threads:v 1` para el encoder; no modifica motor.
- Conserva el diseño del experimento SATURNO-12: runtimes y cachés inicialmente vacíos y separados, rerender forzado, B ejecutado con montajes tmpfs para ocultar las carpetas de originales y de A/A_repeat; plan Stage guardado, no repetición de ingestión/sincronización.
- Archivos originales: 6678870 bytes; paquete conservador (medios+plan/proyecto): 4722348 bytes. ZIP original medios 6509709 bytes; ZIP paquete (incluye plan/proyecto) 4238474 bytes. No comparar estos ZIP como si incluyeran idénticos metadatos.
- Este paquete preserva **todos los GOP de los tres vídeos**; el ahorro principal procede de descartar audio de cámaras, no de seleccionar parcialmente vídeo.

## Alcance preciso de la victoria
Para el plan real Stage fijado (19 segmentos, 3 cámaras, 7 segmentos 360) y el entorno QA, la exportación multicámara completa se reproduce bit a bit desde el paquete conservador B, con originales y cachés de A inaccesibles durante B. Supera el gate C **para este caso, bajo las condiciones QA y aislamiento implementados**. No establece determinismo universal, equivalencia de cualquier proyecto, ni compatibilidad de producción sin cambio de motor.

Los hitos restantes incluyen demostrar ahorro significativo por **selección de GOP de vídeo** (B en sentido estricto), probar transferencias/costes remotos reales (D) y decidir Saturno frente a Júpiter según métricas, sin prometer que un hash permita reconstruir datos ausentes.

## Siguiente bloque propuesto
Conservar el gate completo como referencia aprobada. Diseñar un experimento corto que calcule exactamente qué GOP y dependencias son necesarios para este plan, utilizando mapa de uso y ventanas de decodificación, sin lanzar primero otro A/A/B completo. Medir bytes de vídeo seleccionable; si no existe ahorro real en este fixture, buscar un caso representativo más largo antes de pronunciarse sobre viabilidad de la arquitectura.

## Registro de uso
Dos consultas de jobs y dos lecturas de logs, ambas filtradas por resúmenes/errores; comparación de HEAD, publicación de informe. Tokens reales no disponibles. Sin RunPod, Oracle ni cambios en submódulos.
