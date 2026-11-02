# JÚPITER · EX-06 — cierre de validación de motor (2026-11-02)

**Estado:** `validado-lab` en Linux CPU; integración y publicación del motor **pendientes**.

## Implementación
- Motor ZuckerVideos `ff9baf4`, worktree local aislado `/home/fer/zucker-videos-ex06`, rama `fernando/ex06-engine-lab`.
- Commit **local, no publicado en remoto**: `69b1f6b` `feat(360): optional CPU bilinear interpolation with cubic default`.
- Archivo `core/spherical_motion.py`: parámetro explícito `cpu_interpolation="cubic"|"linear"`, valor por defecto bicúbico, pasado a la ruta normal, hardware y fallback CPU. Solo afecta al `cv2.remap` final en CPU, sin modificar cálculo de mapas bicúbicos, rutas Metal ni variables globales.
- Pruebas nuevas `tests/test_ex06_cpu_interpolation.py`. Regresión: **34 passed, 1 skipped** (Metal macOS-only); prueba de parámetro y fallback satisfactorias; `git diff --check` limpio.
- A/B motor propio fuente fixture 640×320, 30 frames 960×540: bicúbico 0.520 s; bilineal 0.398 s. No extrapolar.

## A/B real 4K HEVC → 1080p30
- Original 3840×1920 a 25 fps. 30 fotogramas desde 840 s, salida 1920×1080 30 fps, FFmpeg CPU + libx264 ultrafast CRF18 threads 1; orden ABBA.
- Bicúbico: 2.251 y 1.991 s (media 2.121 s).
- Bilineal: 1.736 y 1.770 s (media 1.753 s).
- **Reducción observada 17.35%** en esas ejecuciones, no promesa de ahorro en E2E/conciertos.
- Tamaños: bicúbico 1,794,364 bytes; bilineal 1,679,976 bytes (−6.38%).
- Repeticiones idénticas byte por byte dentro de cada modo según SHA256:
  bicúbico `0cfea698a424c4d0987b173b394c91f7b4d958cf6f79e78a7f59645e47cc49d8`;
  bilineal `98b3b603d693a9769ecd2cfaeb8e955c0f7c11ee1a664939068a4a842b63a921`.
- Calidad MP4 de mismo frame y modo distinto: PSNR promedio **47.314116 dB**, SSIM global **0.992273**.
- Revisión visual humana de captura 1920×540 (dos recortes de 960×540 del fotograma 15, sin reescalado): bilineal algo más suave en contornos finos, micrófono, adhesivos, metal; no se observan deformaciones ni artefactos grandes en ese único recorte. No equivale a revisión exhaustiva de movimiento/otras escenas.

## Juicio
**Conservar EX-06 como opción CPU opt-in**, no cambiar el valor predeterminado. Prueba favorable de velocidad/calidad en Linux. Pendiente: validaciones Windows, macOS (incluyendo Metal), E2E y revisión más amplia antes de producción.

## Entrega / limitación crítica
- La PR de MONTARA [#68](https://github.com/amehcgracia-byte/Montara/pull/68) contiene solo el **adaptador experimental previo y su harness**, NO el commit nuevo del motor.
- El conector GitHub empleado no pudo crear rama en `amehcgracia-byte/zucker_videos` (403). El Git HTTPS de la VM tampoco tiene credenciales para publicar allí.
- **No actualizar puntero `engine/` en rama pública MONTARA para referenciar `69b1f6b` hasta que el commit sea accesible remotamente.** Un submódulo apuntando a commit local rompería clones/CI.
- Siguiente paso seguro: generar un `git bundle` local para preservar y transportar el commit, y después solicitar permiso limitado para publicar rama en ZuckerVideos, o entregar bundle a responsable de ese repositorio.
- No tocar `main` ni el checkout del otro laboratorio.

## Próxima línea de investigación
Auditoría de perfiles en motor, con especial foco en cálculo de mapas 360, accesos de memoria y posibles `loop interchange`, `loop tiling`, `loop fusion`. Antes de introducir cambios, localizar cuello de botella real y comprobar si NumPy/OpenCV ya vectoriza la operación.
