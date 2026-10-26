# Proxies locales: fase inicial de Montara

Implementado y probado localmente en `local_media/proxies.py`:

- Preparar una copia de duración completa sin enviar datos por internet. La fuente queda intacta.
- Identificador opaco por fuente y caché de copia; mapa privado fuente-original/copia.
- Metadatos públicos separados: no incluyen rutas absolutas ni nombres de los originales.
- Verificación de duración y rechazo si la copia difiere fuera del margen de fotogramas.
- Resolución de cortes en segundos y source_id contra originales locales, con comprobación de que no se hayan cambiado.
- Rechazo de archivos propietarios 360 sin coser. Copia panorámica equirectangular opcional, sin recortar la esfera.

Prueba inicial: vídeo sintético 1080p de 4 segundos, 7.767.117 bytes → 178.910 bytes, 960×540, duración exactamente 4,0 s. Ahorro 97,7%. La prueba no mide el rendimiento de vídeos reales largos, 4K/VFR, ni todos los formatos 360. No permite garantizar ese porcentaje en otros archivos.

Pendiente antes de ofrecerlo como función pública:

1. Conectar la selección de archivos y el preparador local con el cuadro de entrada, mostrando preparación, tamaño y progreso reales. Dejar de enviar originales por defecto.
2. Empaquetar un auxiliar local con permisos limitados a los archivos elegidos y emparejamiento con la web; sin acceso general al terminal. Añadir cancelación, espacio disponible, recuperación y pruebas Mac/Windows/Linux.
3. Subir únicamente copias, audio y datos necesarios. El servidor devuelve una receta de edición con source_id y tiempos, sin depender de rutas del ordenador.
4. Conectar esa receta al motor local completo para exportar originales, sonido, 360, efectos y recursos. Resolver proxies/originales es la base; el renderer universal y su integración aún no están implementados.
5. Pruebas con VFR, rotación, offsets de audio, sincronización multicámara y reconexión de archivos; las coordenadas visuales deben transformarse correctamente entre copia y original.
6. Adaptadores GPU según plataforma y medición CPU/GPU reales. Usar fallback CPU cuando sea necesario.
7. Más adelante, alternativa de subida reanudable de originales y render remoto con coste explícito. No obliga al cliente que elige exportación local a subir su material completo.

La aplicación web actual conserva su importación anterior. Este prototipo todavía no cambia lo que hace el box ni convierte el producto en un editor totalmente local dentro del navegador. No se han contratado servidores.
