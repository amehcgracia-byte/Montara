# Preparación de Montara antes de Abacus

## Implementado en esta rama

- Stage conserva su flujo de canción única y añade **Audio only** y **Full session**.
- Registro de pistas de una sesión sin copiar originales; cada sesión tiene su propio proceso y estado del proveedor. Los trabajos de sesión comparten una cola de cómputo por espacio.
- Detección acústica con el Mixer original, reutilizando sus envolventes por bloques. Si no consigue límites utilizables, se proponen pausas colectivas de instrumentos, sin confundirlas con reconocimiento infalible de canciones. Siempre hay revisión.
- Lista de canciones con nombre, selección, límites editables, división y retirada de propuestas. La revisión queda en disco.
- Escucha del mixer con un máximo de 60 segundos de la primera canción elegida. Nunca se descargan horas de todos los instrumentos al navegador para escuchar esa prueba.
- Faders, mute y FX existentes se aplican a las canciones seleccionadas; se fija también la ganancia automática de referencia para no cambiar el balance debajo de los faders. Referencia de mastering opcional común.
- Exportaciones MP3 separadas, cancelación de procesos, detección de trabajador interrumpido y recuperación explícita de la sesión desde Stage. Los originales no se borran al cancelar.
- Subidas por fragmentos de 4 MiB para archivos de más de 8 MiB, dos transferencias simultáneas como máximo, reintento de fragmentos, recuperación al volver a elegir el mismo archivo y descarte de una subida fallida. Registro persistente, comprobación de espacio y verificación de inicio/final del archivo. Un fragmento retransmitido no duplica bytes.
- El servidor normal admite por configuración archivos de hasta 30 GiB, sujeto al espacio real. La prueba pública mantiene 256 MiB por archivo: los fragmentos no eluden ese límite. **No se ha probado todavía una sesión real con originales de 30 GB.**
- El actualizador de Vercel comprueba también trabajos de sesión antes de sustituir un espacio ocupado.

- Capa común de IA preparada y conectada a revisión de límites musicales y énfasis de Gamer. Sin cuenta no hay consultas externas; ver [contrato, configuración y pruebas](STANDARD_AI.md).

## Comprobado en el entorno local

- 115 pruebas Python y 6 pruebas de ciclo de preview tras incorporar el contrato común de IA.
- Recorrido real con dos pistas de 6:30 minutos y dos bloques musicales: dos propuestas con límite en 3:15; corrección manual a dos ventanas de 15 segundos, reproducción del mixer y dos MP3 exportados con duración comprobada.
- Recuperación tras recargar la página y revisión en anchura de móvil; sin errores de JavaScript en ese recorrido.
- Interrupción real de la subida en el navegador después de 4 MiB; al recargar y elegir el archivo de nuevo continúa desde ese punto. El SHA-256 completo del archivo recibido coincide con el original.
- Pruebas específicas de desfases de grabadoras, relleno de zonas sin audio, preview acotada, límites inválidos, rutas ajenas, retransmisión de fragmentos, reservas de disco y límite remoto.
- Estrés acústico sintético de cuatro horas, dos pistas y 460,8 MB: 23 propuestas, 8,42 segundos en frío y 3,77 segundos reutilizando caché; pico del proceso de unos 73 MiB en este Mac. No son cifras de render, de grabaciones reales ni de Abacus; no extrapolarlas a 30 GB.

Verificación final en Linux: [ejecución 40517716811](https://github.com/amehcgracia-byte/Montara/actions/runs/40517716811), código `552022c`. Pasaron los cuatro recorridos completos: Stage, Push, Mix y Session; también 115 pruebas Python y 6 de ciclo de preview. Se inspeccionaron las capturas de revisión y recuperación móvil de Session. La instalación de dependencias y los renders de CI no son tiempos de respuesta del producto. Las capturas y los registros de esta comprobación no son material de producción.

## Pendientes que no necesitan una cuenta de Abacus

| Trabajo | Situación |
|---|---|
| Vídeo por canción de una sesión completa | La nueva exportación por lotes es de audio. Falta conectar la asociación temporal de todas las cámaras con cada canción y validar selección/sincronía/deriva y render de vídeo. El flujo existente de vídeo de una canción se conserva. |
| Sesiones reales de varias horas y archivos de 30 GB | La ruta de subida y el procesamiento por canciones están preparados; falta material representativo y espacio disponible para medir memoria, disco, tiempos y resultados. El código no acredita por sí solo esa capacidad. |
| Proxies hechos en el ordenador del usuario y render final local | Existe un prototipo en `local_media/`; todavía no hay asistente instalado ni integración completa con el editor y el render. No confundir la subida fragmentada con evitar subir originales. |
| Estéreo vinculado y otros controles del Mixer | Selección conjunta pendiente. No añadir pan/solo/EQ/gate por defecto. |
| Herramientas avanzadas de Show | Selección conjunta pendiente por familias. El inventario fuente está en `docs/audit/PARIDAD_EDITOR_MIXER.md`. |
| Sustitutos Linux de funciones de Mac | Adaptar solo las herramientas elegidas. La segmentación de persona por Vision no se ha convertido automáticamente en una función Linux. |
| Biblioteca de dibujos animados | Las elecciones del selector separado no son una promoción automática a la biblioteca de producción. Preservar decisiones y colecciones hasta acordar qué se incorpora. |
| Cuotas, autenticación y suscripciones públicas | Preparar el contrato de consumo no equivale a activar cobros. Faltan decisiones de identidad, proveedor de pagos, capacidad incluida y costes medidos. El simulador de planes sigue sin facturar. |

## Aplazado hasta tener Abacus

- Prueba de navegador persistente del servidor y sesión de YouTube. El rechazo actual no está resuelto; no prometer ausencia de CAPTCHA.
- Conexión real al LLM, credenciales, modelos, consumo y límites efectivos por plan.
- GPU disponible, aceleración de modelos/render, almacenamiento contratado y mediciones específicas de esa cuenta.
- Prompt de traspaso: se preparará cuando el usuario se registre, como ha pedido.

No se ha contratado nada, activado facturación ni publicado automáticamente estos cambios en Vercel.
