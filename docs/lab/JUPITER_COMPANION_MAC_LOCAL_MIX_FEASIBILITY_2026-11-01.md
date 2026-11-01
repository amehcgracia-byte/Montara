# JÚPITER — Viabilidad de mezcla local en Companion Mac (solo investigación)
Fecha: 2026-11-01 · Responsable: laboratorio Fernando · Estado: **investigado, NO implementado, NO benchmark Mac**

## Decisión propuesta
**GO a prototipo aislado y medido; NO-GO a despliegue directo.** Enviar al servidor un MP3 final por canción puede reducir mucho el tráfico tras la detección, pero antes hay que garantizar equivalencia de la mezcla, un contrato de plan/versiones, una distribución reproducible y fallback remoto. El Opus ligero inicial para detección/ondas sigue siendo necesario en la arquitectura actual: «que no se suba nada» no es literal.

## Evidencia de producto, versión y coordinación
- Fuente de encargo: issue #34 comentario 6558088838. Chema observó proyección de 140 min por transferencias de 12 canciones, CPU VM ~1.6/8. Es un diagnóstico contextual, **no** benchmark del nuevo diseño.
- Main consultado 2026-11-01: HEAD `7b70626ae79c90bc8208fd0a8ac499c66e73a8b9`; Companion 0.4.0; `companion/companion.py` usa Python stdlib + FFmpeg y puerto 47820; `companion/install.sh` descarga solo el script y requiere Python >=3.9 y FFmpeg. NO instala mezcla científica.
- Comparación main...fernando/continuacion-montara: ramas divergidas, 272 commits ahead y 108 behind; NO sincronizar ni modificar código de producto para esta fase.
- `docs/lab/STATUS-JM.md`: ZuckerMixer en PR #8 `claude/winds-synth-bass-lowpass` no fusionada en master. Debe fijarse **SHA de submódulo, no nombre de rama** en compilación y contrato.
- `mixer_adapter/session.py`: `prepare_tracks` corta, alinea por offset y rellena silencios con FFmpeg a PCM float32; `render_song` aplica `settings.per_song`, tipos, faders, mutes, FX, EQ, referencia y `SingleSongMix.render`. El mixer utiliza estado global, por eso se ejecuta en subproceso por canción. Mover solo `mixer/` NO replica el render.
- `mixer_adapter/single_song.py`: el estado del proveedor se inicializa en imports y `SingleSongMix` reutiliza adaptador y módulos del submódulo. En el Companion hay que reproducir también la extracción temporal, tipos y manifiesto de sesión; sin copiar rutas/archivos del servidor como si existiesen en Mac.
- No se ha lanzado el Companion ni ZuckerMixer en Mac y **no se ha medido** tiempo ni tamaño de paquete real.

## Dependencias y tamaños: hipótesis para presupuesto, NO mediciones
- Necesarias en ruta de render, confirmar con import tracing: Python runtime compatible con Matchering/Numba (ZuckerMixer documenta build soportado Python 3.12), numpy, scipy, soundfile (+libsndfile), pyloudnorm, matchering==2.0.6, numba/llvmlite compatibles, FFmpeg/ffprobe, adaptadores Montara, código ZuckerMixer y datos auxiliares.
- `ZuckerMixer/requirements_app.txt` actualmente enumera además Flask, pywebview, PyInstaller, Pillow, certifi (herramientas/UI/build **no necesariamente necesarias en runtime embebido**); `requirements_whisper.txt` incorpora faster-whisper en runtime separado para detección, **no incluirlo de entrada** en binario exclusivo de render. No copiar indiscriminadamente el `requirements.txt` completo de Montara (incluye engine y visión).
- **Estimación de planificación no verificada**: runtime + scipy/numpy/numba/llvmlite/matchering + dependencias y FFmpeg puede ocupar **150–500 MB instalados o más**, dependiendo de arquitecturas/compresión/paquetes. Instalador comprimido podría variar ampliamente; NO tratar cifra como resultado ni promesa. Medir con `du -sh` y tamaños ZIP/DMG en Intel x86_64 y Apple Silicon arm64, con caché limpia, anotando versión de Python, FFmpeg y wheels.
- Alternativa A (preferida para primer prototipo): venv exclusivo y versionado para mixer, instalado en carpeta privada del Companion con ruedas/hash fijados; ventajas: actualización y depuración; inconvenientes: descarga inicial, dependencia de Python compatible, wheels/macOS y conectividad.
- Alternativa B: PyInstaller onedir por arquitectura (+FFmpeg): sin Python externo y distribución offline, pero más peso, firma/notarización/Gatekeeper, antivirus, imports dinámicos de Numba/Matchering, librerías nativas. Evitar onefile primero por extracción repetida. `ZuckerMixer` ya tiene scripts de build/release Mac y Windows: **reutilizar su CI e inventario** antes de crear empaquetador nuevo.
- Licencias: ZuckerMixer y Matchering GPLv3; revisar compatibilidad y obligaciones de distribución/código fuente/licencias de dependencias antes de redistribuir binarios comerciales.

