# JÚPITER — Preflight real VFR/360 (2026-10-30)

## Resultado de lectura en VM
`experiments/media_optimization/real_media_metadata_preflight.py` ejecutado por fer; archivo local `/home/fer/montara-real-media-preflight-01.json`; Git limpio en rama `fernando/continuacion-montara`. Sin transcodificar ni renderizar.

- `IMG_0044.MOV`: H.264 3840×2160, BT.709; duración 986.825011 s; display matrix rotación **−180°**. En ventanas de paquetes `5%+3` y `60%+3`, 90 paquetes por ventana; deltas PTS positivos 89 por ventana:
  - ventana 5s: 58×33.333 ms, 30×33.334 ms, 1×35 ms.
  - ventana 60s: 59×33.333 ms, 29×33.334 ms, 1×35 ms.
  - Esta variación aislada no certifica VFR de fichero completo ni problema perceptible de sincronía. Ni hay HDR ni HEVC documentado para este iPhone.
- `VID_20260824_204524_00_004.mp4`: HEVC 3840×1920 25fps, BT.709; `Spherical Mapping` **projection=equirectangular**, yaw/pitch/roll 0; Stereo 3D type 2D. Confirma metadatos esféricos reales para F4 (a 4K, no 5.7K).
- Estado servidor al comprobar: `uptime` load 12.40, 24.68, 23.82; procesos independientes de jm `ffmpeg` PID 75522 ~259% CPU y PID 75523 ~239% CPU; `gunicorn` jm ~45%. **No iniciar benchmark ni render todavía**. Los números de ps son muestras de %CPU reportado por el comando, no una medición científica de ocupación instantánea.

## Próxima decisión
Cuando jm confirme inactividad y load normalizado, medir F4 en **fragmentos cortos reales**, revisar métricas de frames/rostros/texto/cables y estabilidad; operador recibirá aviso antes de render pesado. No usar 15 minutos enteros. Para FOCUS A/C el primer gate verdadero exige plan construido desde proxies, sustitución por originales, rotación y sync conservados. No tocar main/engine/mixer.
