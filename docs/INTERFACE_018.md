# Montara 0.18 · 2026-10-25

- Entrada: solo el nombre de Montara animado, con aparición escalonada, breve pausa y desvanecimiento. Pasa automáticamente a elegir modo. Clic, Enter/Escape permiten saltarla. Movimiento reducido respetado.
- Selector: How centrado; Stage, Push y Show centrados, sin puntos ni descripciones. Navegación de pasos oculta en esta pantalla.
- Mastering: archivo local conservado y nuevo formulario de enlace, con importación en segundo plano y estado visible. Solo se cambia la referencia tras obtener audio válido; fallo conserva la referencia anterior. No se puede exportar mientras se prepara.
- Spotify: error explícito porque el enlace de la canción no da acceso al audio completo. No se sustituye por otra grabación ni se afirma haber usado el tema. YouTube depende de que el servicio permita acceso; se informa si exige autenticación/verificación.
- Frames: previsualización muda al situarse sobre la imagen (250 ms de espera), una sola reproducción activa, pausa y descarga detenida al salir. Precarga solo durante la interacción. Usa la URL/cache de preview del motor. Swap y Edit en el centro de la imagen. Edit reutiliza controles de 360 o zoom de cámara plana. Sin botones Preview por escena.

Validación local macOS:
- 7 pruebas de importación pasadas: enlaces no válidos/privados/Spotify, extracción de audio y limpieza temporal.
- Descarga real desde SoundHelix, conversión de audio y recorrido navegador → Use link → Reference ready → Use this mix → master descargable.
- Reproducción de frame confirmada readyState=4 y paused=false; se detiene al salir y al editar. Cero botones .shot-preview. Edit abre el encuadre de cámara; Swap probado en copia aislada.
- Intro y llegada automática a How verificadas; capturas de selector, introducción, frames y referencia guardadas.
- Sintaxis JS y compilación Python verificadas.
- No se ha ejecutado e2e_journey en Linux: estas comprobaciones locales no sustituyen ese requisito.

Instancia instalada: http://127.0.0.1:8086/. Solo local. Sin cambios en engine/ ni mixer/. Se conserva el proyecto que estaba abierto.

La propuesta de proxies locales y exportación en el ordenador del cliente NO está implementada en esta versión. Hoy la aplicación conserva su mecanismo de importación anterior.
