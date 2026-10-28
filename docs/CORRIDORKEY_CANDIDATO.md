# CorridorKey 2.0: candidato para una prueba futura

28 de octubre de 2026. Decisión del propietario: mantenerlo apartado y evaluarlo cuando haya servidor con GPU compatible. No integrarlo ni contactar comercialmente hasta medir su utilidad.

Fuente inspeccionada: [CorridorKey2.0, commit 485f5e9ab759ead6138cc990776184b59d6ea971](https://github.com/nikopueringer/CorridorKey2.0/tree/485f5e9ab759ead6138cc990776184b59d6ea971).

- El código Python exige CUDA; su adaptación a poca memoria no es un fallback CPU/Intel/Metal. El Mac Intel examinado no lo ejecuta. La instalación oficial de torch 2.9.1 carece de rueda para ese Mac.
- Se descargó el código en un entorno separado. **No se ejecutó la red ni se descargaron sus pesos**; no hay calidad o tiempos propios de CorridorKey medidos.
- Se prepararon tres fragmentos de biblioteca de tres segundos, 640×360, con referencia del recorte actual: persona, humo y Matrix. No son un benchmark de 1080p/4K. Matrix es verde sobre negro: necesita el tratamiento de fondo negro, no quitar el verde.
- Hipótesis a probar: pelo, bordes de movimiento, semitransparencias, pantalla desigual y contaminación de color. Comparar todos los frames y fondos claros/oscuros, manteniendo sujetos y sin parpadeo. No asumir recorte perfecto de cualquier fondo.
- Medir arranque y modelo residente, RAM/VRAM, disco, latencia y coste; guardar versiones y hashes de modelos. Conservar el recorte ligero cuando ya basta y estudiar caché por fragmento.
- El plugin comercial y el repositorio Python tienen requisitos/plataformas distintos. Una licencia de plugin de escritorio no equivale a autorización de integración SaaS.
- La [licencia inspeccionada](https://github.com/nikopueringer/CorridorKey2.0/blob/485f5e9ab759ead6138cc990776184b59d6ea971/LICENSE) requiere acuerdo escrito para integración comercial. Si la prueba compensa, explicar la situación del proyecto y consultar condiciones. No se ha enviado correo.

No resuelve YouTube, sincronía, mezcla, transcripción o planificación narrativa. Su ausencia no bloquea la primera prueba de Stage con CPU.
