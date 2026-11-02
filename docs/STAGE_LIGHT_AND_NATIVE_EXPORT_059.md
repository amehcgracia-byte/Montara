# Stage 0.59 — luz y originales

## Implementación

- Stage activa la recuperación de luz de forma automática al confirmar las cámaras. Se miden cinco ventanas por fuente y se calcula una corrección fija por cámara, sin perseguir el nivel fotograma a fotograma.
- El objetivo de luz es común, con límites para no intentar convertir el fondo oscuro del escenario en gris. La curva protege el negro y las altas luces. La cámara usada como referencia también recibe recuperación de sombras.
- Edit en cada toma ofrece Auto, Light, Shadows, comparación Original/Corrected y aplicación a esa cámara o solo a esa toma. Miniaturas, previews y exportación comparten el filtro. No se aplica una segunda ganancia de brillo heredada.
- No es reconstrucción neuronal: una captura negra, quemada o ruidosa no recupera detalle inexistente. El ajuste RGB y el balance de color conservador aproximan las cámaras; no garantizan un color idéntico entre escenas o focos distintos. HDR/Log no se certifica con estas pruebas SDR.

## Calidad final

Antes, una cámara convertida por el companion a 720p podía acabar como exportación 1080p ampliada desde esa copia. Ahora Stage, cuando detecta copias ligeras, solicita una receta de edición por HTTP y el companion vuelve a los originales autorizados en el Mac. No hay un render previo del mismo vídeo en el servidor.

Se conserva el montaje, los encuadres, la luz y el máster. El companion verifica tamaño y huella del original, versión exacta del motor y cobertura de cada toma. Si falta el disco o el renderizador, se muestra un error: nunca se entrega silenciosamente la copia ligera como final. La salida del motor sigue siendo 1080p; no es exportación 4K.

El renderizador opcional se instala con `companion/install.sh --video`. Solo añade dependencias de vídeo; no descarga modelos de IA. Se aísla el proyecto temporal del Editor y el archivo final queda en la carpeta elegida, sin sobrescribir archivos existentes. La reproducción admite rangos HTTP.

Ámbito inicial: Stage, sin marca o con Montara. Push/Show y logos propios aún no usan esta ruta local. Las subidas directas de originales conservan su exportación en servidor.

## Evidencia y aceptación

- Motor candidato: `6300142de3e65a7f7f7594d51c3324ff6e7c6452` (Editor PR #50), descendiente de `ff9baf45`; mixer sin cambios (`f15ff91`).
- macOS: 28 pruebas de luz/encuadre/preview aprobadas. Incluyen dos fuentes oscuras controladas, negros y altas luces, paridad preview/export y guardas de proyecto/revisión.
- Se inspeccionaron muestras antes/después de dos originales SDR reales, uno full-range y otro limited-range. Es una revisión visual de muestras, no una certificación de toda la sesión.
- Exportación local real controlada: original 1920×1080 de cuatro segundos, montaje del motor y salida 1920×1080; el error frente al original es menor que el de reducir a 720p y ampliar. No representa el tiempo de una canción real ni una promesa de velocidad.
- El motor ya presenta diez fallos de expectativas geométricas 360: se reprodujeron los mismos diez en la base limpia y en el candidato (94 aprobadas y 8 omitidas en ambos). No se han ocultado ni modificado esas pruebas.
- La aceptación Linux y del companion instalado se registra al completar el despliegue; hasta entonces es candidato, no validado en producción.

## Diagnóstico de las dos cámaras

El vídeo corto de la prueba duraba 33,28 s también en su original. Solo cubría unos treinta segundos al final; la otra cámara duraba 389,28 s. No se extiende artificialmente ese material. Para disponer de dos cámaras durante toda la canción hay que aportar la grabación larga prevista.

Pendiente independiente: variación automática de zoom en cámaras móviles y lote de canciones ya mezcladas; ver `PENDIENTES_CAMARAS_Y_LOTES.md`.
