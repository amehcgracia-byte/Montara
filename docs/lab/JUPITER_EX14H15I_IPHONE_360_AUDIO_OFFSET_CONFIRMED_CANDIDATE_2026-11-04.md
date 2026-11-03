# JÚPITER · EX-14H-15I — confirmación amplia del offset iPhone / 360

Fecha de registro: 2026-11-04. Fuentes originales `IMG_0044.MOV` (iPhone H.264 3840×2160, 986.825s, AAC mono 44.1k) y `VID_20260824_204524_00_004.mp4` (HEVC 360 3840×1920, 911.64s, AAC estéreo 48k). Sin copiar originales ni escribir vídeo.

## Hipótesis y metodología

EX14H15H había detectado tres candidatos cerca de -19.03s en búsqueda [-20,+210]s. El borde inferior estaba próximo. EX14H15I amplió deliberadamente la ventana a **[-60,+210]s** y escogió tiempos 360 80–110, 340–370, 640–670s para no solicitar instantes negativos del iPhone. Audio decodificado por FFmpeg mono 4kHz; filtro pasabanda 150–1500Hz Butterworth y correlación cruzada FFT normalizada por energía de cada ventana de iPhone (`correlate(y,x,valid)`); picos de correlación absoluta.

| Ventana fuente 360 | Offset estimado iPhone relativo a 360 | Correlación pico |
| --- | ---: | ---: |
| 80–110 s | -19.0445 s | 0.1524 |
| 340–370 s | -19.0490 s | 0.1775 |
| 640–670 s | -19.0172 s | 0.2604 |

**Media offset: -19.0369s**. Máximo–mínimo **31.75ms**. El candidato **se mantiene al ampliar el margen inferior** y se observa a lo largo de ~560s entre ventanas extremas; no parece un simple artefacto del borde inferior anterior.

**Interpretación del signo:**
`t_iphone ≈ t_360 - 19.037s`. Por ejemplo, audio en instante 360=100s coincide aproximadamente con el audio iPhone=81s. No se ha medido todavía si la pequeña variación residual se debe a reloj variable, transcodificación, granularidad del método o deriva real.

**Estado: candidato acústico corroborado; NO se ha ejecutado SyncStage real**. No confundir con mapas heredados `camera-a.mp4` / `camera-b.mp4` de 20s marcados `done`, que no corresponden a estas fuentes. Los metadatos de fechas daban +97s entre inicios, en aparente conflicto con el audio; no asumir que los relojes de las cámaras están correctos ni deducir causa.

## Puerta siguiente

1. Revisar interfaz y esquema de SyncStage nativo del motor aislado y sus reglas de creación de proyecto y máster de audio, sin tocar el engine de Chema en producción.
2. Preparar proyecto nuevo aislado, referencias a originales sin copiarlos; test corto o ventana controlada de SyncStage para las dos fuentes, comparar resultado nativo con -19.0369s y confianza/consenso entre ventanas.
3. Antes de afirmar precisión de sincronización, confirmar picos/consenso temporal, buscar falsos positivos musicales y comprobar deriva o dispersión de 32ms. No generar MP4 largo en esta fase.
4. Mantener >12 GiB de disco libre; no confiar en locks del guest para prevenir el apagado externo GCP `gcloud instances stop` documentado en issue #71.

Sin modificaciones productivas ni cambios de flags EX07/13.
