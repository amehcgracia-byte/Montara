# SATURNO-08 — Resultado real: control de repetibilidad estabilizado

## Veredicto acotado
Run [40878313397](https://github.com/amehcgracia-byte/Montara/actions/runs/40878313397),
job 123462779474, commit `bdb42c6bf12a18908a88556af78dd599dd73c985`.
**SUCCESS**. Este resultado cierra el diagnóstico acotado A/A de SAT-07 bajo un
control de QA del codificador; NO completa los cuatro hitos SATURNO.

Se realizaron doce replays del primer comando FFmpeg (tres por brazo) y tres
exports mediante el renderizador real Zucker. Una única ejecución de Actions.
No se modificaron main, engine, mixer ni ramas ajenas. Sin gasto RunPod.

## Resultados predefinidos
Comparaciones de repeticiones 2 y 3 contra la primera, siempre 60 frames:

| Brazo | Repetición 2 | Repetición 3 | PTS | Interpretación |
|---|---:|---:|---|---|
| Original (libx264 + VBV, hilos automáticos) | 54/60 | 53/60 | Iguales | Variación reproducida fuera de Zucker |
| Solo codificador con `-threads:v 1` | 60/60 | 60/60 | Iguales | Control estable |
| Solo quitar maxrate/bufsize (sin VBV) | 60/60 | 60/60 | Iguales | Control estable |
| Mismos filtros, salida rawvideo framehash | 60/60 | 60/60 | Iguales | Entrada al codificador repetible en este brazo |

Original rep. 2 difiere en [53,54,55,57,58,59]; rep. 3 en [53,54,55,56,57,58,59].
Los PTS son iguales incluso donde los píxeles comprimidos divergen.
Esto separa variación de píxeles de una supuesta variación de la línea temporal.

## Zucker real bajo el control de QA
Fundidos ACTIVOS, `force_rerender_segments=True`, sin override de filter_complex_threads.
Solo se añade `-threads:v 1` a comandos libx264 en memoria del harness de QA.
No es el comportamiento nativo por defecto sin intervención.

- A/A mismo vídeo y ruta: **60/60** en primer segmento y ensamblado.
- A/B copia completa byte idéntica en otra ruta: **60/60** en ambas etapas.
- Original de cámara oculto durante B: true.
- A, repetición A y B: 2.0 s, 516447 bytes y mismo SHA256 de archivo:
  `9df92693b5a5c2efa8b2fbf3fa4a691137951141380e7ce995aa09f143934fe2`.
- SHA256 de vídeo decodificado en los tres:
  `b2b0f75883d46699a63773041d543a5c82e20fb7968ca0ab3c4963fb36d4f354`
  (186624000 bytes).
- Duraciones de llamada _render_plan: 4.5587, 4.4599 y 4.6213 s.
  No compararlas con otro runner como benchmark de rendimiento.

## Interpretación científica
La evidencia converge en la interacción de codificación multihilo con VBV de
libx264 como explicación de la variación observada en este ensayo.
El fallo se reproduce con FFmpeg directamente, con idéntico comando salvo salida.
Limitar el codificador o retirar VBV produce repetibilidad; los filtros dan
píxeles y tiempos repetibles. Esto coincide con el comportamiento descrito en
la lista oficial de x264 en 2015, enlazado en el protocolo.

No es una demostración universal para todas las fuentes/CPU/versiones, ni un
diagnóstico de que las imágenes seleccionadas fueran diferentes en SAT-07.
No hemos variado la arquitectura ni parcheado Zucker. Tres repeticiones por
brazo no permiten estimar tasas de fallo raras. Los controles se ejecutaron
en bloques; no hay experimento aleatorizado ni análisis interno del ratecontrol.

Entorno: Ubuntu 24.04, 2 CPU, FFmpeg 6.1.1-3ubuntu5,
libx264-164 paquete `2:0.164.3108+git31e19f9-1` (registrado en apt/log).
Cámara: 25 fps, time_base 1/12800, inicio 0, 2376 frames.
SHA256 fuente `312f4ff0463d1f713c132b9974fdfa443d72ebf9e7432b2d8b839ee6d7919ed3`.
La conversión a 30 fps está en los filtros reales; no se ha eliminado.

## Evidencia reproducible
- Protocolo predefinido: `docs/SATURNO_08_ENCODER_VBV_PROTOCOL_2026-10-29.md`.
- Comando capturado: `experiments/saturno_08/first_command.json`.
- Ejecutor: `experiments/saturno_08/command_replay.py`.
- Resultados estructurados y hashes por fotograma:
  `experiments/saturno_08/results_40878313397.json`.
- Log completo del run conserva ffprobe de toda la fuente; JSON versionado
  conserva metadatos y frames de 3–7 s para evitar duplicación innecesaria.
- La documentación oficial de FFmpeg, repositorio con 66020 estrellas al
  consultarlo el 29-10-2026, explica el ámbito de los hilos del encoder.
  El número de estrellas identifica el criterio de procedencia solicitado;
  no sustituye evidencia experimental.
  https://github.com/FFmpeg/FFmpeg
  https://github.com/FFmpeg/FFmpeg/blob/master/doc/encoders.texi

## Estado de A, B, C y D tras este resultado
| Hito | Estado |
|---|---|
| A | Render aislado de 2 s estable con control QA. Stage real completo sigue pendiente. |
| B | Copia COMPLETA, package_fraction=1.0. No paquete reducido validado en este run. |
| C | A/A y A/B copia completa 60/60 bajo control QA. No equivalencia completa multicámara/360/audio aislado. |
| D | Tiempos locales del runner y bytes registrados. No empaquetado/transferencia/nube/coste real. |

El máster MP3 sigue compartido y no hay aislamiento completo de fuentes/cachés.
No aprobar SATURNO global ni proponer un cambio de motor sin autorización de José Manuel.

## Siguiente fase: paquete reducido con baseline estable
Retomar el paquete lossless ya estudiado (no reinventar padding ni stream-copy),
ahora bajo el control encoder_one. Verificar primero ventana decodificada y PTS.
Separar físicamente los medios permitidos a B, incluyendo audio, del origen de A.
Después abordar Stage multicámara/360 y D con runtime real. El bloqueo científico
inmediato A/A ha avanzado de forma medible; los demás gates permanecen abiertos.
