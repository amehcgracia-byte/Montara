# Capa común de razonamiento de Montara

La IA es una capacidad interna de la aplicación, disponible para las herramientas que necesiten criterio. No es un chat ni un agente general. Las restricciones comerciales por plan se decidirán después de medir el consumo; no se aplican bloqueos nuevos por precio en este cambio.

## Estado real

`montara_ai.AIService` ofrece consultas con evidencia acotada, una respuesta JSON validada por la herramienta, caché de 24 horas, registro de uso y un máximo de dos consultas remotas simultáneas por espacio de datos. Una consulta idéntica en curso no genera una segunda llamada al abrir dos pantallas: la segunda recibe estado ocupado y conserva el resultado local. Los errores tienen una pausa de 30 segundos antes de permitir otro intento.

Cada consulta HTTP se ejecuta en un proceso auxiliar con plazo de 12 segundos. No hay cadenas de reintentos automáticos ni herramientas de ejecución. Si falla, la edición local continúa. Una consulta sin credenciales/modelo configurados devuelve `not_configured` sin contactar ningún servicio. No se considera un resultado validado por IA.

El registro SQLite guarda tarea, modelo, duración, estado y tokens comunicados por el proveedor. Los aciertos de caché registran cero tokens nuevos. Si una consulta termina sin información de uso, el consumo queda desconocido (`NULL`), no se presume gratuito. Todavía no calcula euros/créditos de Abacus ni implementa facturación pública.

## Primeras herramientas conectadas

- **Sesiones musicales:** revisión de hasta 12 cortes prioritarios con duración de secciones y actividad instrumental en ventanas breves. No se envía el audio completo ni rutas locales. El modelo puede señalar cortes plausibles o dudosos; no inventar tiempos ni borrar propuestas. El usuario sigue aceptando los límites. Si hay más cortes, la interfaz indica cuántos se han enviado. Esta fase no afirma que el modelo haya escuchado la canción.
- **Gamer:** selección semántica de frases del texto para proponer acercamientos. Solo se aceptan IDs de frases existentes. Se conservan límites de duración/separación, encuadres manuales y undo. La consulta de red sucede fuera de los bloqueos de edición; si el material cambia entretanto, se descarta la respuesta. Si no hay IA disponible, se mantienen las reglas locales y el informe identifica ese método.

Story, Podcast y las demás herramientas pueden utilizar el mismo servicio con contratos propios. Su disponibilidad común no significa que sus planes semánticos se hayan integrado ya ni que un LLM sustituya DSP, sincronización o render.

## Configuración futura del servidor

- `MONTARA_LLM_MODEL`: modelo compatible elegido tras medir calidad, tiempo y coste. No se fija un modelo caro ni se inventa un identificador.
- `MONTARA_LLM_API_KEY`, o `ABACUS_API_KEY`: credencial privada del servidor. Nunca va al navegador o al repositorio.
- `MONTARA_LLM_BASE_URL`: por defecto `https://routellm.abacus.ai/v1`; verificar la URL de la cuenta cuando exista.
- `MONTARA_AI_ENABLED=0`: interruptor técnico para desactivar consultas externas sin desactivar la edición local.

La [documentación oficial de Abacus](https://api.abacus.ai/help/route-llm/chat-completions/) confirma Chat Completions compatible y salida JSON. La integración HTTP se ha probado con un servidor local simulado, incluyendo un trabajador real de sesiones y el API real de encuadre de Show. **No se ha realizado una consulta real a Abacus ni se ha probado una mejora de calidad del modelo.**

Montara sigue en Python; esta conexión no introduce un servidor JavaScript ni dependencias de interfaz nuevas. Las futuras tareas registran una `Task` con instrucciones y un validador de dominio y utilizan `app.extensions['montara_ai']`, o el mismo servicio desde su trabajador aislado.
