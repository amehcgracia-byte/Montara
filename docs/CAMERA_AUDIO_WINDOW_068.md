# 0.68 — pistas largas y vídeos: sólo el intervalo necesario

Base main ae9e38b; Engine 4f481002 y Mixer f15ff91 conservados.

Con vídeos y pistas largas separadas, la 0.67 detectaba todas las canciones,
creaba su guía de escucha y después seleccionaba una canción entera. La 0.68
separa la localización del trabajo de mezcla:

1. Inspección de metadatos de todos los micros e interpretación de sus offsets existentes.
2. Guía mono de búsqueda a 24 kHz, sumada por bloques. Su onda se obtiene de
   esos mismos bloques, sin otra decodificación de todos los micros.
3. Sin detección de todas las canciones, envolventes por instrumento ni revisión
   de límites por IA. Reutiliza la sincronización real del Engine por HTTP.
4. Encuentra el intervalo continuo cubierto por las cámaras sincronizadas. Exige
   sincronía fiable de cada cámara y cobertura solapada o con un hueco máximo de
   un segundo; los casos separados/dudosos requieren revisión, no inventar un mix.
5. Sólo ese intervalo entra al mixer. Tras aceptar, extracción de los rangos de
   todos los micros y masterización de ese intervalo, con las reglas de offsets
   y el flujo existente Companion/servidor. Un solo máster descargable pasa al rango.

Los originales se mantienen intactos. La guía de búsqueda sí recorre las copias
ligeras completas: sin información temporal previa no podemos conocer dónde está
el vídeo sin buscar. Esto no promete omitir toda lectura de la jam ni una mejora
porcentual de tiempo total. Los PCM de mezcla y los rangos de calidad original
quedan restringidos a la sección elegida.

Audio-only + Full session conserva la detección y exportación de varias canciones.
Las sesiones antiguas sin video_excerpt conservan su política previa al recuperarse.
Los casos de varias canciones distintas y la edición distribuida no se amplían aquí.

Pruebas: seguridad de rangos (confianza, offsets negativos, límites, cámaras separadas),
guía real de dos micros con offsets y onda reutilizada sin llamar al detector de
canciones, validación de modo/progreso y recorrido real navegador → guía → sync →
mixer → máster → rango. El fixture de integración usa dos pistas de 390 s y una
cámara de 20 s ubicada en t=240; debe extraer y mezclar sólo ~20 s de cada pista.
Los resultados de aceptación completos se registran en la PR, sin extrapolar
esos datos a grabaciones reales de cuatro horas.
