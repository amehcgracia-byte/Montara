# Copia completa para pruebas privadas

Esta carpeta contiene la interfaz, el motor, el mixer y todos los vídeos de prueba de la instalación original. No incluye el adaptador de demostración de Vercel. Los originales no se han modificado.

Arranque de comprobación local: `python app.py --host 127.0.0.1 --port 8090 --data /ruta/a/datos-separados`.

Para el servidor Linux: definir MONTARA_PREVIEW_PASSWORD con al menos 16 caracteres y ejecutar `docker compose up --build -d`. La entrada está protegida con usuario `montara` y esa contraseña. Se publica solo en localhost del servidor: conectar mediante un proxy HTTPS antes de compartir. No exponer el puerto sin TLS. El motor conserva un proyecto activo por instancia: para estas pruebas privadas se usa de uno en uno. Para usuarios simultáneos se necesita una instancia/contenedor y volumen separado por usuario; no aumentar workers para intentar solucionarlo.

El frontal de Vercel puede reenviar todas las rutas al host HTTPS de este contenedor, conservando exactamente los endpoints originales. Todavía no se ha configurado ese destino porque no hay un servidor de procesamiento disponible/contratado. No se ha activado ningún coste ni abierto un túnel hacia el ordenador personal.

Comprobado en macOS: la copia arranca con los mismos archivos, versión y ejemplos; el motor responde. Pendiente: construir imagen y ejecutar el recorrido completo en Linux con FFmpeg. No se ha declarado equivalencia completa de la web pública ni una prueba Linux superada. Las dependencias de IA pueden descargar modelos en la primera ejecución, y los servicios externos requerirán sus credenciales legítimas.
