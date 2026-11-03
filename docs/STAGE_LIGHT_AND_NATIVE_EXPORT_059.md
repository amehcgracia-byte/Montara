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

- Motor candidato: `5877eacba238b610359a754ffd1d34fba50e03d4` (Editor PR #50), descendiente de `ff9baf45`; mixer sin cambios (`f15ff91`).
- macOS: 30 pruebas de luz/encuadre/preview aprobadas. Incluyen dos fuentes oscuras controladas, negros y altas luces, paridad preview/export y guardas de proyecto/revisión.
- Se inspeccionaron muestras antes/después de dos originales SDR reales, uno full-range y otro limited-range. Es una revisión visual de muestras, no una certificación de toda la sesión.
- Exportación local real controlada: original 1920×1080 de cuatro segundos, montaje del motor y salida 1920×1080; el error frente al original es menor que el de reducir a 720p y ampliar. No representa el tiempo de una canción real ni una promesa de velocidad.
- El Fast CI del Editor presenta 22 fallos; se seleccionaron y reprodujeron los mismos 22 en la base limpia `ff9baf45` y el candidato `73106469`. No se han ocultado ni modificado esas pruebas, y no se declara ese CI completo aprobado.
- Al cambiar el perfil compartido de una cámara se regeneran también las miniaturas dependientes, no solo la toma sustituida; una regresión cubre ese caso.
- Siete pruebas locales del companion aprobadas, incluida comparación entre dos exportaciones reales (original 1080p frente a copia 720p codificada), HTTP Range, origen y validación de receta. Una prueba nativa 360 verificó dos puntos de vista distintos con el runtime mínimo.
- Aceptación Linux: cinco recorridos aprobados en Actions `41558675123` (Stage, Push, Mix, sesión/companion y contenedor privado/persistencia); capturas inspeccionadas. Companion 0.6.0 instalado y comprobado con renderer `5877eac` y mixer intacto `f15ff91`.
- Montara #67/#69 y Editor #50 integradas. Despliegue JM comprobado el 03-11: 0.59 `662c06a`, engine `5877eacb`, mixer `f15ff91c`; HTML/scripts y companion verificados. Su exportación anterior terminó al 100% antes del reinicio, sin cancelarla.
- #69 añade Atrás/Adelante del navegador conservando los datos del flujo en memoria (no recuperación tras recargar). Su recorrido específico pasa en Mac/Linux y los cinco jobs Linux de `41561584703` están aprobados; capturas inspeccionadas. Falta la prueba del usuario con una canción completa y sus originales en esta instalación.

## Diagnóstico de las dos cámaras

El vídeo corto de la prueba duraba 33,28 s también en su original. Solo cubría unos treinta segundos al final; la otra cámara duraba 389,28 s. No se extiende artificialmente ese material. Para disponer de dos cámaras durante toda la canción hay que aportar la grabación larga prevista.

Pendiente independiente: variación automática de zoom en cámaras móviles y lote de canciones ya mezcladas; ver `PENDIENTES_CAMARAS_Y_LOTES.md`.
