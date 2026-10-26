# Montara 0.16.1: ganancia de pistas con FX

Causa reproducida: el adaptador convertía las pistas mono con efectos en estéreo duplicado. El motor aplica distinta ley de panorámica a mono y estéreo, con un incremento de 3,01 dB del sonido seco al activar cualquier efecto.

Corrección: mantener la disposición mono/estéreo original tanto en el audio húmedo de previsualización como en la pista preparada para exportar. Nueva versión de la caché de FX para no reutilizar archivos estéreo antiguos.

Además cada operación reactiva la carpeta del trabajo correcto y utiliza sus propios ajustes de mezcla. El análisis automático usa un snapshot limpio; no lee faders/mutes persistidos de otra mezcla. La referencia de mastering se asigna después de resolver el plan para que no sea sobreescrita por el estado global del proveedor.

Comparación con las nueve pistas de la canción de prueba, 80 segundos, reverb 65% y delay 35% sobre voz:
- Antes: incremento de voz de 3,329 dB frente a la mezcla seca.
- Después: incremento de 0,319 dB por el audio húmedo añadido.
- Pico verdadero del master WAV: -4,1 dBFS, con y sin FX, después de corregirlo.
- Los masters originales del usuario medidos estaban bajo 0 dBFS: esto demuestra desequilibrio de nivel, no clipping digital de salida. No prueba que toda distorsión percibida tenga esa única causa.

Validación:
- Cuatro pruebas pytest pasadas (mono/estéreo × reverb/delay): efectos casi a cero no cambian la ganancia seca; intensidad al 65% equivale a seco + 0,65 × húmedo.
- Dos masters con FX idénticos muestra por muestra, incluso intercalando otro trabajo con +12 dB y mute.
- Mezcla automática nueva con fader 0 y sin mute heredado.
- Dos exportaciones completas de 80 s, con y sin FX, con audio finito y sin superar el techo digital medido.
- Compilación Python y sintaxis JS comprobadas.
- No se ha ejecutado e2e_journey en Linux; las comprobaciones locales no sustituyen ese requisito.

Instalado en /Users/macbookair/Desktop/Montara, servicio local 8086. No se modifica engine/ ni mixer/. Se conserva el proyecto abierto y los masters anteriores. Es necesario recargar la página y crear una mezcla nueva para descartar buffers y trabajos previos.
