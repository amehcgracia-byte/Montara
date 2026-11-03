# Iluminación — auditoría y tratamiento de prueba, 2026-11-02

Estado: revisión y muestras reales; **sin cambios en motores, interfaz ni despliegue**. Montara examinada: 0.58, funcional `f902ccc`; Editor fijado: `ff9baf4`.

## Hallazgos en código

- `engine/core/stages/export.py`: `_color_reference_record` prioriza Sony, Nikon, iPhone, 360 y otras, por fabricante; no elige la exposición más aprovechable. `_color_profiles_for_segments` conserva intacta la referencia (`reference_brightness_lift=0`) y ajusta las otras hacia ella. No es recuperación de subexposición.
- `color_correction_for_profile` limita la subida aditiva a 0.035 en cámaras planas y 0.015 en 360; `_color_filter` aplica brillo/saturación y balances pequeños, sin una curva específica de sombras/altas luces.
- Perfil fijo por archivo, medido en muestras. No adapta la recuperación a cambios de luz dentro de una toma.
- `core/shot_review.py`: las miniaturas se generan por defecto sin perfil de color; `render_review_thumbnails` lo desactiva explícitamente. Hay que compartir corrección y caché entre editor y exportación.
- Reels omite expresamente el perfil multicámara para evitar el antiguo tinte verde; no activar ese perfil indiscriminadamente en Push.

## Comprobación real

Se consultó el proyecto más reciente del laboratorio JM con dos vídeos disponibles: 33.28 s y 389.28 s, ambos con copias 1280×720. No se ha confirmado cuál es la Sony del usuario: el perfil guardado clasifica ambos como `other`.

El análisis guardado registra luminancia media 24.412395 y 9.738989, referencia sin levantar y una corrección de brillo de 0.020139969 para la otra fuente. Son valores del análisis existente, no una medición de exposición EV ni de rostros. Sus campos `black_clip_ratio`/`white_clip_ratio` representan muestras con un extremo recortado, **no porcentaje de píxeles perdidos**.

Se extrajeron fotogramas al 20/50/80% de ambos vídeos y comparaciones al 50%, sin modificar archivos originales ni el proyecto. Un incremento de gamma fuerte hace más visible el contenido, pero también produce velo gris/ruido. Una curva con pie negro conservador levanta medios tonos manteniendo mejor el fondo; cambia también el aspecto del color y necesita afinado. Las comparaciones son candidatos visuales, no un ajuste final validado.

Las muestras e informes se guardan en el equipo de trabajo, fuera de Git. No se suben imágenes de usuarios, vídeos, credenciales ni rutas privadas.

## Implementación propuesta

1. Separar recuperación de exposición de igualación entre cámaras. No oscurecer todas para perseguir una referencia subexpuesta ni llevar el fondo nocturno a gris medio.
2. Comprobar rango de vídeo, transferencia/HDR/Log y conversión antes de interpretar una toma oscura como subexposición. Esa comprobación de estos dos originales aún está pendiente.
3. Analizar sujeto/zonas útiles y percentiles, proteger focos y negros; levantar tonos medios y sombras con límites. No considerar el fondo negro del escenario un error.
4. Mantener parámetros estables por tramo de iluminación, con transición suave: sin bombeo por fotograma. No asumir que dos cámaras muestran el mismo sujeto al comparar sus histogramas.
5. Reducción de ruido suave y opcional cuando la recuperación lo requiera; probar textura, rostros en movimiento y coste antes de activarla por defecto.
6. En Edit: automático, Luz, Sombras y comparación Original/Corregido; valores por cámara con excepción por plano. No etiquetar el control como ISO. Aplicar el mismo tratamiento en miniatura, preview y render e invalidar cachés al cambiarlo.
7. Estos ajustes pueden ejecutarse con análisis visual y filtros; no requieren consultar un LLM por fotograma. No se han medido tiempos ni costes de una implementación completa.

Herramientas disponibles y verificadas en el FFmpeg instalado: `exposure`, `eq` (gamma y peso de altas luces), `curves`; evaluar `hqdn3d` para ruido. Documentación oficial: https://www.ffmpeg.org/ffmpeg-filters.html .

Aceptación pendiente: día/noche, dos cámaras igualmente oscuras, cámara ya bien expuesta, luces de color, foco blanco, ruido, cambios de iluminación, HDR/Log y paridad preview/render. No hay PR funcional ni mejora de iluminación instalada todavía. Cualquier cambio del motor se realiza primero en Zucker Editor y después mediante un commit separado del submódulo, conforme a CLAUDE.md.

## Actualización de implementación

La propuesta se ha convertido en candidato 0.59 (PR Montara #67, Editor #50), con pruebas controladas y revisión de muestras de originales SDR. Estado y alcance en [STAGE_LIGHT_AND_NATIVE_EXPORT_059.md](STAGE_LIGHT_AND_NATIVE_EXPORT_059.md); no confundir candidato con despliegue validado.
