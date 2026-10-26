# Gamer: encuadres ligados al texto (0.31)

El ritmo de cortes rápidos se conserva. Montara sustituye el encuadre automático periódico del motor por reposos abiertos y énfasis moderados de 1,22× sobre frases concretas. No añade pushes/pulls repetitivos. Los encuadres apuntados a mano (`aimed`) quedan intactos, incluso si eso obliga a omitir un énfasis. El centro se obtiene del rostro ya detectado; el texto no se usa para inventar la posición de un objeto.

La selección actual usa **reglas lingüísticas locales**, no un LLM: preguntas específicas y expresiones de revelación o giro en español, inglés y alemán. Se excluyen muletillas, se respetan 10 segundos de descanso entre énfasis y una densidad máxima aproximada de uno cada 25 segundos. Puede omitir momentos interesantes o interpretar una expresión literalmente: no equivale a comprensión semántica general ni a visión. Si no hay evidencia textual, no inventa un zoom.

Se registra método, política, cita, motivo, intervalos, zoom, revisiones antes/después y número de planos manuales preservados en `ShowDirection/<huella>.json`, dentro de los datos privados de la sesión. La interfaz muestra los motivos en Decisiones e historial. Se aplica una vez al entrar a revisar un nuevo Gamer. Volver a entrar o deshacer no lo repite; un nuevo análisis invalida su registro. Otros estilos no se modifican. Se usan las APIs públicas del motor, sus copias de seguridad, invalidación de previews y undo. No se cambia el motor ni se renderiza automáticamente.

Pruebas: preguntas frente a saludos/muletillas, distintos ritmos de corte, ausencia de palabras, preservación de un plano manual, cortes/duración/transcripción intactos, idempotencia después de undo, Podcast intacto y render real de 60 segundos con audio. Regresión de biblioteca musical y recuperación de proyecto: seis pruebas adicionales. Recorrido de interfaz con transcripción guardada del ejemplo: pregunta de Cuba seleccionada, 19,2–23,1 s, 1,22×. No se ha reanalizado ni sobrescrito el proyecto del usuario.

## Motor de IA y asistente premium

Un mismo servicio LLM puede atender dos tareas: proponer un plan de edición y responder instrucciones de chat. Ambos deben devolver acciones acotadas, validadas por proyecto, revisión, medios existentes y límites temporales. El modelo recibe transcripción con tiempos, planos y contexto visual relevante; propone cita, motivo, confianza, intervalo y encuadre. No ejecuta órdenes arbitrarias del servidor. Un zoom debe contar con evidencia narrativa y visual; ante incertidumbre, conservar el plano abierto.

El render sigue siendo determinista y separado. Transcribir/catalogar una vez y reutilizar resultados reduce coste y latencia. El chat solicita correcciones al mismo plan; no obliga a analizar todos los medios por cada mensaje. Registrar consumo y comparar contra una revisión humana antes de alquilar GPU de forma permanente. El servicio LLM general y el chat premium **no están conectados en esta versión**; no se ha comprado capacidad ni instalado otro modelo.

Abacus documenta que SuperComputer puede alojar modelos y servirlos por API, con GPU opcional. Los créditos de las llamadas con su API key se consumen aparte del alojamiento. No interpretar una suscripción de chat como GPU o API ilimitada para Montara.

Fuentes consultadas 2026-10-26:
- https://abacus.ai/help/chatllm-ai-super-assistant/supercomputer
- https://docs.vllm.ai/en/latest/features/structured_outputs/
