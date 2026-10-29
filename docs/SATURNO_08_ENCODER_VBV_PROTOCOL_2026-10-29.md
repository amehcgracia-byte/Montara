# SATURNO-08 — Repetibilidad del primer comando y control del codificador

## Estado inicial y procedencia
Base de rama: `58b42315d1ab3e4f61b807b058394bdcfec80641`.
Única rama modificable: `fernando/continuacion-montara`. No cambiar main, engine ni mixer.
SAT-07 run 40865264794: primer segmento A/A 55/60 exactos (53–57 difieren).
El control posterior run 40865665003 ya probó `-filter_complex_threads 1`: A/A 53/60,
índices 53–59. No repetirlo. Los comandos originales A/A, salvo destino, son idénticos.

## Hipótesis apoyada en fuente primaria
El comando usa libx264, bitrate 2 Mbps, maxrate 2.4 Mbps y bufsize 4 Mbps (VBV),
sin fijar los hilos del codificador. Limitar filter_complex NO limita libx264.
En la lista oficial x264-devel, Zhi Li documentó no repetibilidad con varios hilos y VBV,
y Henrik Gramner confirmó ese comportamiento el 17 de abril de 2015:
- https://mailman.videolan.org/pipermail/x264-devel/2015-April/011035.html
- https://mailman.videolan.org/pipermail/x264-devel/2015-April/011036.html
- Documentación del wrapper libx264 de FFmpeg (opción threads):
  https://ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb

Es una comunicación técnica primaria histórica, no un paper ni una prueba de causalidad
para nuestra versión. No se extrapola desde x265 ni se atribuye el fallo a Zucker.
La hipótesis se evalúa con intervenciones controladas y refutables.

## Protocolo consolidado (aún sin resultado al escribir este documento)
`experiments/saturno_08/first_command.json` conserva el comando REAL exitoso de SAT-07,
run 40865264794/job 123418303750. Sustituir solamente ejecutable local, entrada fixture
y salida de cada repetición. Verificar SHA git del fixture para impedir deriva inadvertida.
Tres repeticiones independientes por brazo, en el mismo runner:

| Brazo | Intervención respecto al comando capturado | Pregunta |
|---|---|---|
| original | Ninguna transformación audiovisual | ¿Se reproduce la variación fuera de Zucker? |
| encoder_one | Añadir `-threads:v 1` en ámbito OUTPUT | ¿Se estabiliza al limitar el codificador? |
| without_vbv | Quitar solo maxrate y bufsize | ¿Se estabiliza sin VBV? |
| filtered_framehash | Mismos input/filtros, sustituir salida lossy/MP4 por rawvideo framehash | ¿Los filtros entregan píxeles y tiempos repetibles? |

Conservar comandos efectivos, versión/build FFmpeg, CPU, SHA fixture y archivos,
hashes SHA256 decodificados de CADA fotograma, PTS y tiempos de cada proceso.
No confundir hashes de MP4 con identidad de píxeles ni una mejor compresión con
selección correcta de imágenes. No comparar píxeles entre brazos como requisito:
cambiar parámetros del codificador puede cambiar su resultado legítimamente.

Si el control encoder_one da 60/60 y PTS iguales en sus tres repeticiones, ejecutar
en EL MISMO JOB el harness nativo existente con `SATURNO_QA_ENCODER_THREADS_ONE=1`:
interceptar únicamente argumentos en memoria, sin escribir el motor. Fundidos activos;
sin override de hilos de filtros. A/A y B copia completa idéntica, original de vídeo
oculto durante B. Registrar comando de motor Y comando efectivo de QA.
El gate nativo exige ahora tanto A/A como A/B y exactamente 60 frames en A/A;
antes el código de salida solo comprobaba A/B, una limitación del harness.

## Interpretación predefinida
- Original variable + raw estable + encoder_one estable + sin VBV estable:
  evidencia convergente de variación en codificación bajo combinación hilos/VBV.
  No prueba que desaparezca en todas las fuentes o plataformas.
- Si raw varía, investigar filtros/decodificación/PTS antes de atribuir al encoder.
- Si original no varía, la no repetibilidad no se reproduce en esta muestra;
  no declarar resuelto el problema por ausencia de fallo en tres repeticiones.
- Si encoder_one falla, no ejecutar un A/B nativo bajo un baseline aún inestable.
- Incluso nativo 60/60 NO aprueba paquete reducido, Stage multicámara/360, audio
  aislado ni costes. A/B aquí usa copia COMPLETA, no ahorro de transferencia.

## Ejecución y notificaciones
Una sola ejecución consolidada al actualizar el workflow existente en la rama autorizada.
No crear PR (dispararía el E2E de cuatro jobs), no subir artefactos sujetos a cuota.
Logs contienen evidencia; guardar un resumen versionado después de verificar el run.
Colección de diagnóstico exitosa usa `DIAGNOSTIC_COMPLETE`, no `PASS_SATURNO`;
los gates de igualdad nativa siguen fallando explícitamente si no se cumplen.

## Limitación local
El conector GitHub disponible no entrega el fixture binario (fetch_file vacío para
archivo >1 MB; fetch_blob intenta UTF-8 y falla). Git HTTPS local no está autenticado.
No inventar una ejecución local: los medios reales se leen mediante checkout de CI.
