# SATURNO-07 — Última medición y traspaso de chat (2026-10-29)

## Evidencia actual
Ejecución real GitHub Actions: https://github.com/amehcgracia-byte/Montara/actions/runs/40865264794 (job 123418303750). Resultado **FAIL** porque no hay igualdad exacta, lo cual es el estado correcto del gate.

Instrumentación temporal en `experiments/saturno_05/native_ab.py`: se intercepta `core.stages.export._run_ffmpeg_progress`, se registran comandos reales, SHA256 de resultados y hashes de fotogramas decodificados de archivos intermedios **mientras existen**. Sin modificar `engine`, `mixer` ni `main`.

**Hallazgo:** en dos renders A/A independientes del mismo clip, misma ruta, con rerender forzado, **la primera salida intermedia ya difiere en 5 de 60 fotogramas**, índices **53–57**; salida final también 55/60. Se descarta que el montaje final sea requisito para que aparezca la diferencia. No se ha demostrado todavía qué elemento del primer comando FFmpeg genera la diferencia.

El paso del workflow todavía se llama «fades disabled», pero la variable `SATURNO_QA_NO_FADES` se configuró a `'0'` para este ensayo: **los fundidos están activos**. En SAT-06, con fundidos temporalmente desactivados en QA, persistían diferencias 51/60.

## Qué hay que hacer ahora
1. Extraer los comandos exactos de la primera etapa del log 40865264794 y los PTS/timescale del clip. Ejecutar *exactamente el mismo comando* varias veces en QA, comparando hashes de frames y variando **solo** el paralelismo si se justifica. No cambiar filtros sin test A/A aislado.
2. Resolver el gate de repetibilidad A/A o definir justificadamente tolerancias con evidencia. Sin eso no podemos certificar igualdad A/B.
3. Repetir B con paquete verdaderamente reducido y original oculto; luego Stage completo tres cámaras + 360 y audio; tomar medidas D reales.
4. Recordar que la última prueba Stage E2E QA se bloqueó durante la transición de la interfaz antes del export; que el renderizador aislado sí logró trabajar con una copia de fuente ocultando original.
5. **No dar los cuatro hitos por concluidos**. El usuario quiere completarlos y solo entonces decidir arquitectura.

## Documentación/handoff
Documento ampliado descargable de la conversación: `MONTARA_TRASPASO_SATURNO_2026-10-29.md`, que incluye todas las ejecuciones y condicionantes del proyecto. Abrir nuevo chat en el proyecto MONTARA y adjuntar el documento para continuar sin dependencia de longitud del historial.

## Notificaciones
Los varios emails «Run failed» son GitHub Actions originados por múltiples pushes de QA. Evitar disparo por cambios triviales; preferir `workflow_dispatch` para la siguiente iteración y agrupar pruebas. Hay además límite de cuota de almacenamiento de artefactos CI; conservar resumen relevante en logs.
