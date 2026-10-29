# SATURNO-24 — prueba integral Stage con GOP selectivos

Fecha: 2026-10-29. Rama `fernando/continuacion-montara`.

**Estado:** protocolo publicado y GitHub Actions configurado para lanzamiento por cambio del workflow. No hay resultados científicos todavía.

## Problema controlado
SATURNO-18 certificó A/A/B completo con paquete conservador. SATURNO-23 certificó A/A/B de fragmentos reproyectados 360 con 8/45 GOP y ahorro de 82.27% en fuente sintética. SATURNO-24 combina empaquetado realmente selectivo, plan Stage real, audio master real y aislamiento del original en B.

## Diseño
- Usar las tres cámaras originales del fixture Stage, pero crear versiones **extendidas** duplicando contenido de vídeo tres veces mediante remux stream-copy (sin reencodificar los paquetes originales). Esto introduce duración no utilizada, necesaria para medir ahorro selectivo.
- El plan Stage original se reescribe hacia esas fuentes extendidas en A, y hacia los paquetes selectivos en B. Se conserva el plan de 19 segmentos y 7 movimientos 360.
- Mantener en B todo el primer ciclo de vídeo, además de GOP primero/último, ventanas de segmentos y muestras de color según el código de preflight; eliminar GOP de las repeticiones no necesarias y verificar PTS/DTS y hash de payload de los paquetes seleccionados.
- Usar las mismas funciones de exportación real que SATURNO-18 y controles QA de decodificador/encoder. Exportar A, A_repeat y B en procesos separados.
- B se ejecuta con namespace de montaje privado y tmpfs que ocultan originales del fixture, fuentes extendidas y las carpetas de A y A_repeat; cachés inicialmente vacíos.
- Comparar 3007 fotogramas, PCM de audio, paquetes de tiempo y SHA-256 de MP4. Medir bytes reales de entradas extendidas y selectivas.
- Reportar bytes de vídeo descartados y limitaciones: las grabaciones fueron alargadas artificialmente para crear contenido prescindible; esto **no demuestra tasa típica de ahorro en vídeos reales** ni rendimiento de red. La primera validación integral también podría fallar por dependencias de color, demux, mux o perfil temporal.

## Artefactos y controles
Script `experiments/saturno_24/full_selective_isolated.py`.
Workflow `.github/workflows/saturno24-full-selective.yml`, Ubuntu 24.04, acceso de solo lectura, rama de investigación, sin RunPod/Oracle, motor y mixer intactos. Línea de resultado en Actions: `SATURNO24_SUMMARY`.

**Criterio de éxito:** `PASS_FULL_SELECTIVE_ISOLATED_AB`, con vídeo selectivamente reducido, A/A y A/B exactos en imagen, audio y timestamps (más SHA MP4 idéntico). Éxito de Actions sin estos criterios no debe contarse como victoria científica.

La medición de transferencia real y costes (hito D) seguirá pendiente incluso si esta prueba pasa.
