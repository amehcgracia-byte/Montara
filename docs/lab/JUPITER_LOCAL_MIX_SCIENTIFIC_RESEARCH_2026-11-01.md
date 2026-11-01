# JÚPITER — Investigación externa sobre mixer local (2026-11-01)

**Estado:** revisión documental de fuentes primarias y código actual; NO implementación, NO benchmark Mac. Complementa `JUPITER_COMPANION_MAC_LOCAL_MIX_FEASIBILITY_2026-11-01.md`. Referencia `main` comprobada: `7b70626ae79c90bc8208fd0a8ac499c66e73a8b9`. Trabajo independiente del otro laboratorio.

## Preguntas, evidencia, inferencias y experimentos falsables

### 1. Distribución Mac sin Python externo
**Confirmado en código:** `companion/install.sh` pide Python >=3.9 y FFmpeg, descarga solo `companion.py`; no instala el mixer. ZuckerMixer documenta builds de macOS/Windows y una versión de build Python 3.12, y separa `requirements_app.txt` de `requirements_whisper.txt`.

**Documentación externa:** PyInstaller soporta `x86_64`, `arm64` y `universal2`, pero un paquete universal exige que **todas** las dependencias binarias tengan ambas arquitecturas. PyInstaller firma ad hoc por defecto, sin sustituir la distribución notarizada de macOS. [PyInstaller feature notes](https://pyinstaller.org/en/stable/feature-notes.html) y [usage](https://www.pyinstaller.org/en/stable/usage.html). Los venv tienen rutas absolutas y no son directamente portables: [Python venv](https://docs.python.org/3/library/venv.html). Nuitka advierte sobre dependencias nativas y crecimiento del paquete: [Nuitka docs](https://nuitka.net/user-documentation/common-issue-solutions.html).

**Propuesta:** tres builds comparables, aislados del UI: (A) wheelhouse bloqueado + creación de venv por instalador; (B) PyInstaller onedir arm64/x86_64; (C) reutilización de scripts de empaquetado de ZuckerMixer solo para worker headless. Medir tamaños .zip/.dmg, carpeta descomprimida, tiempo de arranque frío/caliente, instalación limpia, Gatekeeper y memoria. No dar por medido el intervalo preliminar de 150–500 MB.

### 2. Dependencias y versiones: riesgo prioritario
**Confirmado en repos:** `ZuckerMixer/requirements_app.txt` (rama `claude/winds-synth-bass-lowpass`) declara `matchering==2.0.6`, `numba==0.60.0`, `llvmlite==0.43.0`; `Montara/main:requirements.txt` declara `numba==0.62.1`, `llvmlite==0.45.1` y `numpy>=1.26,<2`. NO intentar instalar ambos sets en un solo venv sin resolver conflictos/compatibilidad. No asumir que versiones recientes solucionan todo.

**Actualización del estado del arte:** la tabla oficial de Numba incluye 0.68.0 (2026-09-30) con llvmlite 0.50.x y Python <3.16, compatible con un rango de NumPy; cada actualización implica nuevos LLVM/JIT. [Numba compatibility](https://github.com/numba/numba/blob/main/docs/source/user/installing.rst), [llvmlite](https://github.com/numba/llvmlite).

**Propuesta:** conservar **primero** el set fijado por ZuckerMixer en worker aislado; establecer matrices Python/arquitectura/wheels y pin SHA del mixer. Probar actualización de Numba solo en un experimento separado con tests de referencia, no mientras se evalúa la portabilidad inicial.

### 3. Performance en Apple Silicon: oportunidad, sin afirmar aceleración automática
Apple Accelerate/vDSP proporciona FFT, filtros biquad y operaciones vectoriales optimizadas: [Apple Accelerate](https://developer.apple.com/documentation/accelerate). SciPy añadió soporte de Accelerate en 1.14 para determinados cálculos y reporta mejoras de álgebra lineal y wheel más pequeño en macOS: [SciPy release notes](https://docs.scipy.org/doc/scipy/release/1.14.0-notes.html). No extrapolar a los efectos específicos del mixer sin perf profiling.

**Experimentos:** mismo Mac, misma canción, mismo SHA y mismo entorno; 1 frío + >=3 calientes; cronometraje separado de FFmpeg decode/preparación, inspección, auto-mix, efectos, mastering, encode; RSS/carga/energía/caché, correlacionado con el perfil de funciones. Comparar opción Accelerate solo si profiler demuestra que el kernel relevante usa esa ruta, sin cambiar dos variables a la vez.

### 4. Equivalencia audio: normas y criterio de falsación
`session.py` usa FFmpeg para ventanas, offsets, padding y PCM f32le; después `SingleSongMix` usa procesamiento del submódulo. Por tanto, pasar un JSON con faders sin resolver fuentes/offsets **no basta**. `track_types`, EQ, FX, panorámica, selección de pistas, L/R, referencia, sample rate y manejo de silencio deben formar contrato versionado.

ITU-R **BS.1770-5** define medición LUFS/true-peak: [ITU](https://www.itu.int/rec/R-REC-BS.1770-5-202311-I/es). Para A/B: primero WAV/PCM antes de MP3 con muestras alineadas; duración y desplazamiento, null residual y error RMS, LUFS y true peak, cortes/transitorios, escucha ciega de casos problemáticos. Tras MP3 comparar PCM decodificado y parámetros (los hashes MP3 pueden variar por versiones, tags y metadatos). Definir umbrales **antes** de medir; un solo valor no garantiza equivalencia perceptual.

### 5. Alternativa novedosa: worker versionado, no convertir Companion entero en ZuckerMixer
**Hipótesis de arquitectura:** Companion sigue sirviendo proxies y localización; worker de render por canción separado por proceso y venv/binario, con `mixer_git_sha`, `adapter_schema`, `python_runtime`, `ffmpeg_build`, plataforma y hash del manifiesto. Módulo `mixer_adapter/session.py` actual usa subprocesos para aislar globals del vendor: preservarlo. Cache temporales con TTL/quota; excluir inputs no seleccionados.

**Economía:** comparar transferencia de Opus 192/256k por cada pista/rango vs un MP3 final (e.g. 4 min a 320k ~9.6 MB decimal) incluyendo Opus ligero inicial, procesado local, tránsito WAN, fallbacks y esperas; en una línea 7.6 Mbit/s 9.6 MB serían ~10.1s mínimos ideales, NO tiempo real. Para 7 pistas mono 4 min f32le 44.1kHz temporal ~296 MB antes de procesamiento/otros temporales. No reemplazar números medidos de Chema por estas extrapolaciones.

## Gates de adopción (en orden)
1. Compatibilidad exacta: mixer SHA y set de dependencias versionados, import/render en Mac arm64 e Intel con instalación limpia.
2. Fiabilidad audio: mismos dos fixtures reales/sintéticos de consola en servidor y Mac, con estándares y tolerancias acordados, y casos con FX, offsets y L/R.
3. Economía de usuario: tiempo Confirm→MP3 en VM; tráfico real; CPU/RAM/SSD; simulación de fallo, cancelación y suspensión.
4. Si y solo si mejora, prototipo local opt-in y fallback automático sin tocar la UI. Seguridad: sólo localhost; validar permisos de origen, rutas, manifiesto y salida; no aceptar ejecución arbitraria. Revisar distribución GPLv3 de ZuckerMixer/Matchering.

**Sin cambios de código, ni recursos externos nuevos, ni pruebas de pago ni ejecución en VM.** Publicar únicamente investigación y atribuir cifras no medidas a estimaciones.
