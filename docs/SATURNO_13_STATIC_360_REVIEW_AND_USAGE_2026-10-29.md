# SATURNO-13 — revisión estática del primer segmento 360 divergente y uso de herramientas

Fecha: 2026-10-29. Bloque limitado a lectura de código/registros y documentación. Sin renders nuevos, navegador, consultas web ni subagentes.

## Punto de partida

HEAD comprobado antes de la revisión: `e8fa77695a6ddaca05bf734efac8719fc78ad980` en `fernando/continuacion-montara`.

Se reutilizan los resultados recuperados de SATURNO-12. La divergencia de seis segmentos 360 está registrada antes del ensamblado; los doce segmentos planos y el primer 360 tienen MP4 idénticos. No se repite la comparación completa.

## Recorrido del segmento 0003

Plan guardado: `experiments/saturno_10/stage_edit_plan.json`.

- Fuente original: `tests/fixtures/much-to-me/cam-360.mp4`.
- Inicio de cámara: `21.76784580498866` s.
- Inicio en master: `14.5` s; primera imagen final divergente a 24,5 s al incluir la intro.
- Duración del segmento: `9.266667000000002` s; codificador observado: 278 fotogramas a 30 fps.
- Movimiento: `settle`, pose guardada yaw 164, pitch -17, fov 90; sweep_enabled/intershot_sweep false.
- Precede el plano 0002 de cámara plana; el anterior 360 es 0001. En esta ruta, la función de continuidad solo añade previous_shot si se habilitan las condiciones de sweep, ausentes en 0003.

Engine inspeccionado, sin modificaciones: `amehcgracia-byte/zucker_videos@60a7b7e9a39077b36f45057811abd6a833a168ef`.

1. `core/stages/export.py:_segment_source_info` (línea 4132) selecciona el registro mediante source_path/clip_path y devuelve la ruta original y metadatos probe.
2. `_render_segment` (2295) activa native_motion según spherical_shot y proyección equirectangular.
3. La llamada (2458–2462) entrega fuente, dimensiones, clip_start_sec completo, frame_count y shot a run_reprojected_command. Para settle, la expresión de 2457 deja pose_sampler en None.
4. `core/spherical_motion.py:_run_reprojected_command` construye el decodificador (187–188), lee cuadros BGR completos y aplica motion_pose por índice/fps (243). Remapea con OpenCV y escribe al pipe del codificador (252–254).
5. Los comandos exitosos de codificación observados en SATURNO-12 coinciden A/B salvo su ruta de salida. Sus filtros de color también coinciden. Los argumentos de entrada al reproyector y los hashes de imágenes del pipe no fueron capturados en esa prueba; no se infiere su igualdad a partir del comando de salida.

Comando de decodificación reconstruido **estáticamente**, no capturado de un proceso nuevo:

```text
<ffmpeg> -hide_banner -loglevel error -nostdin -threads 2
  -ss 21.76784580498866 -i <fuente A o B>
  -vf fps=30,format=bgr24 -an -frames:v 278 -f rawvideo pipe:1
```

Corresponde a la rama CPU, sin decode_size. La ruta Linux usada evita la selección de hardware de macOS. No sustituye una traza real de parámetros.

## Diferencia metodológica encontrada

`experiments/saturno_10/packet_preflight.py:64–73` comprobó ventanas con el mismo seek completo y filtro fps=30,format=bgr24 para 360, pero añadió opciones de salida `-map 0:v:0 -pix_fmt bgr24 -fps_mode passthrough`.

El decodificador real de `spherical_motion.py:187–188` no fija `-fps_mode passthrough`. **Los comandos no son idénticos.** La opción puede ser relevante para investigar selección/cadencia, pero esta revisión no demuestra que produzca el fallo. No se declara falso el resultado previo: se limita su alcance al comando que efectivamente comprobó.

No hay todavía evidencia suficiente para atribuir la divergencia a decodificación, reproyección, poses o empaquetado.

## Siguiente prueba propuesta, no ejecutada

Pregunta: ¿el decodificador nativo exacto entrega los mismos 278 cuadros BGR para A y B en el segmento 0003?

- Usar las fuentes y receta de paquete ya verificadas, y confirmar hashes.
- Reproducir el comando exacto de decodificación, sin añadir passthrough ni cambiar opciones.
- Medir hashes por fotograma, cantidad y primera diferencia; incluir como control el comando previo con passthrough para aislar esa diferencia metodológica.
- Si la entrada ya difiere, cerrar ese bloque con la evidencia y estudiar seek/cadencia/metadatos. No hacer reproyección ni export completo para ese diagnóstico.
- Si la entrada coincide, cerrar ese bloque y plantear comparar parámetros/poses y cuadros reprojectados del mismo segmento en un bloque posterior.

No se ha creado ni despachado un workflow nuevo. No se modifica el motor para instrumentarlo. Cualquier intervención en sus fuentes requiere autorización.

## Registro de uso y límites de medición

**Tokens consumidos: no disponibles.** Esta sesión no expone telemetría fiable de tokens de entrada/salida, uso facturado ni la fórmula del porcentaje de contexto del cliente. No se inventa una cifra ni se convierte caracteres a tokens como si fuera medición.

Se usa el conector GitHub, no HTML ni navegador. Lecturas remotas de investigación: 5. Tamaño agregado del campo textual de contenido recuperado: **683811 unidades UTF-16**, contado con JavaScript string.length, sin envoltorios del protocolo ni metadatos de herramientas.

| Lectura | Unidades UTF-16 del contenido |
| --- | ---: |
| read branch ref | 432 |
| experiments/saturno_10/stage_edit_plan.json | 384712 |
| core/spherical_motion.py | 16311 |
| core/stages/export.py | 270184 |
| experiments/saturno_10/packet_preflight.py | 12172 |

Estos contenidos se almacenaron en el contexto de ejecución de herramientas y se emitieron fragmentos seleccionados al modelo; el total recuperado **no equivale** a tokens incorporados al contexto. El volumen exacto de texto de herramientas visible al modelo no se contabilizó en esta sesión.

Operaciones previstas para cerrar este informe: una creación de archivo en nuestra rama, y dos lecturas de verificación (HEAD y ejecuciones asociadas al nuevo commit). El recuento final se comunicará con sus resultados. Las llamadas de descubrimiento de herramientas, inspección de la captura adjunta y filtrado local se distinguen de las 5 lecturas GitHub de investigación.

Navegador: 0 llamadas en este bloque. Web: 0. Renders: 0. Subagentes: 0. Lecturas repetidas de los mismos archivos: 0 en este bloque; se reutilizan los JSON SATURNO-12 de la recuperación anterior.

La captura aportada por el usuario muestra un navegador con GitHub 404 de un intento del bloque antiguo, y una fuente web x264-devel de la investigación anterior. No acredita una extracción masiva de HTML ni permite calcular su coste. En el historial sí hay actividad evitable conocida: sondeos prolongados y volcados extensos/redundantes de resultados. No se puede cuantificar retrospectivamente su consumo ni afirmar una fuga técnica solo con esos indicios.

Medidas operativas: filtrar antes de mostrar, reutilizar evidencia, no imprimir JSON completos, no sondear trabajos largos continuamente y cerrar cada bloque con alcance y conclusión.
