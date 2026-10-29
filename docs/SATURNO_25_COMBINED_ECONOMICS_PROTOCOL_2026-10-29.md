# SATURNO-25 — Protocolo unificado de bytes, empaquetado y economía

Fecha: 2026-10-29. Rama `fernando/continuacion-montara`. Estado: Action publicada, **sin resultado todavía**.

## Objetivo
Cerrar la medición local/controlada del hito D sobre el caso de SATURNO-24, **sin repetir ningún render**. Se mantienen las tres fuentes extendidas artificialmente por stream-copy y el criterio conservador de selección de GOP, incluyendo ventanas usadas y muestras de color. Se verifican payload, PTS y DTS de cada paquete conservado.

## Fases de una sola Action
1. Preparación: registrar tiempo medido de generación de fuentes extendidas y del paquete selectivo, número de GOP y tamaños de medios de A y B, en idéntica base de comparación. El coste de preparación incluye generación de fuentes extendidas de laboratorio: no estimarlo como coste de un flujo de producción.
2. Archivo: crear ZIP de medios originales y ZIP del paquete completo que incluye `plan.json` y `project.json`; medir tiempos y tamaños. **Los ZIP no contienen el mismo tipo de ficheros**, por lo que se registran además los tamaños de medios en base homogénea. Los recursos software compartidos no se incluyen.
3. Transferencia: tres solicitudes HTTP POST del ZIP original y tres del paquete hacia un servidor receptor local `127.0.0.1` en el mismo runner; medir tiempo con reloj monotónico y certificar cada SHA-256 recibido. **Esta prueba NO mide Internet, ancho de banda de subida de un usuario, latencia WAN ni dos servidores diferentes.** No extrapolar sus tiempos a producción.
4. Escenarios económicos: calcular euros por 10.000 transferencias hipotéticas para 0.02, 0.05 y 0.10 €/GB decimal, con tarifa **hipotética, no un precio contratado**. Son cálculos de bytes ahorrados: no incluyen CPU, almacenamiento de caché, renderización, transferencia de entrada que pudiera cobrar un proveedor, operación o concurrencia.

## Éxito
`CONTROLLED_PREPARE_TRANSFER_ECONOMICS_MEASURED` solamente si la preparación funciona, recepción hash coincide, el paquete selectivo contiene menos bytes que los originales tanto en medios como ZIP y se calculan tiempos/escenarios. No equivale a hito D completo en red real.

Código: `experiments/saturno_25/transfer_economics.py`.
Workflow: `.github/workflows/saturno25-transfer.yml`.
Resultado impreso: `SATURNO25_SUMMARY`, `SATURNO25_PRESERVED`.

La prueba de transferencia remota real requiere una infraestructura y condiciones de red explícitas y medibles, aún no disponibles; no se han autorizado gastos de RunPod/Oracle. Nada se modifica en los motores, `main` o `mixer`.

## Decisión sobre Júpiter
SATURNO-18/24 ya probaron equivalencia del montaje completo bajo QA y SATURNO-20/23 ahorros selectivos en vídeo sintético. SATURNO-25 podrá ofrecer un informe local de tamaños y tiempos, pero la generalización a vídeos reales, GOP abiertos y WAN aún exige una matriz de validaciones separada antes de declarar éxito universal.
