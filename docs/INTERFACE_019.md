# Montara 0.19 · 25 octubre 2026

Cambios instalados:
- How conserva Stage/Push/Show centrados. Explicaciones mínimas bajo el nombre, visibles con hover/foco; visibles siempre en pantallas sin hover.
- Intro: letras apiladas que se ordenan, con movimiento breve en las barras de la marca y desvanecimiento. Respeta movimiento reducido.
- Swap/Edit debajo de la imagen, con espacio propio. Previews siguen sobre la imagen; los botones ya no la tapan.
- Faders: muestran la ganancia automática real de cada pista, no solo un ajuste relativo que empieza a cero. La escucha conserva la misma ganancia que antes: el valor visible incluye la base automática y exportación recibe solo la diferencia manual. Se comprueba -6 dB en preview y payload. Reset vuelve a los niveles automáticos.
- Animación de faders desde abajo hasta su nivel real al preparar mezcla y master. Mientras anima no hay reproducción ni controles editables; no modifica ganancias al azar. La posición representa ganancia de pista, no un medidor de energía instantánea.
- Importación: INSV/MSV y otros originales propietarios 360 se rechazan antes de ingerirlos. Mensaje: exportar un MP4 360 cosido/equirectangular desde la aplicación de la cámara. Guardia en navegador y backend.
- Finalización: sustituye el detalle confuso joining segments 100% por una explicación de unión, comprobación y guardado; no da 100% antes de acabar. Los logs de la prueba del usuario muestran reparación automática de cadencia tras detectar un salto de 0,1 s frente a 0,0333 s esperado. El proceso terminó; no se ha cambiado ese mecanismo de corrección ni prometido acelerar su duración.

Sin cambios al algoritmo de mastering con referencia aprobado por el usuario. Informe separado con LUFS y true peak; no es prueba A/B causal ni puntuación de calidad.

Proxies: nuevo módulo local experimental, con caché, identificadores, separación de metadatos privados/públicos y resolución de cortes contra originales. Prueba sintética 1080p de 4 s: 7,77 MB → 0,18 MB, duración completa conservada. NO está conectado aún al cuadro de subida ni al renderer completo; no cambia la subida actual ni evita hoy subir los originales a una futura instancia remota. Ver LOCAL_PROXIES_019.md.

Validación:
- 11 pruebas Python existentes de FX/importación pasadas.
- Prueba adicional de proxies pasada (duración, tamaño, privacidad, caché, selección del original e invalidación).
- Prueba Node de ganancia visible, escucha, offsets de exportación, mute y reset pasada.
- Guardia backend devuelve 415 ante INSV/MSV/.360 antes de ingerir.
- Navegador: niveles automáticos visibles distintos, voz de -12 a -18 dB, escucha y exportación; el archivo de ajustes guarda -6 dB relativo. Master descargable completado.
- Rectángulos del navegador confirman botones después del borde inferior de la imagen, sin superposición. Capturas de How, intro, faders y frames guardadas.
- Compilación Python y sintaxis JS verificadas.
- Falta ejecutar e2e_journey en Linux; las pruebas locales no sustituyen ese requisito.

La escucha web conserva su aproximación de faders/pan y compresor de seguridad; no se presenta como reproducción idéntica de todo el EQ/dinámica/master del render Python. La corrección de ganancia no cambia el balance aprobado en la exportación.

Instancia local http://127.0.0.1:8086/, conserva el proyecto abierto. Sin cambios en engine/ ni mixer/. Sin compra de dominio/marca, despliegue, servidor o coste contratado.
