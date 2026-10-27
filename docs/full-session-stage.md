# Stage: sesiones completas — alcance y estado

**Actualización 2026-10-27:** detección/revisión de canciones y exportación de audio por lotes implementadas en la rama `codex/pre-abacus-sessions`; ver [estado y pruebas](PRE_ABACUS_2026-10-27.md). La asociación de cámaras por canción y la validación con una sesión real de varias horas siguen pendientes. El alcance siguiente conserva las decisiones originales.

2026-10-25. La sesión completa pertenece al plan superior. La tarifa básica no incluye mezclar una jam entera. El plan superior debe admitir más horas, pistas, cámaras, canciones y análisis, con capacidad de proceso/prioridad mayor. No se ha decidido precio, cupo ni velocidad: se medirán en el servidor con material real la próxima semana. No contratar recursos ni activar cobros para preparar esta función.

## Flujo previsto

Stage conserva edición de una canción. Audio only oculta el cuadro de vídeos; Full session registra la sesión entera. Se propone una lista común de canciones en la línea de tiempo y el usuario puede corregir cortes. Una mezcla común de instrumentos se aplica a todas, con exportación de canciones elegidas y posibilidad posterior de crear vídeo para una canción. No repetir análisis ni sincronización por canción. No generar vídeos si sólo se solicita audio. Asociar los vídeos por su intervalo sincronizado en la sesión; no depender sólo del nombre del archivo. Eliminar desplazamientos/relojes distintos requiere compensar offsets y posible deriva de grabadores.

## Base local inspeccionada

/Users/macbookair/ZuckerMixer, versión 2.8.13, commit 3764c88. No se modificó. Montara usa actualmente un adaptador de una sola canción; todavía no importa este flujo de sesión.

- jam_mix_pipeline.detect_segments: actividad acústica MC/instrumentos/batería, opcionalmente presentaciones habladas con Whisper; propuestas con needs_review cuando no hay evidencia suficiente.
- load_cached_timelines_or_die / ensure_detection_cache: envolventes RMS por pista, reutilizables sin releer originales al reagrupar.
- active_session_end_from_timelines: final común a partir de actividad real, incluyendo colas.
- transcribe_speech_candidates: ventanas candidatas y caché de transcripciones; no obliga a transcribir íntegramente todas las pistas.
- jam_app: snapshots de análisis y render por lotes, errores por canción, reutilización de mezcla.
- estimate_segment_drum_bpm y análisis rítmico no equivalen a detectar con certeza estrofas/estribillos ni todas las fronteras entre canciones. No presentar heurísticas como reconocimiento musical infalible.

Respetar engine/ y mixer/ como proveedores: la integración se hará mediante un adaptador propio y una revisión explícita de la versión del proveedor, nunca parcheando sus carpetas. Pipeline tiene estado global: aislar cada trabajo/cliente en un proceso y directorio propios; no mezclar sesiones con threads que compartan esos globals.

## Rendimiento y presupuesto

Procesar lectura en bloques, guardar envolventes y plan de cortes en disco. No cargar horas de todas las pistas PCM a la vez. Analizar referencias/proxies ligeros; conservar correspondencia temporal con originales. Cola durable, reanudación, cancelación y progreso por fase antes de sesiones de varias horas. Subidas reanudables y almacenamiento dedicado: la prueba actual limitada no está dimensionada para una jam completa.

DSP y Whisper ejecutado en infraestructura propia no consumen tokens de un proveedor. Sí gastan cómputo, almacenamiento y transferencia. Servicios IA externos se contabilizan aparte y se cachean. No confundir horas de sesión con horas-pista: 4 horas × 12 pistas son 48 horas-pista de lectura. Mayor RAM permite capacidad; no garantiza acelerar todas las fases.

Medir con una sesión real: tamaño original y proxy, horas-pista, offsets/deriva, tiempo de registro y análisis frío/caliente, detección, mezcla/exportación por canción y en lote, pico RAM/CPU, GPU si corresponde, coste de IA externa, almacenamiento/transferencia y concurrencia. Comparar cortes propuestos con cortes revisados. Con esos datos decidir horas incluidas, concurrencia y coste del plan superior. No prometer uso ilimitado ni precio del plan superior antes de medir.
