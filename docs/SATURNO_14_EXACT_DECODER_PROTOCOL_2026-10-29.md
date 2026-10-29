# SATURNO-14 — protocolo de diagnóstico del decodificador 360

2026-10-29. Rama exclusiva: fernando/continuacion-montara. Parte de `65326c5757b40c5729f37a6dcbc0e6e34a610751`.

## Pregunta y límite

¿Entrega el comando CPU real del decodificador 360 los mismos 278 cuadros BGR al leer originales A y el paquete B, en el segmento 0003? Se contrasta con el comando de la comprobación SATURNO-11, que no era idéntico.

No hay render completo, reproyección, codificación de salida, interfaz, ingestión ni sincronización. Se conserva todo el vídeo de cámara en B y se elimina su audio mediante la receta previamente verificada. No es una nueva prueba de ahorro selectivo de GOP.

## Controles y ejecución

Script: `experiments/saturno_14/decoder_window.py`. Solo biblioteca estándar Python y FFmpeg.

- Engine debe seguir en `60a7b7e9a39077b36f45057811abd6a833a168ef`; no se importa ni modifica.
- Se verifican SHA-256 de la fuente y paquete contra SATURNO-11 antes de decodificar. Se reutiliza su comando de empaquetado, sustituyendo solo rutas.
- Plan guardado, segmento 3: inicio 21.76784580498866 s, 278 cuadros, fps=30, salida BGR24 a dimensiones de fuente.
- Cinco procesos secuenciales: A_exact, A_repeat_exact, B_exact, A_previous, B_previous.
- Exact: argv de spherical_motion.py:187–188, rama CPU sin decode_size, usando ffmpeg del PATH. Previous: argv de packet_preflight.window_hash con native_360=True.
- Cada cuadro se lee completo y se resume con SHA-256. Se conservan todos los hashes, recuentos, comandos, tiempos, versión FFmpeg y comparaciones.
- Una repetición de A verifica repetibilidad local del comando exacto; no acredita repetibilidad universal ni repite SATURNO-12.
- No se ocultan los originales en esta prueba: no se está certificando aislamiento de B. Los comandos identifican expresamente la fuente correspondiente.
- Control previous difiere del exacto en varias opciones. Si sus resultados difieren, no se atribuye causalidad a una sola opción, incluido fps_mode, sin una intervención posterior que la aísle.

## Interpretación y condición de cierre

- OPERATIONAL_ERROR: faltan datos válidos, falla la receta, proceso o integridad; salida 1.
- UNSTABLE_EXACT_AA: A no repite exactamente; no atribuir diferencias A/B al paquete.
- EXACT_DECODER_AB_DIFFERS con A/A estable: divergencia ya presente en la salida del decodificador exacto; estudiar después seek/cadencia/metadatos.
- EXACT_DECODER_AB_IDENTICAL con A/A estable: esta ventana no localiza el fallo en ese decodificador aislado; siguiente bloque revisaría parámetros/poses/reproyección.
- El informe registra si se alcanzaron los 278 cuadros solicitados en los cinco procesos. La ausencia de cuadros es error operativo.
- Un diagnóstico interpretable puede terminar verde aunque descubra diferencias; esta tarea no es el gate de equivalencia completa. Ese gate conserva su FAIL_FULL_PLAN_AB.

La prueba termina después de estas comparaciones. No lanza automáticamente otros experimentos.

## Entorno, límites y evidencia

Workflow existente `.github/workflows/saturno05-native-ab.yml` dedicado ahora al diagnóstico, con push limitado a su propia ruta en nuestra rama. Se evita crear otro disparador o alterar otros workflows. Versiones anteriores recuperables por commit.

Ubuntu 24.04, Python 3.11 solicitado, FFmpeg instalado por apt. Se registra versión efectiva para valorar comparabilidad con SATURNO-12. Límite job 10 minutos; instalación 5 minutos; diagnóstico 3 minutos y temporizador por proceso de 120 segundos.

Resultado persistido durante el job en `/tmp/saturno14-decoder/REPORT.json` y emitido entre `SATURNO14_REPORT_BEGIN/END` en los logs; resumen aparte. No se suben vídeos ni artefactos que consuman la cuota agotada. El resultado final se recuperará y versionará en un bloque posterior, sin sondeos continuos.

Validación previa: compilación de sintaxis y comprobación del lector BGR con cuatro cuadros sintéticos diminutos, incluyendo detección de un cuadro ausente por el comparador. No es evidencia científica de Saturno.

## Uso del chat

Tokens: no medibles con las herramientas expuestas. No se presenta una cifra estimada como consumo real.

Preparación: seis lecturas GitHub (HEAD, evidencia de receta, árbol base y disparadores de workflows). Se reutilizaron plan y código ya recuperados. Publicación prevista: tres blobs, un árbol, un commit, actualización condicionada exclusivamente de nuestra rama y una consulta de ejecuciones para obtener el enlace (siete operaciones más). Total previsto: 13 operaciones GitHub si todas concluyen sin incidencias.

Navegador, web y subagentes: cero. No se imprimieron JSON completos ni evidencia previa extensa. Una consulta de ejecuciones al publicar; sin espera activa por el resultado.
