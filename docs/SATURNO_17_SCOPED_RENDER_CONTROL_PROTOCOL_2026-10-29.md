# SATURNO-17 — protocolo QA para el renderizador real (preparación)

Fecha: 2026-10-29. Rama única `fernando/continuacion-montara`.

## Evidencia que autoriza el siguiente experimento

SATURNO-16: A/B exacto en los seis segmentos 360, 1259/1259 fotogramas, con `-fps_mode passthrough` añadido al decodificador; A/A repetido exacto para cada ventana. Ver `docs/SATURNO_16_SIX_WINDOWS_RESULTS_2026-10-29.md`.

La función `core/spherical_motion.py:_run_reprojected_command` en engine fijado `60a7b7e9a39077b36f45057811abd6a833a168ef` crea el proceso de decodificación mediante `subprocess.Popen(decoder_command,...)`; esto es distinto del comando del encoder que instrumentaba el control SATURNO-12.

## Próxima pregunta única

¿Permanece la equivalencia de los píxeles de una salida reproyectada por Zucker en un segmento 360 con el mismo control QA aplicado **únicamente al Popen del decodificador**?

Primero probar únicamente el segmento 0003 para validar guardia de argv, conteo de intervenciones, A/A y A/B. Solo si funciona ampliar a otros segmentos o al montaje real A/A/B de SATURNO-12.

## Preparación publicada, no resultado

`experiments/saturno_17/qa_decoder_override.py` ofrece un context manager que cambia temporalmente `subprocess.Popen` en un proceso aislado. Solo transforma comandos reconocidos como decoder `fps=...,format=bgr24` con `-frames:v N -f rawvideo pipe:1`; añade `-fps_mode passthrough` y registra originales y efectivos. Se restaura la función en `finally`. Este helper **aún no ha sido probado con un render real** y no debe usarse concurrentemente con otros renders en el mismo proceso. La guardia no modifica el engine en disco.

Antes de lanzar: construir harness de un segmento con ruta A y B que utilice el renderizador real, verificar el número de interceptaciones esperado, reproducir las opciones de encoder QA `-threads:v 1`, controlar source/cache isolation e instrumentar hashes de salida. Sin demostrar estos controles, no reportar C aprobado.

Se prohíbe afirmar que SATURNO-16 prueba igualdad final de montajes. Los hitos B selectivo y D transferencia/coste siguen pendientes. No se habilita ningún gasto cloud ni render completo en esta preparación.

## Instrumentación de resultados

En las futuras Actions almacenar resumen compacto con run ID en ruta versionada de la rama. El helper `experiments/saturno_common/persist_run_summary.py` está preparado pero **no está integrado**; requiere validar permisos y la política de push/no bucles. No atribuirle automatización aún.
