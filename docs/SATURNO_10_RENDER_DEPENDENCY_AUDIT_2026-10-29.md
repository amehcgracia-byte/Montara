# SATURNO-10 — Dependencias de render más allá de los cortes

## Fuente y alcance
Auditoría estática del motor fijado, SIN modificaciones:
amehcgracia-byte/zucker_videos commit 60a7b7e9a39077b36f45057811abd6a833a168ef,
core/stages/export.py, funciones identificadas abajo.
Es lectura de contrato de implementación; no sustituye el ensayo A/B completo.

## Dependencias observadas
| Componente | Lectura del motor | Consecuencia para el paquete |
|---|---|---|
| Vídeo del plano | _segment_source_info resuelve original, normalized/proxy, probe y paired_path | Inventariar ambos medios y metadatos, no sustituir rutas a ciegas |
| Color de cámaras planas | _color_profiles_for_segments -> measure_clip_color -> color_sample_commands | Necesita muestras de la fuente fuera de los planos seleccionados |
| Color 360 | _visible_color_samples elige 5 vistas de segmentos no planet y usa su punto medio con reproyección | Preservar vistas, pose, tiempos y ventana de análisis completa |
| Preparación 360 | _spherical_export_source_info puede crear proxy equirectangular de toda la fuente; _spherical_uses_original_motion decide si lo necesita | No concluir que bastan los planos hasta verificar la ruta efectiva |
| Movimiento 360 | _continuous_spherical_render_segments transporta previous_shot entre cámaras | Mantener orden y estado de movimiento del plan completo |
| Audio | master_window_start, master_start_sec y mux con bookends/fades | La ventana audiovisual del paquete debe incluir este contrato temporal |
| Marca/overlays | _render_plan y _overlay_config, logos/intro/outro | Declarar assets y configuración además de cámaras y master |

El ajuste de color se omite expresamente en reel/reel_horizontal. Por eso el
caso reducido de SAT-09 no prueba este comportamiento de youtube/Stage.

## Ejemplo numérico trazable de color plano
La cámara cam-fixed.mp4 dura 95.04 s (ffprobe guardado en resultados SAT-08),
25 fps y 2376 frames. color_sample_commands calcula window=min(2,max(.25,duration/5))
y toma cinco ventanas desde 10,30,50,70,90 % de la duración, con límites al final.
Para esta fuente: [9.504,11.504], [28.512,30.512], [47.520,49.520],
[66.528,68.528], [85.536,87.536] segundos. Son ventanas de entrada al comando;
la función añade fps=2 antes de medir signalstats. No asumir que equivalen
a todos los frames del intervalo ni ignorar las dependencias del decodificador.

Si se cambia duración/origen de la fuente a un fragmento, las cinco posiciones
porcentuales se recalculan. Aunque los frames DEL PLANO coincidan, las correcciones
de color podrían cambiar. Es una hipótesis de divergencia fundada en el código;
no se ha medido todavía una divergencia multicámara por esta causa.

## Reglas para el siguiente A/B
1. Capturar edit_plan REAL y proyecto, configuración y assets; no recrear decisiones.
2. Inventariar los comandos y las rutas efectivamente leídas, incluidas normalizaciones.
3. Construir cierre de dependencias con ventanas de análisis, GOP y tiempos.
4. Si se propone transportar resultados de análisis como metadatos, declararlo
   como una variante explícita y probar su importación. No copiar caches A a B
   ocultándolo ni parchear funciones del motor para forzar equivalencia.
5. B sin acceso a originales/outputs/caches A; gate incluye vídeo, audio y tiempo.
6. Medir tamaño REAL; que una fuente original esté muy comprimida puede hacer
   que una variante lossless crezca. No confundir menos segundos con menos bytes.
7. Instrumentar también export.run_reprojected_command: core/spherical_motion.py
   abre el encoder directamente con subprocess.Popen, sin pasar por
   export._run_ffmpeg_progress. El control SAT-08/SAT-09 cubre la ruta plana;
   no se puede presumir que controle todos los encoders de movimiento 360.
   El Stage actual sirve de baseline único, no de demostración de A/A 360.

## Pendientes
Esta auditoría anticipa trabajo para B/C completos. No declara fallido Saturno,
ni aprobado Stage, ni autoriza parches a los motores de José Manuel.
