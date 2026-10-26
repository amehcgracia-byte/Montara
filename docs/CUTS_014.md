# Montara 0.14 — cortes editables

Las líneas naranjas se arrastran hacia los lados. Se guarda una vez al soltar; no se lanza una previsualización en cada movimiento. Doble clic abre el tiempo exacto del corte en el vídeo completo. Las flechas mueven un fotograma; Mayús + flecha, medio segundo.

- Gamer e Influencer: pista de cortes del vídeo. Botón derecho sobre un plano abre su encuadre; se elige el punto haciendo clic en la imagen y se ajusta el zoom.
- Podcast: pistas separadas para los cortes de voz y los cambios de cámara. El botón derecho sobre un plano de cámara conserva el selector de cámara/tiro 360.
- Story: cortes de voz y pista de imágenes. Se pueden mover todos los cambios entre imágenes, y el botón derecho abre las decisiones para sustituir material. En entrevistas con intervalos fuente explícitos a velocidad real se conserva la velocidad: si falta imagen, se sostiene el fotograma del extremo. Los otros materiales conservan su tratamiento de montaje.
- Stage y Pulse: pista de cortes en la revisión de planos. Botón derecho, o clic, permite elegir una cámara disponible en ese intervalo y ajustar un tiro 360. «Preview shot» genera solo ese plano cuando se pide.

La duración del programa y el reloj de la canción no cambian al desplazar un corte. Se limita el movimiento entre los planos vecinos, dejando al menos 0,2 s por plano; música respeta también los extremos de los vídeos fuente. No hay salto de sincronización de la canción. Los cortes que caen dentro de una pausa eliminada siguen accesibles en la unión visible.

Después de cambiar cámaras o imágenes en Podcast/Story se pide «Preview this part» para actualizar el programa. Se impide reproducir una copia antigua como si ya contuviera esos cambios. La exportación también actualiza el programa pendiente.

API: GET/PATCH /api/v1/edit/timeline; GET/PATCH /api/v1/edit/shot. Proyecto y revisión obligatorios para las escrituras. Se rechazan documentos antiguos y cambios durante un render activo. Cambios de cortes registrados en el historial como ediciones manuales sin validación editorial.

Validación en macOS: pruebas de límites, continuidad, revisiones, persistencia, cámara concreta, velocidad de entrevistas y fotogramas sostenidos; render sintético confirma el nuevo instante real de cambio de cámara. Prueba visual de arrastre en Podcast, corte y encuadre en Show, y corte/cámara/previsualización/exportación en Pulse. La comprobación Linux e2e_journey de CLAUDE.md no se ha ejecutado en este Mac.
