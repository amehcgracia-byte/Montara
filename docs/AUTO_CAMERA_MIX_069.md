# 0.69 — máster automático de vídeos y pistas

## Comportamiento

Stage con vídeos y dos o más pistas separadas (también una copia larga enviada
como preview): analiza el índice de audio, sincroniza cámaras, selecciona sólo
su intervalo fiable, mezcla y masteriza automáticamente y abre cámaras/rango
con un único máster descargable. No prepara otro excerpt del mixer web ni espera
la aceptación de sus faders. Hay mensajes y actividad durante análisis, búsqueda
y mezcla/master. Si no hay coincidencia fiable, no se mezcla la jam completa.

Sólo audio + Full session mantiene detección, canciones separadas, revisión,
mixer por canción, Confirm y exportación. Un máster normal con vídeos conserva
el recorrido habitual. No hay cambios en los submódulos.

## Preparación compacta

Las nuevas copias Opus de Stage acompañadas de vídeos (incluso si éstos todavía
están subiendo) se registran como Ogg Opus, sin expandir toda la grabación a WAV.
La inspección conserva time_reference dividido por el sample rate original;
Opus se decodifica a 48 kHz, que NO es necesariamente el reloj del grabador.
Sólo la ventana confirmada se prepara desde originales mediante las rutas
existentes de Companion/rangos. El resultado no se mezcla desde el proxy.

Si el audio empezó a subirse antes de añadir cualquier vídeo, o se reutiliza una
subida ya expandida, se conserva el WAV existente. No se modifica una carga en
curso, no se borran originales/cachés y no se promete un porcentaje de ahorro.
La guía de sincronización todavía debe recorrer el audio para encontrar dónde
está el fragmento desconocido. Las canciones de Full session no cambian de flujo.

La transferencia indica preparación tras enviar los bytes. Una respuesta de
chunk que no avance falla de forma acotada, en vez de repetir indefinidamente.

## Verificación

Pendiente de completar: aceptación real cámara + dos pistas comprimidas,
regresión audio-only Full session, Stage/Push/Mix y Linux con capturas revisadas.
Engine 4f481002950a9dd1488957cac0214d5a0759c909;
Mixer f15ff91c1b80fc5f157099dcd9451d958d553ae6.

## Usuarios

La base #100 sigue aislada y opt-in. No se activan cuentas públicas ni Google.
Petición de Chema coordinada con FER en issue #34, comentario 6694605277:
página de prueba, identidad Google verificada en servidor y proyectos por dueño.
