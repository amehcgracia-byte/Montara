# JÚPITER W3R — puerta de licencias y distribución (análisis inicial)

**Fecha:** 2026-11-05. Ámbito: Companion Windows PR #74 en draft, no release, no publicación de FFmpeg, no merge ni cambios en producción.

## Evidencia verificada en fuentes primarias

- **Gyan, builds Windows:** https://www.gyan.dev/ffmpeg/builds/ — el propio distribuidor indica que todos sus builds estáticos (incluidos `essentials`) están licenciados bajo **GPLv3**. Se pueden usar para experimentar y estudiar integración, pero una distribución a terceros exige revisar las condiciones aplicables.
- **FFmpeg, licencia:** https://ffmpeg.org/legal.html y https://ffmpeg.org/doxygen/trunk/md_LICENSE.html — FFmpeg suele ser LGPL 2.1+ por defecto; determinados componentes opcionales activados con `--enable-gpl` pasan la compilación a GPL. No existe opción de comprar una licencia propietaria de FFmpeg a su proyecto.
- **GNU, FAQ sobre programas independientes:** https://www.gnu.org/licenses/gpl-faq.es.html — dos programas comunicados a través de interfaces separadas pueden ser obras distintas, pero depende de detalles técnicos y jurídicos; **no es un permiso automático** por lanzar un proceso con `subprocess`.

## Situación del laboratorio

- Tests W3L–W3Q: EXE congelado mediante PyInstaller y herramientas externas `bin/ffmpeg.exe` y `bin/ffprobe.exe`, invocadas como procesos separados.
- W3P Windows Actions creó únicamente carpeta **temporal** de ~238.5 MB en el runner de prueba; no adjuntó artifact ni release. La prueba visual W3Q local usa el EXE anterior del usuario, sin acreditar el paquete integrado definitivo.
- El pipeline de proxy requiere la codificación H.264 `libx264` en el camino software. Por ello, una migración a un build LGPL sin x264 **no es intercambiable sin cambio de encoder y pruebas funcionales adicionales**.
- No se ha verificado que el producto completo (frontend/backend y otras dependencias) sea compatible con una licencia específica; tampoco se ha confeccionado el paquete de avisos y fuentes correspondientes.

## Opciones para decisión futura

1. **Cumplir GPLv3 para el FFmpeg distribuido:** preservar avisos y derechos, ofrecer el código fuente correspondiente a esos binarios y materiales de compilación conforme corresponda, y verificar jurídicamente separación con Montara y demás obligaciones. Puede ser viable para un producto comercial; GPL no significa prohibición de venta. Requiere revisión de asesoramiento jurídico especializado.
2. **Producir/procurar compilación LGPL adecuada:** reducir complejidad GPL si se puede evitar `--enable-gpl`, pero habrá que sustituir `libx264` por un encoder realmente disponible y medir calidad, rendimiento, soporte y garantías; revisar igualmente cumplimiento LGPL.
3. **No empaquetar FFmpeg:** exigir una instalación separada o selección de ruta por usuario, con menor simplicidad UX. Tampoco supone automáticamente que desaparezcan todos los requisitos de licencia y debe revisarse.

**Recomendación técnica provisional:** mantener el bundle solo en CI privado, sin distribuirlo, documentar de forma transparente el cumplimiento de GPLv3 y preparar decisión con JM/asesoría antes de publicar. No eliminar `libx264` ni cambiar codec del motor por motivos legales sin evaluación del impacto del producto.

## Próximos pasos autónomos

- Completar inventario de dependencias y obligaciones de terceros en la PR; documentar versión y checksum del binario elegido.
- Proponer checklist de publicación segura (licencia/fuentes/avisos, procedencia, firma/SmartScreen, actualización, ejecutable/lanzador).
- Cerrar reporte W3S separando **PASS técnico experimental** de **NO GO de release** hasta resolver licencias y aceptación del paquete final. Única participación necesaria del usuario: decisión comercial/jurídica y eventual validación final del paquete autorizado.

**Nota:** análisis técnico y referencias de licencia, no dictamen jurídico definitivo.
