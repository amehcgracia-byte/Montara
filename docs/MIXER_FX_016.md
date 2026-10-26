# Montara 0.16 — FX por pista

Instalado en /Users/macbookair/Desktop/Montara. Instancia local: http://127.0.0.1:8086/.

- Botón FX en cada pista, reverb y delay fijos, encendido independiente e intensidad 0–100%.
- Los efectos apagados conservan su intensidad para volver a activarlos.
- Previsualización al reproducir, con cambios de intensidad sin renderizar el vídeo.
- Reutiliza plate_reverb_streaming y slap_delay_streaming del mixer sin modificar su submódulo. Ajustes fijos: reverb 1,7 s; delay a 90 BPM.
- El adaptador prepara audio húmedo por pista bajo demanda y lo guarda en caché. El mismo audio húmedo alimenta la escucha y se suma a la pista antes del procesado de mezcla/master final; desactiva los envíos automáticos para evitar duplicación. La escucha conserva la aproximación de niveles/pan del mixer web y no sustituye al master con su compresión/EQ.
- Los controles funcionan también en pistas cuyo rol original no tenía envío de delay. Silenciar/variar fader actúa sobre pista y efectos.
- Cambiar de trabajo limpia las pistas de audio de la caché del navegador.

Validación realizada en macOS:
- Fragmento real de voz de 12 s e impulso de prueba; reverb y delay generan señal posterior al impulso.
- Comparación exacta del audio húmedo al 40%; pista vecina sin modificar.
- Render completo con efectos y bypass: archivos finitos, misma duración, contenido diferente.
- Entradas WAV y MP3, caché reutilizada, intensidades inválidas y pistas desconocidas rechazadas.
- Recorrido con navegador: FX → reverb 65% + delay 35% → Play/Pause → Use this mix → master descargable HTTP 200.
- Comprobación sintáctica de JS y compilación Python.
- No se ha ejecutado la prueba e2e_journey de Linux; esta validación no la sustituye.

El proyecto de música que estaba abierto se conserva. No se ha contratado infraestructura ni enviado vídeos a servicios externos.
