# Show: primeras pruebas, decisiones y futura automatización

## Objetivo

Aproximar el resultado de los montajes de referencia conservando un historial que permita explicar, corregir y repetir cada decisión. Las primeras pruebas son de 90 segundos para Podcast y 60 segundos para Story. Esto no equivale a un modelo entrenado ni demuestra todavía generalización a vídeos desconocidos.

## Recorrido de la aplicación

Show abre siempre la carga de vídeos, incluso al refrescar con un trabajo guardado. Después de Continuar aparece la elección Gamer, Influencer, Story y Podcast, en ese orden. Solo un segundo Continuar abre o prepara la revisión. Se conservan los datos del trabajo, pero no se omiten las páginas. Hay botones Atrás, navegación entre pasos y compatibilidad con Atrás del navegador.

## Podcast

El motor de la 2.6.20 hace localmente: alineación por sonido, actividad por micrófono, turnos de palabra, correspondencia entre boca y micrófono cuando no existe un mapa previo, selección de cámara y mezcla con atenuación de micrófonos inactivos. No consulta un LLM para cada corte.

En esta primera prueba se reutiliza el mapa de asientos/cámaras del kit existente. No atribuimos su creación a un nuevo análisis. Los cinco micrófonos son las separaciones del material de prueba, no cinco grabaciones físicas independientes. Es necesario otro ensayo real para medir el comportamiento con filtraciones, solapamientos y sincronización imperfecta.

Análisis inicial guardado: 33 turnos y 16 tomas en 90 segundos. Se puede corregir un intervalo con botón derecho en el vídeo o su barra de cámara. La vista 360 se apunta arrastrando; una cámara fija también puede sustituirla. Se guarda el cambio y el motivo. El render solo se pide con Preview o al exportar.

Los subtítulos se activan o desactivan, cambian de estilo y tamaño y se arrastran o redimensionan sobre el vídeo. Su configuración se usa también al generar el vídeo.

## Story

El asistente revisó una hoja de contacto de los diez clips y transcribió localmente el minuto de audio con Whisper small. Se distinguieron presentador, entrevista, transición, ilustraciones de llamadas y archivo de una vivienda quemada. La pista de narración existente ya contiene la voz de la entrevista; no se sintetizó una voz ni se identificó una persona por su cara.

El primer plan está guiado por el montaje de referencia y conserva sus intervalos. Esto es una calibración conocida, no una prueba ciega de selección semántica. Las entrevistas conservan su velocidad original para no desincronizar los labios. Tres huecos breves de los recursos extraídos se cubren con insertos y quedan señalados para revisión; el plan tiene trece momentos. El catálogo incluye la descripción observada y cada intervalo contiene el texto transcrito, el papel de voz, la elección y su motivo.

El plan aprobado se reproduce sin volver a consultar una IA. Se puede sustituir el clip de un momento desde Decisiones e historial; el cambio queda anotado. Para material nuevo sin plan, el motor puede usar correspondencia visual local, cuya selección necesita revisión editorial: no garantiza identificar correctamente una entrevista o una persona nombrada.

## Qué se guarda

Por proyecto: artifacts/show_decisions.jsonl (eventos con fecha UTC, acción, método, antes, después y evidencias); artifacts/show_podcast.json (personas, sincronía, cámaras, turnos, tomas y correcciones); artifacts/story_plan.json (catálogo, texto, momentos, recursos y motivos); artifacts/show_caption_layout.json (subtítulos y posiciones).

En el kit: podcast/analysis.json, storytelling/transcript.json y storytelling/review-plan.json. Las rutas del kit son relativas y sus límites están declarados. Montara usa MONTARA_LOCAL_DIRECTOR=1: estas pruebas no ejecutan el cliente de Claude ni llaman a un proveedor LLM externo.

## Contrato para un futuro planificador

1. La aplicación transcribe una vez con tiempos y conserva el audio original. En Podcast calcula actividad, sincronía y turnos antes de proponer cámaras.
2. Se catalogan recursos una vez: identificador estable, duración, tipo de plano, descripción visual, texto visible y, cuando haga falta, audio/transcripción. No deducir una identidad a partir de un rostro desconocido.
3. El planificador recibe fragmentos acotados de relato y candidatos del catálogo. Devuelve JSON con intervalo, recurso, entrada/salida, papel de voz, motivo, evidencias y confianza. Nunca inventa un archivo o tiempo.
4. Un validador rechaza huecos, tiempos imposibles, archivos ajenos al proyecto y revisiones obsoletas. Una respuesta incompleta o un fallo se muestra para revisión; no se mantiene una espera infinita.
5. El render ejecuta el plan aprobado de forma determinista. Una corrección no obliga a analizar de nuevo todos los vídeos.

El trabajo semántico de Story necesita visión y comprensión del audio/texto, o servicios separados que produzcan un catálogo fiable. No basta con un LLM de texto que vea nombres de archivos. Podcast puede avanzar mucho con reglas y modelos locales de voz/visión, sin LLM generativo.

## Cómo comparar

Podcast: porcentaje de tiempo con el hablante correcto, cambios tardíos, cambios innecesarios, calidad de mezcla y correcciones necesarias por minuto. Separar planos deliberados de reacción/grupo de los errores.

Story: correspondencia entre relato y recurso, entrevistas correctamente mostradas, coherencia de personas/fechas/lugares, repeticiones, continuidad y correcciones por minuto. La próxima evaluación debe usar material no empleado para preparar el plan y compararse con una revisión humana independiente.

Registrar además tiempo de análisis, tiempo de render, tamaño de caché y coste por minuto de entrada. Un modelo más pequeño solo se adoptará si conserva la calidad medida; estos registros sirven para evaluarlo, no prueban por sí solos que esté entrenado.

## Auditoría de las comprobaciones

Las pruebas de interfaz incluyen cambios temporales de cámara y de recurso que después se restauraron. Sus motivos los identifican como pruebas. No deben convertirse automáticamente en ejemplos positivos de entrenamiento. El campo histórico `method: human` significa una edición mediante los controles, no demuestra quién la hizo ni que esté validada. Para preparar un dataset habrá que separar actor, origen de la decisión y aprobación editorial; conservar también las restauraciones y los casos que necesitan revisión.

Validación realizada en macOS: pruebas de audio, montaje, subtítulos, proyecto/revisión, corrección de cámara que llega al render y cambio de versión de previsualización al cambiar el archivo del programa. Podcast real de 90 s exportado con 102 subtítulos; Story de 60 s reconstruida con 13 momentos. No se ha ejecutado el recorrido completo de Linux ni desplegado una instancia pública.

Motor utilizado: base 2.6.20 con las revisiones posteriores de Story y las adaptaciones de Montara; commit 111f60db112b010a39618506193d3cd880d5046a. Pin del repositorio Montara actualizado en 06cb4c9. No se han publicado cambios remotos.
