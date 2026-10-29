# SATURNO-11 — Preflight de GOP sobre el plan Stage real

## Pregunta nueva y continuidad
SAT-09 aprobó caso plano reducido. SAT-10 generó Stage real (plan de 19 planos).
No repetir sus exports ni reconstruir decisiones. Antes de tres renders completos,
comprobar las entradas y el tamaño de un paquete sin recodificar los frames originales.
Se han leído las auditorías históricas GOP/end-boundary, frame identity y portable V2;
sus fallos sintéticos NO se borran ni se convierten en PASS por añadir margen.

## Fuente primaria y mecanismo acotado
FFmpeg oficial (repositorio consultado: 66020 estrellas), BSF noise:
https://www.ffmpeg.org/ffmpeg-bitstream-filters.html#noise
https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/bsf/noise.c
amount=0 no altera payload; drop evalúa expresión por paquete, índice n desde cero.
Se usa únicamente para omitir grupos completos de paquetes entre keyframes,
stream-copy MP4, timestamps originales, sin seleccionar frames decodificados.
No se proclama algoritmo universal de cierre de referencias GOP abiertas.

## Protocolo predefinido
1. Leer los archivos EXACTOS stage_edit_plan.json y stage_project.json de SAT-10.
2. ffprobe fuente: GOPs/paquetes, hash SHA256 de payload, PTS/DTS y time_base.
3. Ventanas del plan real + ventanas color_sample_commands del motor fijado.
   Añadir un periodo de frame para la conversión de cadencia y retener primer/último
   GOP para preservar origen y duración que usa el análisis de color.
4. Retener GOPs que cubren esas ventanas; no elegir 0.4 s de margen por intuición.
5. Verificar payload, PTS y DTS de cada paquete conservado y duración de contenedor.
6. Comparar decodificación de TODOS los planos: misma ruta de seek redondeado
   en planos ordinarios, ruta fps30/bgr24 por frame_count para el decodificador 360.
7. Ejecutar _color_profiles_for_segments nativo en proyectos A/B con identidades
   independientes y fuentes remapeadas. Exigir coeficientes exactos.
8. Medir fuentes completas, payload VIDEO real, payload retenido, contenedores,
   master completo (necesario para toda la canción), y JSON de plan/proyecto.

## Evitar falsas conclusiones
- Las cámaras pueden contener audio que el render no usa: separar ahorro por
  omitir ese audio del ahorro por descartar GOPs. No llamar recorte de vídeo a ambos.
- Plan/proyecto se serializan y se cuentan. Manifest de transporte y assets adicionales
  aún no están incluidos: el tamaño es un límite inferior declarado.
- Es paquete para exportar plan FIJO; no se promete poder volver a sincronizar/editar
  sin las pistas de cámara descartadas.
- El preflight de B NO está aislado por namespace. Sí remapea rutas y recalcula color
  con claves de proyecto independientes; no es el gate C de export final aislado.
- PASS_INPUT_PREFLIGHT no significa PASS_RENDER_AB ni prueba de rentabilidad remota.
- Cualquier payload/PTS/DTS, ventana o coeficiente distinto produce FAIL.
- Registrar también si el cierre por GOP obliga a conservar TODOS los paquetes de vídeo.
- No modificar motores ni main ni ramas ajenas, ni gastar RunPod.

## Verificación del mecanismo antes de CI
Prueba local SINTÉTICA NUEVA de este mecanismo (H264 160x80,25 fps,12 s,GOP25),
no repetición de SAT-02/03: selección de GOP [0,3,8,11] de 12, payload/PTS/DTS
exactos, duración exacta y ventanas de decodificación ordinaria/360 exactas,
archivo menor. No se presenta como resultado de nuestras cámaras reales.

La siguiente ejecución consolidada hace solo este preflight sobre las fuentes reales.
El export Stage de ocho minutos no se repite para resolver una cuestión de entrada.
