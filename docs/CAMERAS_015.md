# Montara 0.15 — tipos y encuadre de cámaras

- Separadores de corte grises y finos. Conservan el área de agarre; el acento aparece al pasar el cursor, seleccionar con teclado o arrastrar.
- En Stage/Pulse, la línea de tiempo muestra número de toma y tipo: «01 · Moving», «02 · 360 · [nombre del tiro]», «03 · Fixed». Las tarjetas conservan el mismo número. Los nombres de archivo siguen en la carga; no se utilizan marcas como clasificación de cámara.
- La pantalla de cámaras permite elegir 360, Fixed camera o Moving camera para cada vídeo, incluso si hay una sola cámara normal. Los nombres de personas/lugares pertenecen a los tiros de la 360. La elección se persiste al continuar. Una grabación raw .insv conserva su tipo 360.
- Botón derecho sobre un plano normal: zoom de 1× a 3×, botón para abrir/cerrar, clic para elegir el centro, arrastre del cuadro y restauración del encuadre original. Se guarda por toma; previsualización explícita. La misma herramienta está en las cámaras normales del Podcast. No se pueden recuperar zonas fuera de lo grabado ni detalle óptico inexistente.
- Se comparte el recorte entre miniaturas, previsualizaciones, render musical y programa Podcast. Un recorte manual sustituye el movimiento automático de esa toma, evitando sumar dos zooms. Las cachés incluyen el encuadre.

Motor: 60a7b7e9a39077b36f45057811abd6a833a168ef. Pin del repositorio Montara: d0ffa77. Distribución instalada desde un archivo del commit del motor, sin parches directos al submódulo.

Validación macOS: 60 pruebas; material sintético rojo/azul confirma que el zoom y el punto de interés cambian los píxeles correctos tanto en previsualización como en el render final. Pruebas visuales en cámaras Fixed y Moving de Stage y cámara normal de Podcast; previsualización real de ambas rutas. Pruebas de persistencia, límites, documentos antiguos, etiquetas, cambios de tipo y exclusión de falsos tiros 360. Linux e2e_journey no ejecutado en este Mac.