## Rendimiento y tráfico: hipótesis verificables
- Ejemplo matemático, no benchmark: MP3 estéreo 320 kbps / 4 minutos => 9.6 MB decimal; a subida 7.6 Mbit/s, mínimo teórico ~10 s sin overhead. 12 canciones => ~115 MB / ~2 minutos teóricos solo de subida, **si** duran 4 minutos cada una y se codifican correctamente. Si 192 kbps: ~5.76 MB por canción. Audio Opus de previsualización y latencias no incluidos.
- El consumo de CPU/RAM/SSD del mezclador local es desconocido; no afirmar «tiempo real» sin probar. Decodificación, análisis, FX, normalización/mastering y codificación pueden dominar. WAV temporal f32le: 44.1kHz × 4 bytes × 1 canal × 240s = ~42.3 MB por pista; 7 pistas mono ~296 MB en una canción, antes de copias, FX, cachés y salidas. El código reserva espacio de seguridad, comprobar espacio libre antes de empezar.
- Protocolo Mac normal: registrar chip (Intel/Apple Silicon), RAM, macOS, arquitectura, versiones SHA, FFmpeg y energía/temperatura; 1 tema de 3–5 min con 7 pistas, 1 frío + 3 calientes, con y sin FX/mastering. Capturar p50/p95, tiempo preparar/analizar/render/codificar, pico RSS, CPU, disco, MB de artefacto y upload WAN. Probar 12 canciones en secuencia y en paralelo limitado; la concurrencia sin límites puede saturar memoria.

## Riesgos principales
1. **Equivalencia**: offsets, silencios, fronteras, sample rate, canales estéreo L/R, asignación de tipos, filtros, faders, automatismos, efectos, referencias y metadatos. Comparar PCM decodificado con tolerancia perceptual/técnica definida (el MP3 puede ser no determinista a nivel byte).
2. **Versiones**: handshake `companion_version`, `mixer_sha`, `adapter_schema_version`, `ffmpeg_version`; servidor rechaza mezcla local con incompatibilidad y usa servidor. Pin de ZuckerMixer PR #8 es crítico.
3. **Seguridad**: endpoint local solo en 127.0.0.1 con validación Origin y token efímero por sesión, rutas locales autorizadas por usuario, no ejecutar comandos enviados desde web, inputs tipados y sin path traversal. Subida final con autenticación y checksum.
4. **Recursos**: Mac viejo, Intel vs arm64, wheels no disponibles, Numba JIT startup, memoria/SSD, OS antiguo, suspensión, micrófonos silenciosos, rutas desconectadas y caché sin límite.
5. **Resiliencia**: cancelación real de procesos descendientes, limpieza de temporales, reintento idempotente, progreso por canción, pérdida de conexión, actualización incompleta; fallback que no silencie diferencias ni sobreescriba el resultado.
6. **Producto**: actualmente la UI de escucha/ondas y detección corre sobre Opus; mover export no equivale a mover detección ni mezclar preview. No prometer cero subidas.

## Plan incremental propuesto (sin implementación en esta entrega)
0. Confirmar contrato de `session.json`, versiones de mixer y comportamiento de `render_song` con Chema; congelar SHA y fixtures, y establecer dos canciones de oro: mono/estéreo, silencios, offsets, EQ/FX.
1. **PoC de consola en un Mac**, sin modificar interfaz ni Companion: mismo plan y originales, render local vs servidor; medir tamaño dependencias y tiempos con hashes/versiones. Gate: audio y cortes equivalentes; condiciones explícitas de tolerancia.
2. Worker local aislado, preferiblemente proceso independiente con venv privado y endpoint `/capabilities` versionado (sin romper API existente). Datos de la canción por manifiesto firmado/validado y rutas resueltas localmente.
3. Enrutamiento de export por canción con timeout, progreso, checksum y fallback al servidor; no repetir trabajos completados. Feature flag opt-in. No confundir fallo de local con éxito remoto.
4. CI macOS Intel/arm64, clean install, validación Gatekeeper, comprobación de dependencias nativas, licencias y actualización/rollback atómicos.
5. Prueba con usuarios reales y métricas: tiempo desde Confirm a MP3 recibido, GB transferidos, tasa fallback, CPU/SSD, concordancia perceptual. Windows como trabajo independiente y sin bloqueo del Mac.

**Criterio de decisión:** si con 7 pistas/4 min el cliente mezcla de forma fiable, reproduce fielmente el plan y completa el recorrido más rápido que enviar rangos Opus 192/256k por la WAN, continuar. Si no, mantener server render y optimizar envío. No introducir cambios en `engine/`, `mixer/` ni `main`.

## Fuentes revisadas
`CLAUDE.md`, `docs/COLLABORATION.md`, STATUS-JM, STATUS-FER, INVENTORY-FER, RUNS.md; `companion/companion.py`, `companion/install.sh`, `mixer_adapter/session.py`, `mixer_adapter/single_song.py`, ZuckerMixer `requirements_app.txt`, `requirements_whisper.txt`, `README.md`; issue #34 comentario 6558088838.

*Alcance: investigación estática con GitHub, sin ejecutar nada en la VM/Mac, sin benchmarks nuevos, sin cambios de producto.*
